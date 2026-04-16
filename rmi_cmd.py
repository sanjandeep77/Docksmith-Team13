#!/usr/bin/env python3
"""
docksmith/rmi_cmd.py
--------------------
Implements: docksmith rmi <name:tag>

Removes the image manifest and all of its layer files from disk.
Fails with a clear error if the image does not exist.

Note (per PRD): No reference counting. If another image shares a layer,
that layer file will be deleted too — this is expected behavior.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import storage_stub as storage


def cmd_rmi(image_ref: str):
    storage.init_storage()

    if ":" in image_ref:
        name, tag = image_ref.rsplit(":", 1)
    else:
        name, tag = image_ref, "latest"

    manifest_path = storage.find_manifest_path(name, tag)
    if manifest_path is None:
        print(f"Error: image '{image_ref}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        data = json.load(f)

    # Collect layer digests that belong to this image
    # Per PRD: only delete layers listed in THIS image's manifest
    removed_layers = []
    skipped_layers = []
    for layer in data.get("layers", []):
        digest = layer.get("digest", "")
        hex_part = digest.replace("sha256:", "")
        layer_path = os.path.join(storage.LAYERS_DIR, hex_part + ".tar")
        if os.path.exists(layer_path):
            os.remove(layer_path)
            removed_layers.append(digest[:19])
        else:
            skipped_layers.append(digest[:19])

    # Remove the manifest
    os.remove(manifest_path)

    print(f"Untagged: {name}:{tag}")
    for d in removed_layers:
        print(f"Deleted: {d}")
    if skipped_layers:
        for d in skipped_layers:
            print(f"Already gone: {d}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: docksmith rmi <name:tag>", file=sys.stderr)
        sys.exit(1)
    cmd_rmi(sys.argv[1])
