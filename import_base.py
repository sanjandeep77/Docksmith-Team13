#!/usr/bin/env python3
"""
import_base.py
--------------
One-time setup: imports a docker-saved tar into ~/.docksmith/

Usage:
    python3 import_base.py alpine:3.18 alpine.tar
"""

import hashlib
import json
import os
import sys
import tarfile
import tempfile
import shutil
from urllib.parse import quote

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")


def manifest_filename(name, tag):
    return f"{quote(name, safe='')}--{quote(tag, safe='')}.json"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def import_image(image_ref, tar_path):
    if ":" in image_ref:
        name, tag = image_ref.rsplit(":", 1)
    else:
        name, tag = image_ref, "latest"

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)

    print(f"Importing {image_ref} from {tar_path} ...")

    with tempfile.TemporaryDirectory(prefix="docksmith_import_") as tmpdir:
        # Extract the docker-saved tar
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(tmpdir)

        # Read manifest.json to find layers
        manifest_path = os.path.join(tmpdir, "manifest.json")
        with open(manifest_path) as f:
            docker_manifest = json.load(f)

        entry = docker_manifest[0]
        layer_paths = entry.get("Layers", [])  # e.g. ["abc123/layer.tar", ...]

        # Read image config for ENV, CMD, WorkingDir
        config_file = entry.get("Config", "")
        config_path = os.path.join(tmpdir, config_file)
        config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)

        container_config = config.get("config", config.get("Config", {}))
        env_list = container_config.get("Env") or []
        cmd_list = container_config.get("Cmd") or []
        workdir = container_config.get("WorkingDir") or ""

        # Copy each layer tar into ~/.docksmith/layers/ named by its sha256
        imported_layers = []
        for rel_layer_path in layer_paths:
            src = os.path.join(tmpdir, rel_layer_path)
            digest_hex = sha256_file(src)
            dest = os.path.join(LAYERS_DIR, digest_hex + ".tar")
            size = os.path.getsize(src)

            if not os.path.exists(dest):
                shutil.copy2(src, dest)
                print(f"  Imported layer sha256:{digest_hex[:12]}  ({size} bytes)")
            else:
                print(f"  Layer already exists sha256:{digest_hex[:12]}")

            imported_layers.append({
                "digest": f"sha256:{digest_hex}",
                "size": size,
                "createdBy": f"<{name}:{tag} base layer>",
            })

        # Build the manifest
        manifest_data = {
            "name": name,
            "tag": tag,
            "digest": "",
            "created": "2024-01-01T00:00:00Z",
            "config": {
                "Env": env_list,
                "Cmd": cmd_list,
                "WorkingDir": workdir,
            },
            "layers": imported_layers,
        }

        # Compute digest: sha256 of canonical JSON with digest=""
        canonical = json.dumps(manifest_data, sort_keys=True, separators=(",", ":"))
        computed = "sha256:" + sha256_bytes(canonical.encode("utf-8"))
        manifest_data["digest"] = computed

        # Write manifest
        out_path = os.path.join(IMAGES_DIR, manifest_filename(name, tag))
        with open(out_path, "w") as f:
            json.dump(manifest_data, f, indent=2)

        print(f"\nSuccessfully imported {name}:{tag}")
        print(f"  Digest  : {computed[:19]}")
        print(f"  Layers  : {len(imported_layers)}")
        print(f"  Manifest: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 import_base.py <name:tag> <tar_file>")
        print("Example: python3 import_base.py alpine:3.18 alpine.tar")
        sys.exit(1)
    import_image(sys.argv[1], sys.argv[2])