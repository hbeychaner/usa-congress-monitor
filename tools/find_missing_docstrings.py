"""Scan repository Python files and report functions/classes without docstrings.

Usage: python tools/find_missing_docstrings.py
"""

import ast
import os

ROOT = "."
skip_prefixes = ("./.", "./venv", "./env", "./.venv")
ignore_dirs = {"__pycache__", ".git"}
results = []

for root, dirs, files in os.walk(ROOT):
    # filter out ignored dirs
    dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
    for fname in files:
        if not fname.endswith(".py"):
            continue
        path = os.path.join(root, fname)
        if any(path.startswith(p) for p in skip_prefixes):
            continue
        try:
            with open(path, encoding="utf-8") as source_file:
                src = source_file.read()
            tree = ast.parse(src)
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            # Skip files we cannot read or parse and report the reason.
            print(f"Skipping {path}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                doc = ast.get_docstring(node)
                if not doc:
                    results.append((
                        path.removeprefix("./"),
                        node.lineno,
                        type(node).__name__,
                        name,
                    ))

# deduplicate and sort
seen = set()
uniq = []
for item in results:
    if item in seen:
        continue
    seen.add(item)
    uniq.append(item)
uniq.sort()

for p, ln, t, n in uniq:
    print(f"{p}:{ln} {t} {n}")
print(f"FOUND:{len(uniq)}")
