"""
docksmith/types.py
------------------
Shared data types used across all three modules (Storage, Runtime, Build Engine).
Person C defines these so all three team members can work in parallel.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LayerEntry:
    """Represents one layer in an image manifest."""
    digest: str       # "sha256:<hex>"
    size: int         # byte size of the tar file on disk
    created_by: str   # instruction that produced this layer, e.g. "COPY . /app"


@dataclass
class ImageConfig:
    """Image-level config stored in the manifest."""
    env: List[str] = field(default_factory=list)       # ["KEY=value", ...]
    cmd: List[str] = field(default_factory=list)       # ["python", "main.py"]
    working_dir: str = ""


@dataclass
class ImageManifest:
    """Full image manifest — stored as JSON in ~/.docksmith/images/<name>:<tag>.json"""
    name: str
    tag: str
    digest: str          # sha256 of canonical manifest JSON
    created: str         # ISO-8601 timestamp
    config: ImageConfig
    layers: List[LayerEntry] = field(default_factory=list)


@dataclass
class Instruction:
    """One parsed line from a Docksmithfile."""
    line_number: int
    opcode: str          # FROM, COPY, RUN, WORKDIR, ENV, CMD
    args: str            # everything after the opcode


@dataclass
class BuildState:
    """Mutable state tracked across instructions during a build."""
    base_manifest: Optional[ImageManifest] = None
    layers: List[LayerEntry] = field(default_factory=list)
    workdir: str = ""
    env: dict = field(default_factory=dict)   # {key: value}
    cmd: List[str] = field(default_factory=list)
    last_layer_digest: Optional[str] = None   # digest of the last COPY/RUN layer
