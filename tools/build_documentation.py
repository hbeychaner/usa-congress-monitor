"""Build static source references, rendered diagram pages, and a local GitHub wiki."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from pydantic import BaseModel, Field


class SymbolKind(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async function"
    FIELD = "field"


class SourceSymbol(BaseModel):
    name: str
    kind: str
    line: int
    signature: str


class SourceModule(BaseModel):
    path: Path
    symbols: list[SourceSymbol] = Field(default_factory=list)


class DocumentationConfig(BaseModel):
    root: Path
    repository_url: str = "https://github.com/hbeychaner/usa-congress-monitor"
    source_ref: str = "main"
    python_roots: tuple[str, ...] = ("cdm", "scripts", "tools")
    link_pattern: str = r"(?<!!)\[(?:`[^`]*`|[^\]\n])+\]\(([^)\n]+)\)"
    wiki_files: tuple[str, ...] = (
        "README.md",
        "architecture.md",
        "OPERATIONS_RUNBOOK.md",
        "CONTRIBUTING.md",
    )
    wiki_directories: tuple[str, ...] = ("guides", "reference")
    repository_only_start: str = "<!-- wiki:repository-only:start -->"
    repository_only_end: str = "<!-- wiki:repository-only:end -->"

    @property
    def documentation(self) -> Path:
        return self.root / "documentation"


class PythonSymbolReader(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[SourceSymbol] = []
        self.scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        self._record(node.name, SymbolKind.CLASS, node.lineno, f"({bases})")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node, SymbolKind.FUNCTION)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node, SymbolKind.ASYNC_FUNCTION)

    def _function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: SymbolKind
    ) -> None:
        signature = f"({ast.unparse(node.args)})"
        if node.returns is not None:
            signature += f" -> {ast.unparse(node.returns)}"
        self._record(node.name, kind, node.lineno, signature)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._record(
                node.target.id,
                SymbolKind.FIELD,
                node.lineno,
                f": {ast.unparse(node.annotation)}",
            )
        self.generic_visit(node)

    def _record(self, name: str, kind: SymbolKind, line: int, signature: str) -> None:
        self.symbols.append(
            SourceSymbol(
                name=".".join((*self.scope, name)),
                kind=kind,
                line=line,
                signature=signature,
            )
        )


class DocumentationBuilder:
    def __init__(self, config: DocumentationConfig) -> None:
        self.config = config

    def source_modules(self) -> list[SourceModule]:
        inventory = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=self.config.root,
            text=True,
            capture_output=True,
            check=True,
        )
        paths = [
            self.config.root / name
            for name in inventory.stdout.split("\0")
            if name.endswith(".py")
            and Path(name).parts[0] in self.config.python_roots
            and (self.config.root / name).is_file()
        ]
        modules: list[SourceModule] = []
        for path in sorted(paths):
            reader = PythonSymbolReader()
            reader.visit(
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            )
            modules.append(
                SourceModule(
                    path=path.relative_to(self.config.root), symbols=reader.symbols
                )
            )
        result = subprocess.run(
            ["node", str(self.config.root / "tools/build_frontend_reference.mjs")],
            cwd=self.config.root,
            text=True,
            capture_output=True,
            check=True,
        )
        modules.extend(
            SourceModule.model_validate(value) for value in json.loads(result.stdout)
        )
        return modules

    def reference_pages(self) -> dict[Path, str]:
        groups: dict[Path, list[SourceModule]] = {}
        modules = self.source_modules()
        for module in modules:
            parts = module.path.parts
            group = Path(parts[1] if parts[0] == "cdm" else parts[0])
            if parts[0] == "cdm" and len(parts) == 2:
                group = Path("composition")
            groups.setdefault(group, []).append(module)
        destination = self.config.documentation / "reference/symbols"
        pages: dict[Path, str] = {}
        overview = [
            "# Source symbol index",
            "",
            "Generated by `uv run python tools/build_documentation.py`; do not edit.",
            "",
            "This is a static declaration catalogue, not a call graph or inferred API.",
            "Python includes every declared class, function (including private and nested",
            "functions), and annotated name in application, scripts and tools source.",
            "Ignored local scripts and tests are excluded. TypeScript/TSX includes classes,",
            "interfaces, type aliases, enums, variables, methods, and properties in",
            "the frontend source. Inherited fields, runtime-generated names, imports,",
            "anonymous callbacks, and Python unannotated assignments are not expanded.",
            "Class fields link to their declarations; defaults and validation behavior",
            "remain authoritative in source. Follow the narrative chapters for intent.",
            "",
            "| Area | Files | Declarations |",
            "|---|---:|---:|",
        ]
        for group, items in sorted(groups.items()):
            target = destination / f"{group.as_posix()}.md"
            count = sum(len(item.symbols) for item in items)
            overview.append(
                f"| [{group}]({group.as_posix()}.md) | {len(items)} | {count} |"
            )
            lines = [
                f"# {group} source reference",
                "",
                "[All source areas](README.md)",
                "",
                "Generated from declarations; see the catalogue scope in the index.",
                "",
            ]
            for module in items:
                link = "../../../" + module.path.as_posix()
                lines.extend(
                    [f"## {module.path.as_posix()}", "", f"[Source]({link})", ""]
                )
                if not module.symbols:
                    lines.extend(["No declarations in this module.", ""])
                for symbol in module.symbols:
                    label = f"{symbol.name}{symbol.signature}".replace("`", "'")
                    label = " ".join(label.split()).replace("|", r"\|")
                    lines.append(f"- {symbol.kind}: [`{label}`]({link}#L{symbol.line})")
                lines.append("")
            pages[target] = "\n".join(lines)
        overview.extend(
            [
                "",
                (
                    f"Total: {len(modules)} source files; "
                    f"{sum(len(module.symbols) for module in modules)} declarations."
                ),
                "",
            ]
        )
        pages[destination / "README.md"] = "\n".join(overview)
        return pages

    def visual_page(self) -> dict[Path, str]:
        diagrams = sorted((self.config.documentation / "diagrams").glob("*.mmd"))
        diagrams.append(self.config.root / "worker-architecture.mmd")
        lines = [
            "# Visual atlas",
            "",
            (
                "Generated from the `.mmd` sources by "
                "`uv run python tools/build_documentation.py`."
            ),
            "The diagrams describe implementation boundaries, not measured production",
            "coverage. C4 context, containers, and components are different zoom levels.",
            "",
        ]
        for path in diagrams:
            if path.parent == self.config.root:
                relative = Path("../..") / path.name
            else:
                relative = Path("..") / path.relative_to(self.config.documentation)
            lines.extend(
                [
                    f"## {path.stem}",
                    "",
                    f"[Editable Mermaid source]({relative.as_posix()})",
                    "",
                    "```mermaid",
                    path.read_text(encoding="utf-8").strip(),
                    "```",
                    "",
                ]
            )
        return {self.config.documentation / "reference/visuals.md": "\n".join(lines)}

    def write_pages(self, pages: dict[Path, str], *, check: bool) -> None:
        stale: list[Path] = []
        for path, content in pages.items():
            if check:
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    stale.append(path)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        if stale:
            names = ", ".join(str(path) for path in stale)
            raise ValueError(f"Generated documentation is stale: {names}")

    def wiki_name(self, path: Path) -> str:
        relative = path.relative_to(self.config.documentation)
        if relative == Path("README.md"):
            return "Home"
        return "-".join(relative.with_suffix("").parts)

    def wiki_link(self, origin: Path, href: str, pages: set[Path]) -> str:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or href.startswith("#"):
            return href
        target = (origin.parent / unquote(parsed.path)).resolve()
        if target in pages:
            result = self.wiki_name(target)
        else:
            relative = target.relative_to(self.config.root)
            tree = "tree" if target.is_dir() else "blob"
            result = (
                f"{self.config.repository_url}/{tree}/"
                f"{quote(self.config.source_ref, safe='')}/"
                f"{quote(relative.as_posix(), safe='/')}"
            )
        if parsed.fragment:
            result += f"#{parsed.fragment}"
        return result

    def wiki_text(self, path: Path) -> str:
        lines: list[str] = []
        repository_only = False
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            marker = line.strip()
            if marker == self.config.repository_only_start:
                if repository_only:
                    raise ValueError(f"Nested repository-only wiki block: {path}")
                repository_only = True
            elif marker == self.config.repository_only_end:
                if not repository_only:
                    raise ValueError(f"Unmatched repository-only wiki end: {path}")
                repository_only = False
            elif not repository_only:
                lines.append(line)
        if repository_only:
            raise ValueError(f"Unclosed repository-only wiki block: {path}")
        return "".join(lines)

    def build_wiki(self, output: Path, *, check: bool) -> None:
        if output.resolve() == self.config.documentation.resolve():
            raise ValueError("Wiki output must not overwrite canonical documentation")
        sources = {
            path.resolve()
            for path in self.config.documentation.rglob("*.md")
            if output.resolve() not in path.resolve().parents
            and "wiki" not in path.relative_to(self.config.documentation).parts
            and "original" not in path.relative_to(self.config.documentation).parts
            and (
                path.relative_to(self.config.documentation).as_posix()
                in self.config.wiki_files
                or path.relative_to(self.config.documentation).parts[0]
                in self.config.wiki_directories
            )
        }
        names = [self.wiki_name(path) for path in sources]
        if len(set(names)) != len(names):
            raise ValueError("Wiki page names collide")
        pages: dict[Path, str] = {}
        for path in sorted(sources):
            text = self.wiki_text(path)
            text = re.sub(
                self.config.link_pattern,
                lambda match, path=path: match.group(0).replace(
                    match.group(1), self.wiki_link(path, match.group(1), sources)
                ),
                text,
            )
            canonical = (
                f"{self.config.repository_url}/blob/"
                f"{quote(self.config.source_ref, safe='')}/"
                f"{quote(path.relative_to(self.config.root).as_posix(), safe='/')}"
            )
            pages[output / f"{self.wiki_name(path)}.md"] = (
                f"> Generated from [canonical repository documentation]({canonical}). "
                "Edit the repository source, not this wiki copy.\n\n" + text
            )
        pages[output / "_Sidebar.md"] = (
            "## Congress Tracker\n\n"
            "[Home](Home)\n\n"
            "### Understand\n"
            "- [Architecture](architecture)\n"
            "- [Visual atlas](reference-visuals)\n"
            "- [Data structures](reference-data-models)\n"
            "- [Indexing](reference-indexing)\n"
            "- [API and web app](reference-api-and-frontend)\n"
            "- [Source symbols](reference-symbols-README)\n\n"
            "### Operate and develop\n"
            "- [Ingestion](guides-ingestion)\n"
            "- [Analytics](guides-analytics)\n"
            "- [Configuration and deployment](guides-configuration-and-deployment)\n"
            "- [Operations runbook](OPERATIONS_RUNBOOK)\n"
            "- [Documentation maintenance](CONTRIBUTING)\n"
        )
        pages[output / "_Footer.md"] = (
            "Congress Tracker | Repository documentation is canonical. "
            "Regenerate before publishing; do not edit generated wiki pages.\n"
        )
        unexpected = set(output.glob("*.md")) - pages.keys()
        if unexpected:
            raise ValueError(
                "Wiki contains obsolete or unmanaged pages; inspect and remove "
                f"them before regenerating: {sorted(str(path) for path in unexpected)}"
            )
        self.write_pages(pages, check=check)

    def validate_links(self) -> None:
        missing: list[str] = []
        sources = [
            self.config.root / "README.md",
            *(
                path
                for path in self.config.documentation.rglob("*.md")
                if "wiki" not in path.relative_to(self.config.documentation).parts
                and "original" not in path.relative_to(self.config.documentation).parts
            ),
        ]
        for path in sources:
            for match in re.finditer(
                self.config.link_pattern, path.read_text(encoding="utf-8")
            ):
                href = match.group(1)
                parsed = urlsplit(href)
                if parsed.scheme or parsed.netloc or href.startswith("#"):
                    continue
                target = path.parent / unquote(parsed.path)
                if not target.exists():
                    missing.append(f"{path.relative_to(self.config.root)}: {href}")
                    continue
                if re.fullmatch(r"L\d+", parsed.fragment) and target.is_file():
                    lines = len(target.read_text(encoding="utf-8").splitlines())
                    if int(parsed.fragment[1:]) > lines:
                        missing.append(f"{path.relative_to(self.config.root)}: {href}")
        if missing:
            raise ValueError(
                f"{len(missing)} broken local documentation links "
                "(showing up to 20):\n" + "\n".join(missing[:20])
            )

    def run(self, *, check: bool, wiki: Path | None, wiki_only: bool = False) -> None:
        if wiki_only and wiki is None:
            raise ValueError("Wiki-only preparation requires an output directory")
        if not wiki_only:
            self.write_pages(self.reference_pages(), check=check)
            self.write_pages(self.visual_page(), check=check)
        self.validate_links()
        if wiki is not None:
            self.build_wiki(wiki, check=check)


class DocumentationCommand:
    def run(self) -> None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--check", action="store_true")
        parser.add_argument(
            "--wiki-only",
            action="store_true",
            help="Prepare/check prose wiki pages without regenerating source references",
        )
        parser.add_argument(
            "--wiki", type=Path, help="Local wiki output; never publishes"
        )
        parser.add_argument("--source-ref", default="main")
        args = parser.parse_args()
        if args.wiki_only and args.wiki is None:
            parser.error("--wiki-only requires --wiki")
        config = DocumentationConfig(
            root=Path(__file__).resolve().parents[1], source_ref=args.source_ref
        )
        DocumentationBuilder(config).run(
            check=args.check, wiki=args.wiki, wiki_only=args.wiki_only
        )
        if args.wiki_only:
            print("Local links and wiki verified; source/visual freshness not checked.")
        else:
            print("Documentation references and local links verified.")
        if args.wiki:
            print(f"Local wiki prepared at {args.wiki.resolve()}; nothing published.")


if __name__ == "__main__":
    DocumentationCommand().run()
