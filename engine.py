"""
docksmith/engine.py
-------------------
Person C's main deliverable: the Build Engine.

Implements:
  - Phase 2: Build Engine Core (BuildState, main build loop, step logging)
  - Phase 3: State management (WORKDIR, ENV, CMD)
  - Phase 5: COPY instruction
  - Phase 6: RUN instruction
  - Phase 8: Integration with storage and runtime
  - Phase 9: Final image manifest creation

Usage (called by CLI in build.py):
    from engine import build_image
    build_image(
        context_dir=".",
        name="myapp",
        tag="latest",
        no_cache=False,
    )
"""

import datetime
import glob as glob_mod
import json
import os
import shutil
import sys
import tempfile
import time
from typing import List, Optional

from types_ import BuildState, Instruction, ImageManifest, ImageConfig, LayerEntry
from parser import parse_docksmithfile, ParseError
from cache import compute_cache_key, cache_lookup, cache_store
import storage_stub as storage
import runtime_stub as runtime


class BuildError(Exception):
    pass


def build_image(
    context_dir: str,
    name: str,
    tag: str,
    no_cache: bool = False,
) -> ImageManifest:
    """
    Main entry point for the build engine.

    Reads Docksmithfile from context_dir, executes all instructions,
    writes the final image manifest. Returns the final manifest.
    """
    docksmithfile = os.path.join(context_dir, "Docksmithfile")
    if not os.path.exists(docksmithfile):
        raise BuildError(f"No Docksmithfile found in {context_dir!r}")

    # --- Phase 1: Parse ---
    try:
        instructions = parse_docksmithfile(docksmithfile)
    except ParseError as e:
        raise BuildError(str(e))

    total_steps = len(instructions)
    state = BuildState()
    cache_invalidated = no_cache  # once True, all subsequent steps are misses

    build_start = time.monotonic()

    for step_idx, instr in enumerate(instructions, start=1):
        step_label = f"Step {step_idx}/{total_steps}"
        instr_text = f"{instr.opcode} {instr.args}".strip()

        # ------------------------------------------------------------------
        # FROM — load base image, no cache check, no layer created
        # ------------------------------------------------------------------
        if instr.opcode == "FROM":
            print(f"{step_label} : {instr_text}")
            image_ref = instr.args.strip()
            if ":" in image_ref:
                base_name, base_tag = image_ref.rsplit(":", 1)
            else:
                base_name, base_tag = image_ref, "latest"

            manifest = storage.load_manifest(base_name, base_tag)
            if manifest is None:
                raise BuildError(
                    f"Base image '{image_ref}' not found in local store. "
                    f"Import it first with: docksmith import"
                )
            state.base_manifest = manifest
            state.layers = list(manifest.layers)   # inherit base layers
            state.last_layer_digest = None          # first new layer uses manifest digest
            continue

        # ------------------------------------------------------------------
        # WORKDIR — update state only, no layer
        # ------------------------------------------------------------------
        if instr.opcode == "WORKDIR":
            print(f"{step_label} : {instr_text}")
            state.workdir = instr.args.strip()
            continue

        # ------------------------------------------------------------------
        # ENV — update state only, no layer
        # ------------------------------------------------------------------
        if instr.opcode == "ENV":
            print(f"{step_label} : {instr_text}")
            key, _, value = instr.args.partition("=")
            state.env[key.strip()] = value.strip()
            continue

        # ------------------------------------------------------------------
        # CMD — update state only, no layer
        # ------------------------------------------------------------------
        if instr.opcode == "CMD":
            print(f"{step_label} : {instr_text}")
            state.cmd = json.loads(instr.args.strip())
            continue

        # ------------------------------------------------------------------
        # COPY and RUN — layer-producing instructions
        # ------------------------------------------------------------------
        if instr.opcode in ("COPY", "RUN"):
            step_start = time.monotonic()

            # Determine copy src pattern for cache key (COPY only)
            copy_src_pattern = None
            if instr.opcode == "COPY":
                copy_parts = instr.args.split(None, 1)
                copy_src_pattern = copy_parts[0]

            # Compute cache key
            cache_key = compute_cache_key(
                instruction_text=instr_text,
                state=state,
                context_dir=context_dir,
                copy_src_pattern=copy_src_pattern,
            )

            # Cache lookup (skip if no_cache or already invalidated)
            cached_digest = None
            if not cache_invalidated:
                cached_digest = cache_lookup(cache_key)

            if cached_digest is not None:
                # ---- CACHE HIT ----
                elapsed = time.monotonic() - step_start
                print(f"{step_label} : {instr_text} [CACHE HIT] {elapsed:.2f}s")
                # Restore the cached layer into state
                layer_path = storage.get_layer_path(cached_digest)
                layer_size = os.path.getsize(layer_path)
                layer = LayerEntry(
                    digest=cached_digest,
                    size=layer_size,
                    created_by=instr_text,
                )
                state.layers.append(layer)
                state.last_layer_digest = cached_digest

            else:
                # ---- CACHE MISS ----
                cache_invalidated = True  # cascade: all subsequent steps are misses

                if instr.opcode == "COPY":
                    layer = _execute_copy(instr, context_dir, state, instr_text)
                else:
                    layer = _execute_run(instr, context_dir, state, instr_text)

                # Store in cache (unless --no-cache)
                if not no_cache:
                    cache_store(cache_key, layer.digest)

                state.layers.append(layer)
                state.last_layer_digest = layer.digest

                elapsed = time.monotonic() - step_start
                print(f"{step_label} : {instr_text} [CACHE MISS] {elapsed:.2f}s")

    # ------------------------------------------------------------------
    # Phase 9: Build final image manifest
    # ------------------------------------------------------------------
    total_elapsed = time.monotonic() - build_start

    # Check if there's an existing manifest to preserve its created timestamp on full cache hit
    existing = storage.load_manifest(name, tag)
    if existing is not None and not cache_invalidated:
        # All steps were cache hits → preserve original created timestamp
        created = existing.created
    else:
        created = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    env_list = [f"{k}={v}" for k, v in sorted(state.env.items())]

    config = ImageConfig(
        env=env_list,
        cmd=state.cmd,
        working_dir=state.workdir,
    )

    manifest = ImageManifest(
        name=name,
        tag=tag,
        digest="",   # will be computed by save_manifest
        created=created,
        config=config,
        layers=state.layers,
    )

    storage.save_manifest(manifest)

    print(f"Successfully built {manifest.digest[:19]} {name}:{tag} ({total_elapsed:.2f}s)")
    return manifest


