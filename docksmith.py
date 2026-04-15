#!/usr/bin/env python3
"""
docksmith/docksmith.py
----------------------
Main CLI entry point. Dispatches to subcommands:

  docksmith build -t <name:tag> [--no-cache] <context>
  docksmith images
  docksmith rmi <name:tag>
  docksmith run <name:tag> [cmd] [-e KEY=VALUE ...]

Usage:
  python docksmith.py build -t myapp:latest .
  python docksmith.py images
  python docksmith.py rmi myapp:latest
  python docksmith.py run myapp:latest
  python docksmith.py run -e NAME=world myapp:latest
"""

import sys
import os

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

USAGE = """Usage: docksmith <command> [options]

Commands:
  build   -t <name:tag> [--no-cache] <context>   Build an image from a Docksmithfile
  images                                          List all local images
  rmi     <name:tag>                              Remove an image and its layers
  run     [-e KEY=VAL] <name:tag> [cmd]           Run a container from an image

Run 'docksmith <command> --help' for more information on a command.
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    subcmd = sys.argv[1]
    rest = sys.argv[2:]

    if subcmd == "build":
        from build_cmd import main as build_main
        sys.argv = ["docksmith build"] + rest
        build_main()

    elif subcmd == "images":
        from images_cmd import cmd_images
        cmd_images()

    elif subcmd == "rmi":
        if not rest:
            print("Usage: docksmith rmi <name:tag>", file=sys.stderr)
            sys.exit(1)
        from rmi_cmd import cmd_rmi
        cmd_rmi(rest[0])

    elif subcmd == "run":
        from run_cmd import cmd_run
        cmd_run(rest)

    elif subcmd in ("--help", "-h", "help"):
        print(USAGE)

    else:
        print(f"Error: unknown command '{subcmd}'", file=sys.stderr)
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
