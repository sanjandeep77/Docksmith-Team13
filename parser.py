"""
docksmith/parser.py
-------------------
Phase 1: Parse a Docksmithfile into a list of Instruction objects.
Validates that only the 6 allowed opcodes are used.
Fails immediately with a clear error message and line number on any invalid instruction.
"""

# COMMIT MESSAGE:
# Implement Docksmithfile parser with instruction validation
# - Parse and validate 6 allowed opcodes (FROM, COPY, RUN, WORKDIR, ENV, CMD)
# - Line-by-line parsing with clear error reporting
# - Instruction format validation (JSON for CMD, KEY=VALUE for ENV)
# - Require FROM as first instruction

import json
from typing import List
from types_ import Instruction

ALLOWED_OPCODES = {"FROM", "COPY", "RUN", "WORKDIR", "ENV", "CMD"}


class ParseError(Exception):
    pass


def parse_docksmithfile(path: str) -> List[Instruction]:
    """
    Read a Docksmithfile and return a list of Instruction objects.
    Raises ParseError with line number on any invalid line.
    """
    instructions: List[Instruction] = []

    with open(path, "r") as f:
        lines = f.readlines()

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        # Split into opcode and args
        parts = line.split(None, 1)
        opcode = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""

        if opcode not in ALLOWED_OPCODES:
            raise ParseError(
                f"Line {lineno}: Unknown instruction '{opcode}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_OPCODES))}"
            )

        # Validate specific instruction formats
        _validate_instruction(opcode, args, lineno)

        instructions.append(Instruction(line_number=lineno, opcode=opcode, args=args))

    if not instructions:
        raise ParseError("Docksmithfile is empty or has no instructions.")

    if instructions[0].opcode != "FROM":
        raise ParseError(
            f"Line {instructions[0].line_number}: Docksmithfile must start with FROM."
        )

    return instructions


def _validate_instruction(opcode: str, args: str, lineno: int):
    """Validate the arguments for each instruction type."""
    if not args.strip():
        raise ParseError(f"Line {lineno}: {opcode} requires an argument.")

    if opcode == "CMD":
        try:
            parsed = json.loads(args)
            if not isinstance(parsed, list):
                raise ParseError(f"Line {lineno}: CMD argument must be a JSON array, e.g. [\"sh\", \"-c\", \"echo hi\"]")
        except json.JSONDecodeError:
            raise ParseError(
                f"Line {lineno}: CMD argument must be valid JSON array, e.g. [\"sh\", \"-c\", \"echo hi\"]. Got: {args!r}"
            )

    if opcode == "ENV":
        if "=" not in args:
            raise ParseError(
                f"Line {lineno}: ENV must be in KEY=VALUE format. Got: {args!r}"
            )

    if opcode == "COPY":
        parts = args.split()
        if len(parts) < 2:
            raise ParseError(
                f"Line {lineno}: COPY requires <src> and <dest>. Got: {args!r}"
            )

    if opcode == "FROM":
        if not args.strip():
            raise ParseError(f"Line {lineno}: FROM requires an image name.")
