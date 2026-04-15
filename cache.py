"""
docksmith/cache.py
------------------
Phase 4 & 7: Deterministic cache key generation + cache hit/miss logic.

Cache key is SHA-256 of:
  - previous layer digest (or base image manifest digest for first layer-producing step)
  - full instruction text as written
  - current WORKDIR value
  - current ENV state (sorted key order)
  - COPY only: SHA-256 of each source file's raw bytes (sorted by path)

Cache index lives at ~/.docksmith/cache/index.json
  { "<cache_key>": "<layer_digest>" }
"""

# COMMIT MESSAGE:
# Add deterministic cache key generation and lookup logic
# - SHA-256 based cache keys from instruction state
# - Source file hashing for COPY instructions
# - Cache index persistence at ~/.docksmith/cache/index.json
# - Cache hit/miss validation with disk verification

import hashlib
import json
import os
import glob as glob_mod
from typing import Optional, Dict, List

from types_ import BuildState


DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
CACHE_INDEX_PATH = os.path.join(DOCKSMITH_DIR, "cache", "index.json")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")


# ---------------------------------------------------------------------------
# Cache key computation
# ---------------------------------------------------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _env_string(env: dict) -> str:
    """Serialize env dict to deterministic string (sorted keys)."""
    if not env:
        return ""
    return ",".join(f"{k}={env[k]}" for k in sorted(env.keys()))


def _previous_digest(state: BuildState) -> str:
    """
    Return the digest to use as the 'previous layer' in cache key computation.
    - If we've already produced a layer in this build: use last_layer_digest
    - Otherwise (first layer-producing step): use base image manifest digest
    """
    if state.last_layer_digest is not None:
        return state.last_layer_digest
    if state.base_manifest is not None:
        return state.base_manifest.digest
    return ""


def compute_cache_key(
    instruction_text: str,
    state: BuildState,
    context_dir: Optional[str] = None,
    copy_src_pattern: Optional[str] = None,
) -> str:
    """
    Compute the deterministic cache key for a COPY or RUN instruction.

    Args:
        instruction_text: The full instruction line as written in the Docksmithfile
                          e.g. "COPY . /app" or "RUN pip install -r requirements.txt"
        state: Current BuildState (has workdir, env, last_layer_digest, base_manifest)
        context_dir: Build context directory (required for COPY to hash source files)
        copy_src_pattern: The src glob pattern from COPY (e.g. "." or "*.py")

    Returns:
        Hex string of the cache key (SHA-256).
    """
    parts: List[str] = []

    # 1. Previous layer digest
    parts.append(_previous_digest(state))

    # 2. Full instruction text
    parts.append(instruction_text)

    # 3. Current WORKDIR
    parts.append(state.workdir or "")

    # 4. Current ENV state (sorted)
    parts.append(_env_string(state.env))

    # 5. COPY only: hash of source files (sorted by path)
    if copy_src_pattern is not None and context_dir is not None:
        file_hashes = _hash_copy_sources(context_dir, copy_src_pattern)
        parts.append(file_hashes)

    key_input = "\n".join(parts).encode("utf-8")
    return _sha256_bytes(key_input)


def _hash_copy_sources(context_dir: str, src_pattern: str) -> str:
    """
    Hash all files matched by src_pattern inside context_dir.
    Files are sorted lexicographically by their relative path.
    Returns a single hex string representing all source files combined.
    """
    # Resolve glob
    pattern = os.path.join(context_dir, src_pattern)
    matched = glob_mod.glob(pattern, recursive=True)

    # Expand directories to all files within
    all_files = []
    for m in matched:
        if os.path.isdir(m):
            for root, _, files in os.walk(m):
                for fname in files:
                    all_files.append(os.path.join(root, fname))
        elif os.path.isfile(m):
            all_files.append(m)

    # Sort by relative path for determinism
    all_files.sort(key=lambda p: os.path.relpath(p, context_dir))

    h = hashlib.sha256()
    for fpath in all_files:
        rel = os.path.relpath(fpath, context_dir)
        h.update(rel.encode("utf-8"))
        h.update(_sha256_file(fpath).encode("utf-8"))

    return h.hexdigest()


# ---------------------------------------------------------------------------
# Cache index read/write
# ---------------------------------------------------------------------------

def _load_index() -> Dict[str, str]:
    """Load the cache index from disk. Returns {} if not found."""
    if not os.path.exists(CACHE_INDEX_PATH):
        return {}
    with open(CACHE_INDEX_PATH, "r") as f:
        return json.load(f)


def _save_index(index: Dict[str, str]):
    """Persist the cache index to disk."""
    os.makedirs(os.path.dirname(CACHE_INDEX_PATH), exist_ok=True)
    with open(CACHE_INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)


def cache_lookup(cache_key: str) -> Optional[str]:
    """
    Look up a cache key.
    Returns the layer digest ("sha256:<hex>") if there's a hit AND the layer file
    actually exists on disk. Returns None on any miss.
    """
    index = _load_index()
    digest = index.get(cache_key)
    if digest is None:
        return None

    # Verify the layer file is actually present (may have been deleted by rmi)
    hex_part = digest.replace("sha256:", "")
    layer_path = os.path.join(LAYERS_DIR, hex_part + ".tar")
    if not os.path.exists(layer_path):
        return None  # Layer file gone → treat as miss

    return digest


def cache_store(cache_key: str, layer_digest: str):
    """Store a cache key → layer digest mapping."""
    index = _load_index()
    index[cache_key] = layer_digest
    _save_index(index)
