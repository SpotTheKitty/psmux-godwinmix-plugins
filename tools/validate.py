#!/usr/bin/env python3
"""Check index.json against schema.json, and the two things a schema cannot
say: no name is listed twice, and every source is a form the core installs.

    pip install jsonschema
    python tools/validate.py
"""

import json
import pathlib
import re
import sys

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = re.compile(
    r"^(\./[\w./-]+"                      # a folder that ships with the mixer
    r"|[\w.-]+/[\w.-]+(@[\w.+-]+)?"       # a GitHub release
    r"|https://\S+\.git(#\S+)?"           # a git repository
    r"|(cargo|npm|pypi|oci):\S+)$"        # a package
)


def main():
    schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    problems = [f"{'/'.join(map(str, e.path)) or 'the document'}: {e.message}"
                for e in jsonschema.Draft202012Validator(schema).iter_errors(index)]
    seen = set()
    for plugin in index.get("plugins", []):
        name = plugin.get("name", "")
        if name in seen:
            problems.append(f"{name}: listed twice")
        seen.add(name)
        if not SOURCE.match(plugin.get("source", "")):
            problems.append(f"{name}: `{plugin.get('source')}` is not a source the core installs")
        if plugin.get("source", "").startswith("./") and not plugin.get("bundled"):
            problems.append(f"{name}: a folder source is only for a plugin that ships with the mixer")
    for line in problems:
        print(f"::error::{line}")
    print(f"{len(index.get('plugins', []))} plugins, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
