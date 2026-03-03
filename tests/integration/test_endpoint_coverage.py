"""Coverage check for endpoint helper functions.

This test verifies that all endpoint getter functions (get_*) in
src.data_collection.endpoints are exercised somewhere in the integration tests.
"""

from __future__ import annotations

import ast
import inspect
import importlib
import pkgutil
from pathlib import Path
from typing import Iterable, Set, Tuple


ENDPOINTS_PACKAGE = "src.data_collection.endpoints"


def iter_endpoint_getters() -> Iterable[Tuple[str, str]]:
    """Yield (qualified_name, function_name) for list-level endpoint getters."""
    package = importlib.import_module(ENDPOINTS_PACKAGE)
    package_paths = [str(path) for path in package.__path__]
    for module_info in pkgutil.iter_modules(package_paths):
        module = importlib.import_module(f"{ENDPOINTS_PACKAGE}.{module_info.name}")
        module_file = Path(getattr(module, "__file__", ""))
        referenced_getters: Set[str] = set()
        if module_file.is_file():
            tree = ast.parse(
                module_file.read_text(encoding="utf-8"), filename=str(module_file)
            )
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith(
                    "gather_"
                ):
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.Call):
                            func = inner.func
                            if isinstance(func, ast.Name) and func.id.startswith(
                                "get_"
                            ):
                                referenced_getters.add(func.id)
                            elif isinstance(
                                func, ast.Attribute
                            ) and func.attr.startswith("get_"):
                                referenced_getters.add(func.attr)
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if obj.__module__ != module.__name__:
                continue
            if not name.startswith("get_"):
                continue
            if referenced_getters and name not in referenced_getters:
                continue
            yield f"{module.__name__}.{name}", name


def collect_referenced_names(tests_dir: Path) -> Set[str]:
    """Collect referenced names anywhere in integration tests."""
    referenced: Set[str] = set()
    for path in tests_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
    return referenced


def test_endpoint_getter_coverage() -> None:
    """Ensure all endpoint getter functions are called in integration tests."""
    tests_dir = Path(__file__).resolve().parent
    referenced_names = collect_referenced_names(tests_dir)
    missing = [
        qualified
        for qualified, name in iter_endpoint_getters()
        if name not in referenced_names
    ]
    assert not missing, (
        "Missing integration test coverage for endpoint getters: "
        + ", ".join(sorted(missing))
    )
