import ast
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.build_documentation import (
    DocumentationBuilder,
    DocumentationCommand,
    DocumentationConfig,
    PythonSymbolReader,
    SourceModule,
)


class TestPythonSymbolReader:
    def test_records_nested_functions_private_methods_and_fields(self) -> None:
        reader = PythonSymbolReader()
        reader.visit(
            ast.parse(
                "class Record(BaseModel):\n"
                "    identifier: str\n"
                "    async def _read(self, limit: int = 2) -> str:\n"
                "        def inner() -> int:\n"
                "            return 1\n"
                "        return str(inner())\n"
            )
        )
        assert [symbol.name for symbol in reader.symbols] == [
            "Record",
            "Record.identifier",
            "Record._read",
            "Record._read.inner",
        ]
        assert reader.symbols[2].signature == "(self, limit: int=2) -> str"
        assert reader.symbols[2].kind == "async function"
        assert reader.symbols[2].line == 3


class TestDocumentationBuilder:
    def builder(self, root: Path) -> DocumentationBuilder:
        return DocumentationBuilder(DocumentationConfig(root=root))

    def test_source_inventory_skips_tracked_worktree_deletions(
        self, tmp_path: Path
    ) -> None:
        present = tmp_path / "cdm" / "present.py"
        present.parent.mkdir()
        present.write_text("class Present:\n    pass\n", encoding="utf-8")
        with patch(
            "tools.build_documentation.subprocess.run",
            side_effect=[
                subprocess.CompletedProcess(
                    [], 0, stdout="cdm/present.py\0cdm/deleted.py\0"
                ),
                subprocess.CompletedProcess([], 0, stdout="[]"),
            ],
        ):
            modules = self.builder(tmp_path).source_modules()
        assert [module.path for module in modules] == [Path("cdm/present.py")]
        assert modules[0].symbols[0].name == "Present"

    def test_source_reference_links_resolve_from_nested_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builder = self.builder(tmp_path)
        monkeypatch.setattr(
            builder,
            "source_modules",
            lambda: [SourceModule(path=Path("cdm/example.py"))],
        )
        reference = builder.reference_pages()[
            tmp_path / "documentation/reference/symbols/composition.md"
        ]
        assert "(../../../cdm/example.py)" in reference

    def test_check_reports_missing_and_stale_pages(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        destination = tmp_path / "page.md"
        with pytest.raises(ValueError, match="stale"):
            builder.write_pages({destination: "content"}, check=True)
        builder.write_pages({destination: "content"}, check=False)
        builder.write_pages({destination: "content"}, check=True)
        with pytest.raises(ValueError, match="stale"):
            builder.write_pages({destination: "changed"}, check=True)

    def test_visuals_include_root_worker_diagram(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        diagrams = tmp_path / "documentation/diagrams"
        diagrams.mkdir(parents=True)
        (diagrams / "context.mmd").write_text("C4Context\n", encoding="utf-8")
        (tmp_path / "worker-architecture.mmd").write_text(
            "C4Container\n", encoding="utf-8"
        )
        page = next(iter(builder.visual_page().values()))
        assert "../diagrams/context.mmd" in page
        assert "../../worker-architecture.mmd" in page
        assert "```mermaid\nC4Container\n```" in page

    def test_wiki_rewrites_docs_and_source_links(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        doc = tmp_path / "documentation/README.md"
        target = tmp_path / "documentation/reference/indexing.md"
        pages = {doc, target}
        assert builder.wiki_link(doc, "reference/indexing.md#aliases", pages) == (
            "reference-indexing#aliases"
        )
        assert builder.wiki_link(doc, "../cdm/store/indexer.py#L10", pages) == (
            "https://github.com/hbeychaner/usa-congress-monitor/"
            "blob/main/cdm/store/indexer.py#L10"
        )
        assert builder.wiki_link(doc, "#local", pages) == "#local"
        assert builder.wiki_link(doc, "https://example.com", pages) == (
            "https://example.com"
        )

    def test_wiki_does_not_ingest_its_own_output(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        docs = tmp_path / "documentation"
        docs.mkdir()
        (docs / "README.md").write_text("# Home\n", encoding="utf-8")
        wiki = docs / "wiki"
        builder.build_wiki(wiki, check=False)
        builder.build_wiki(wiki, check=True)
        assert sorted(path.name for path in wiki.iterdir()) == [
            "Home.md",
            "_Footer.md",
            "_Sidebar.md",
        ]
        with pytest.raises(ValueError, match="overwrite"):
            builder.build_wiki(docs, check=False)

    def test_wiki_publishes_current_reference_not_plans_or_incidents(
        self, tmp_path: Path
    ) -> None:
        docs = tmp_path / "documentation"
        docs.mkdir()
        for name in (
            "README.md",
            "IMPLEMENTATION_PLAN.md",
            "FUTURE_PLANS.md",
            "FAILURE_RECONCILIATION_2026-09-07.md",
        ):
            (docs / name).write_text(f"# {name}\n", encoding="utf-8")
        reference = docs / "reference"
        reference.mkdir()
        (reference / "indexing.md").write_text("# Indexing\n", encoding="utf-8")
        wiki = tmp_path / "published"
        self.builder(tmp_path).build_wiki(wiki, check=False)
        assert {path.name for path in wiki.iterdir()} == {
            "Home.md",
            "reference-indexing.md",
            "_Sidebar.md",
            "_Footer.md",
        }
        assert "IMPLEMENTATION_PLAN" not in (wiki / "_Sidebar.md").read_text()
        assert (docs / "IMPLEMENTATION_PLAN.md").exists()

    def test_wiki_omits_repository_only_history_without_changing_source(
        self, tmp_path: Path
    ) -> None:
        docs = tmp_path / "documentation"
        docs.mkdir()
        source = docs / "README.md"
        content = (
            "# Current behavior\n\n"
            "<!-- wiki:repository-only:start -->\n"
            "## Prior incident\nHistorical detail\n"
            "<!-- wiki:repository-only:end -->\n"
            "## Operations\nCurrent commands\n"
        )
        source.write_text(content, encoding="utf-8")
        wiki = tmp_path / "published"
        builder = self.builder(tmp_path)
        builder.build_wiki(wiki, check=False)
        builder.build_wiki(wiki, check=True)
        published = (wiki / "Home.md").read_text()
        assert "Current behavior" in published and "Current commands" in published
        assert "Prior incident" not in published
        assert "wiki:repository-only" not in published
        assert source.read_text() == content

    @pytest.mark.parametrize(
        "content",
        [
            "<!-- wiki:repository-only:end -->\n",
            "<!-- wiki:repository-only:start -->\n",
            (
                "<!-- wiki:repository-only:start -->\n"
                "<!-- wiki:repository-only:start -->\n"
            ),
        ],
    )
    def test_wiki_rejects_malformed_repository_only_blocks(
        self, tmp_path: Path, content: str
    ) -> None:
        docs = tmp_path / "documentation"
        docs.mkdir()
        (docs / "README.md").write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match="repository-only"):
            self.builder(tmp_path).build_wiki(tmp_path / "published", check=False)

    def test_wiki_only_does_not_invoke_source_or_visual_generation(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "README.md").write_text("# Repository\n")
        docs = tmp_path / "documentation"
        docs.mkdir()
        source = docs / "README.md"
        source.write_text("# First revision\n")
        builder = self.builder(tmp_path)
        output = docs / "wiki"
        with (
            patch.object(
                builder,
                "source_modules",
                side_effect=AssertionError("Node/scientific dependencies must not run"),
            ),
            patch.object(
                builder,
                "visual_page",
                side_effect=AssertionError("Visual regeneration is explicit"),
            ),
        ):
            builder.run(check=False, wiki=output, wiki_only=True)
            builder.run(check=True, wiki=output, wiki_only=True)
            source.write_text("# Updated prose\n")
            with pytest.raises(ValueError, match="stale"):
                builder.run(check=True, wiki=output, wiki_only=True)
            builder.run(check=False, wiki=output, wiki_only=True)
        assert "# Updated prose" in (output / "Home.md").read_text()

    def test_wiki_only_requires_output(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="requires"):
            self.builder(tmp_path).run(check=False, wiki=None, wiki_only=True)

    def test_wiki_only_cli_does_not_claim_source_freshness(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch(
                "sys.argv",
                ["build_documentation.py", "--wiki-only", "--wiki", str(tmp_path)],
            ),
            patch.object(DocumentationBuilder, "run") as run,
        ):
            DocumentationCommand().run()
        run.assert_called_once_with(check=False, wiki=tmp_path, wiki_only=True)
        assert "source/visual freshness not checked" in capsys.readouterr().out

    def test_wiki_only_cli_requires_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch("sys.argv", ["build_documentation.py", "--wiki-only"]),
            pytest.raises(SystemExit) as error,
        ):
            DocumentationCommand().run()
        assert error.value.code == 2
        assert "--wiki-only requires --wiki" in capsys.readouterr().err

    def test_wiki_rewrites_typed_symbol_labels(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        docs = tmp_path / "documentation"
        docs.mkdir()
        (docs / "README.md").write_text(
            "[`load() -> list[str]`](../source.py#L1)\n", encoding="utf-8"
        )
        wiki = docs / "wiki"
        builder.build_wiki(wiki, check=False)
        assert "blob/main/source.py#L1" in (wiki / "Home.md").read_text(
            encoding="utf-8"
        )

    def test_alternate_wiki_output_excludes_default_publication_copy(
        self, tmp_path: Path
    ) -> None:
        builder = self.builder(tmp_path)
        docs = tmp_path / "documentation"
        docs.mkdir()
        (docs / "README.md").write_text("# Home\n", encoding="utf-8")
        builder.build_wiki(docs / "wiki", check=False)
        alternate = tmp_path / "alternate"
        builder.build_wiki(alternate, check=False)
        assert sorted(path.name for path in alternate.iterdir()) == [
            "Home.md",
            "_Footer.md",
            "_Sidebar.md",
        ]

    def test_wiki_rejects_unmanaged_pages(self, tmp_path: Path) -> None:
        builder = self.builder(tmp_path)
        docs = tmp_path / "documentation"
        docs.mkdir()
        (docs / "README.md").write_text("# Home\n", encoding="utf-8")
        wiki = docs / "wiki"
        builder.build_wiki(wiki, check=False)
        (wiki / "old.md").write_text("# Obsolete\n", encoding="utf-8")
        with pytest.raises(ValueError, match="obsolete or unmanaged"):
            builder.build_wiki(wiki, check=False)

    def test_link_validation_checks_files_and_source_line_numbers(
        self, tmp_path: Path
    ) -> None:
        builder = self.builder(tmp_path)
        source = tmp_path / "source.py"
        source.write_text("x = 1\n", encoding="utf-8")
        readme = tmp_path / "README.md"
        readme.write_text("[`list[str]`](source.py#L1)\n", encoding="utf-8")
        builder.validate_links()
        readme.write_text("[`list[str]`](source.py#L2)\n", encoding="utf-8")
        with pytest.raises(ValueError, match="source.py#L2"):
            builder.validate_links()
        readme.write_text("[missing](missing.md)\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing.md"):
            builder.validate_links()
