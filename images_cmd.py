#!/usr/bin/env python3
"""
docksmith/images_cmd.py
-----------------------
Implements: docksmith images

Lists all images in the local store.
Columns: Name, Tag, ID (first 12 chars of digest), Created
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import storage_stub as storage


def cmd_images():
    storage.init_storage()

    if not os.path.isdir(storage.IMAGES_DIR):
        print("No images found.")
        return

    manifests = []
    for fname in sorted(os.listdir(storage.IMAGES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(storage.IMAGES_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            manifests.append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    if not manifests:
        print("No images found.")
        return

    # Print table
    fmt = "{:<20} {:<12} {:<14} {}"
    print(fmt.format("NAME", "TAG", "ID", "CREATED"))
    for m in manifests:
        digest = m.get("digest", "")
        short_id = digest.replace("sha256:", "")[:12]
        print(fmt.format(
            m.get("name", ""),
            m.get("tag", ""),
            short_id,
            m.get("created", ""),
        ))


if __name__ == "__main__":
    cmd_images()
