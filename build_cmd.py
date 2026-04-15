#!/usr/bin/env python3
"""
docksmith/build_cmd.py
----------------------
Phase 10: CLI for 'docksmith build'

Usage:
    python build_cmd.py -t myapp:latest .
    python build_cmd.py -t myapp:latest --no-cache .

This is the user-facing entry point for the build command.
When Person A and B are done, this file wires everything together.
"""

# COMMIT MESSAGE:
# Add CLI entry point for docksmith build command
# - Argument parsing for -t/--tag and --no-cache options
# - Build context validation
# - Integration with engine and parser modules
# - User-friendly error handling and exit codes

import argparse
import sys
import os

# Make sure we can import sibling modules
sys.path.insert(0, os.path.dirname(__file__))

from engine import build_image, BuildError
from parser import ParseError


def main():
    parser = argparse.ArgumentParser(
        prog="docksmith build",
        description="Build a container image from a Docksmithfile.",
    )
    parser.add_argument(
        "-t", "--tag",
        required=True,
        metavar="NAME:TAG",
        help="Name and tag of the image to build (e.g. myapp:latest)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Skip all cache lookups and writes for this build.",
    )
    parser.add_argument(
        "context",
        metavar="CONTEXT",
        help="Path to the build context directory (must contain a Docksmithfile).",
    )

    args = parser.parse_args()

    # Parse name:tag
    if ":" in args.tag:
        name, tag = args.tag.rsplit(":", 1)
    else:
        name, tag = args.tag, "latest"

    context_dir = os.path.abspath(args.context)
    if not os.path.isdir(context_dir):
        print(f"Error: context directory '{context_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        build_image(
            context_dir=context_dir,
            name=name,
            tag=tag,
            no_cache=args.no_cache,
        )
    except (BuildError, ParseError) as e:
        print(f"Build failed: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBuild interrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
