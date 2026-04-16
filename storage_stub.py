"""
docksmith/storage_stub.py
--------------------------
Storage and image-management module for Docksmith.

Responsibilities:
    - initialize local state under ~/.docksmith
    - store layers as content-addressed tar blobs
    - load/save image manifests
    - provide layer path resolution helpers
"""

import hashlib
import json
import os
import tarfile
from urllib.parse import quote
from typing import Optional

from types_ import ImageManifest, ImageConfig, LayerEntry

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")


def _ensure_dirs():
    for d in [IMAGES_DIR, LAYERS_DIR]:
        os.makedirs(d, exist_ok=True)


def init_storage():
    """Ensure Docksmith storage directories exist."""
    _ensure_dirs()


def _manifest_filename(name: str, tag: str) -> str:
    """Build a cross-platform safe manifest file name."""
    return f"{quote(name, safe='')}--{quote(tag, safe='')}.json"


def _legacy_manifest_filename(name: str, tag: str) -> str:
    """Legacy filename format used by older builds."""
    return f"{name}:{tag}.json"


def get_manifest_path(name: str, tag: str) -> str:
    """Return preferred manifest path for reading/writing."""
    return os.path.join(IMAGES_DIR, _manifest_filename(name, tag))


def find_manifest_path(name: str, tag: str) -> Optional[str]:
    """Find manifest path, preferring current format with legacy fallback."""
    preferred = get_manifest_path(name, tag)
    if os.path.exists(preferred):
        return preferred

    legacy = os.path.join(IMAGES_DIR, _legacy_manifest_filename(name, tag))
    if os.path.exists(legacy):
        return legacy
    return None


def load_manifest(name: str, tag: str) -> Optional[ImageManifest]:
    """Load an image manifest from disk. Returns None if not found."""
    _ensure_dirs()
    path = find_manifest_path(name, tag)
    if path is None:
        return None
    with open(path, "r") as f:
        data = json.load(f)
    config = ImageConfig(
        env=data["config"].get("Env", []),
        cmd=data["config"].get("Cmd", []),
        working_dir=data["config"].get("WorkingDir", ""),
    )
    layers = [
        LayerEntry(digest=l["digest"], size=l["size"], created_by=l["createdBy"])
        for l in data.get("layers", [])
    ]
    return ImageManifest(
        name=data["name"],
        tag=data["tag"],
        digest=data["digest"],
        created=data["created"],
        config=config,
        layers=layers,
    )


def save_manifest(manifest: ImageManifest):
    """
    Serialize and save an image manifest.
    Computes the manifest digest by hashing the JSON with digest=''.
    """
    _ensure_dirs()

    def _to_dict(m: ImageManifest, digest_override: str = "") -> dict:
        return {
            "name": m.name,
            "tag": m.tag,
            "digest": digest_override,
            "created": m.created,
            "config": {
                "Env": m.config.env,
                "Cmd": m.config.cmd,
                "WorkingDir": m.config.working_dir,
            },
            "layers": [
                {"digest": l.digest, "size": l.size, "createdBy": l.created_by}
                for l in m.layers
            ],
        }

    # Compute digest over canonical JSON with digest=""
    canonical = json.dumps(_to_dict(manifest, digest_override=""), sort_keys=True, separators=(",", ":"))
    computed = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    manifest.digest = computed

    final = json.dumps(_to_dict(manifest, digest_override=computed), indent=2)
    path = get_manifest_path(manifest.name, manifest.tag)
    with open(path, "w") as f:
        f.write(final)


def create_layer(staged_dir: str, created_by: str) -> LayerEntry:
    """
    Create a content-addressed tar layer from staged_dir.
    Files are added in sorted order with timestamps zeroed for determinism.
    Returns a LayerEntry with the digest and size.
    """
    _ensure_dirs()
    import io

    # Build the tar in memory first to compute its digest
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        all_files = []
        for root, dirs, files in os.walk(staged_dir):
            dirs.sort()
            for fname in sorted(files):
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, staged_dir)
                all_files.append((full, arcname))

        for full_path, arcname in all_files:
            info = tar.gettarinfo(full_path, arcname=arcname)
            info.mtime = 0       # zero timestamps for determinism
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            with open(full_path, "rb") as f:
                tar.addfile(info, f)

    raw = buf.getvalue()
    hex_digest = hashlib.sha256(raw).hexdigest()
    digest = f"sha256:{hex_digest}"
    layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")

    if not os.path.exists(layer_path):
        with open(layer_path, "wb") as f:
            f.write(raw)

    return LayerEntry(digest=digest, size=len(raw), created_by=created_by)


def get_layer_path(digest: str) -> str:
    """Return the filesystem path for a layer tar given its digest."""
    hex_part = digest.replace("sha256:", "")
    return os.path.join(LAYERS_DIR, hex_part + ".tar")