# ---------------------------------------------------------------------------
# COPY implementation (Phase 5)
# ---------------------------------------------------------------------------

def _execute_copy(
    instr: Instruction,
    context_dir: str,
    state: BuildState,
    instr_text: str,
) -> LayerEntry:
    """
    Execute a COPY instruction.
    Copies files from context_dir (with glob support) into a staged directory,
    then hands off to storage to create a content-addressed tar layer.
    """
    parts = instr.args.split(None, 1)
    if len(parts) < 2:
        raise BuildError(f"Line {instr.line_number}: COPY requires <src> and <dest>.")

    src_pattern = parts[0]
    dest = parts[1].strip()

    # Resolve globs relative to context_dir
    pattern = os.path.join(context_dir, src_pattern)
    matched = glob_mod.glob(pattern, recursive=True)
    if not matched:
        raise BuildError(
            f"Line {instr.line_number}: COPY source '{src_pattern}' matched no files in context."
        )

    with tempfile.TemporaryDirectory(prefix="docksmith_copy_") as staged:
        for match in matched:
            if os.path.isdir(match):
                # Copy entire directory tree
                for root, dirs, files in os.walk(match):
                    rel_root = os.path.relpath(root, context_dir)
                    for fname in files:
                        src_file = os.path.join(root, fname)
                        dst_rel = os.path.join(dest.lstrip("/"), rel_root, fname)
                        dst_file = os.path.join(staged, dst_rel)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
            else:
                rel = os.path.relpath(match, context_dir)
                dst_rel = os.path.join(dest.lstrip("/"), os.path.basename(match))
                dst_file = os.path.join(staged, dst_rel)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(match, dst_file)

        layer = storage.create_layer(staged, created_by=instr_text)

    return layer


