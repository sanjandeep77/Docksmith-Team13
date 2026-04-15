"""
docksmith/runtime_stub.py
--------------------------
Runtime implementation for Person B's module.

Implements Linux process isolation for both:
  - build-time RUN instruction execution
  - `docksmith run`

Isolation model:
  - unshare namespaces (user, mount, uts, ipc, pid)
  - chroot into the assembled root filesystem
  - mount /proc in the new mount namespace

The same mechanism is used for both build and run flows.
"""

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import List, Optional


_ROOTFS_HINT_KEY = "DOCKSMITH_INTERNAL_ROOTFS"


def _safe_extract_tar(tar: tarfile.TarFile, dest_dir: str):
    """Extract a tar safely and reject path traversal entries."""
    dest_real = os.path.realpath(dest_dir)
    for member in tar.getmembers():
        target_path = os.path.realpath(os.path.join(dest_dir, member.name))
        if target_path != dest_real and not target_path.startswith(dest_real + os.sep):
            raise RuntimeError(f"Unsafe layer entry detected: {member.name!r}")
    tar.extractall(path=dest_dir)


def _normalize_workdir(workdir: str) -> str:
    wd = (workdir or "/").strip()
    if not wd.startswith("/"):
        wd = "/" + wd
    return wd


def _build_isolated_command(rootfs: str, workdir: str, command: List[str]) -> List[str]:
    if not command:
        raise RuntimeError("No command provided to runtime.")

    chroot_bin = shutil.which("chroot")
    unshare_bin = shutil.which("unshare")
    if not chroot_bin:
        raise RuntimeError("Missing 'chroot' binary; Linux runtime cannot start container.")
    if not unshare_bin:
        raise RuntimeError("Missing 'unshare' binary; namespace isolation is required.")

    # Use shell positional arguments to avoid manual quoting/escaping.
    shell_script = 'cd "$1" && shift && exec "$@"'
    inner = [
        chroot_bin,
        rootfs,
        "/bin/sh",
        "-c",
        shell_script,
        "docksmith-run",
        workdir,
        *command,
    ]

    # Rootless-first strategy: use user namespace and map caller to root in namespace.
    return [
        unshare_bin,
        "--user",
        "--map-root-user",
        "--mount",
        "--uts",
        "--ipc",
        "--pid",
        "--fork",
        "--mount-proc",
        "--",
        *inner,
    ]


def run_in_container(
    layer_tars: List[str],
    command: List[str],
    workdir: str = "/",
    env_vars: Optional[dict] = None,
) -> int:
    """
    Assemble a root filesystem from layer_tars (in order), then execute
    `command` inside it using Linux isolation (chroot + namespaces).

    Args:
        layer_tars: Ordered list of tar file paths to extract (base first).
        command: Command to execute, e.g. ["sh", "-c", "pip install -r requirements.txt"]
        workdir: Working directory inside the container.
        env_vars: Environment variables to inject (image ENV + any overrides).

    Returns:
        Exit code of the process.

    Raises:
        RuntimeError: If isolation cannot be set up.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Docksmith runtime requires Linux (chroot + namespaces).")

    effective_env = dict(env_vars or {})
    external_rootfs = effective_env.pop(_ROOTFS_HINT_KEY, None)
    workdir = _normalize_workdir(workdir)

    # Keep environment deterministic and explicit.
    child_env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }
    child_env.update(effective_env)

    def _run_with_rootfs(rootfs: str) -> int:
        os.makedirs(os.path.join(rootfs, workdir.lstrip("/")), exist_ok=True)
        isolated_cmd = _build_isolated_command(rootfs=rootfs, workdir=workdir, command=command)

        try:
            result = subprocess.run(isolated_cmd, env=child_env)
            return result.returncode
        except FileNotFoundError as e:
            raise RuntimeError(f"Runtime dependency missing: {e}") from e
        except PermissionError as e:
            raise RuntimeError(
                "Insufficient privileges for namespace/chroot runtime. "
                "Enable unprivileged user namespaces or run with required permissions."
            ) from e

    if external_rootfs:
        if not os.path.isdir(external_rootfs):
            raise RuntimeError(f"Internal rootfs path does not exist: {external_rootfs}")
        return _run_with_rootfs(external_rootfs)

    with tempfile.TemporaryDirectory(prefix="docksmith_run_") as rootfs:
        assemble_rootfs(layer_tars, rootfs)
        return _run_with_rootfs(rootfs)


def assemble_rootfs(layer_tars: List[str], dest_dir: str):
    """
    Extract all layer tars in order into dest_dir.
    Used by Person B's runtime for 'docksmith run'.
    """
    os.makedirs(dest_dir, exist_ok=True)
    for tar_path in layer_tars:
        if not os.path.exists(tar_path):
            raise RuntimeError(f"Layer tar not found: {tar_path}")
        with tarfile.open(tar_path, "r") as tar:
            _safe_extract_tar(tar, dest_dir)