# ---------------------------------------------------------------------------
# RUN implementation (Phase 6)
# ---------------------------------------------------------------------------

def _execute_run(
    instr: Instruction,
    context_dir: str,
    state: BuildState,
    instr_text: str,
) -> LayerEntry:
    """
    Execute a RUN instruction inside the assembled layer filesystem.
    Uses runtime module (Person B) for isolation.

    Delta-layer strategy:
      1. Snapshot every regular file's (size, mtime) BEFORE the command runs.
      2. Run the command inside the assembled rootfs.
      3. Walk the rootfs AFTER — collect only files that are new or modified
         (not present in the snapshot, or whose size/mtime changed).
      4. Stage just those changed files and hand them to storage as the layer.

    This means the layer produced by RUN contains only the diff, not a full
    copy of the entire filesystem — matching how Docker/OCI layers work.
    """
    import stat as stat_mod

    # Virtual filesystem paths that must never appear in a layer.
    _SKIP = ("proc", "sys", "dev", "run", "var/run", "var/lock", "tmp")

    def _is_skipped(rel_path: str) -> bool:
        for prefix in _SKIP:
            if rel_path == prefix or rel_path.startswith(prefix + os.sep):
                return True
        return False

    def _snapshot(rootfs: str) -> dict:
        """
        Return {rel_path: (size, mtime_ns)} for every regular file in rootfs,
        excluding virtual/special directories.
        """
        snap = {}
        for root, dirs, files in os.walk(rootfs, followlinks=False):
            rel_root = os.path.relpath(root, rootfs)
            # Prune virtual dirs in-place so os.walk skips them entirely.
            if _is_skipped(rel_root):
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs
                       if not _is_skipped(os.path.join(rel_root, d)
                                          if rel_root != "." else d)]
            for fname in files:
                src = os.path.join(root, fname)
                try:
                    st = os.lstat(src)
                except OSError:
                    continue
                if not stat_mod.S_ISREG(st.st_mode):
                    continue
                rel = os.path.relpath(src, rootfs)
                snap[rel] = (st.st_size, st.st_mtime_ns)
        return snap

    # --- collect layer tars ------------------------------------------------
    layer_tars = [storage.get_layer_path(l.digest) for l in state.layers]

    # --- build clean env for the container ---------------------------------
    env_dict = {k: v for k, v in state.env.items()}

    command = ["sh", "-c", instr.args.strip()]
    workdir = state.workdir or "/"

    with tempfile.TemporaryDirectory(prefix="docksmith_run_") as rootfs:
        # 1. Assemble rootfs from all prior layers.
        runtime.assemble_rootfs(layer_tars, rootfs)

        # 2. Snapshot the filesystem state BEFORE the command.
        before = _snapshot(rootfs)

        # 3. Run the command inside the isolated container.
        runtime_env = dict(env_dict)
        runtime_env["DOCKSMITH_INTERNAL_ROOTFS"] = rootfs

        exit_code = runtime.run_in_container(
            layer_tars=layer_tars,
            command=command,
            workdir=workdir,
            env_vars=runtime_env,
        )

        if exit_code != 0:
            raise BuildError(
                f"Line {instr.line_number}: RUN command failed with exit code {exit_code}.\n"
                f"Command: {instr.args.strip()}"
            )

        # 4. Snapshot AFTER and compute the delta.
        after = _snapshot(rootfs)

        changed_files = []
        for rel, (size_a, mtime_a) in after.items():
            prev = before.get(rel)
            if prev is None:
                # New file — always include.
                changed_files.append(rel)
            elif prev != (size_a, mtime_a):
                # Existing file whose size or mtime changed — include.
                changed_files.append(rel)
        # (Files that disappeared are deletions; OCI whiteouts are out of scope
        #  for this project, so we simply omit them — same as Docker's basic model.)

        # 5. Stage only the changed files into a clean temp dir.
        with tempfile.TemporaryDirectory(prefix="docksmith_stage_") as staged:
            for rel in changed_files:
                src = os.path.join(rootfs, rel)
                dst = os.path.join(staged, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    shutil.copy2(src, dst)
                except (PermissionError, OSError):
                    continue

            layer = storage.create_layer(staged, created_by=instr_text)

    return layer