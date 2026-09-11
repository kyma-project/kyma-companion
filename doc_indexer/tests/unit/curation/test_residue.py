"""Unit tests for curation.residue."""

import os

import pytest
from curation.residue import _EXCERPT_TOKEN_LIMIT, find_residue

pytestmark = pytest.mark.unit

_THREE_FILES = 3
_TWO_RESULTS = 2


@pytest.fixture
def docs_path(tmp_path):
    """Return a temporary docs_path root directory."""
    return str(tmp_path / "data")


def _write_md(base: str, rel_path: str, content: str) -> str:
    """Write a markdown file under *base/rel_path* and return its abs path."""
    abs_path = os.path.join(base, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return abs_path


class TestMissingDocsPath:
    def test_nonexistent_docs_path_returns_empty(self, tmp_path):
        result = find_residue(str(tmp_path / "nonexistent"), [])
        assert result == []


class TestNewRepo:
    def test_file_in_unknown_module_is_residue_new_repo(self, docs_path):
        _write_md(docs_path, "unknown-module/docs/file.md", "# Hello\nContent")
        sources: list[dict] = []  # no entries -> all modules are "new"

        results = find_residue(docs_path, sources)

        assert len(results) == 1
        assert results[0].repo == "unknown-module"
        assert results[0].residue_reason == "new_repo"

    def test_new_repo_with_multiple_files(self, docs_path):
        for i in range(_THREE_FILES):
            _write_md(docs_path, f"new-repo/docs/file{i}.md", f"# File {i}")

        results = find_residue(docs_path, [])

        assert len(results) == _THREE_FILES
        assert all(r.residue_reason == "new_repo" for r in results)


class TestIncludePatterns:
    def test_matching_file_is_not_residue(self, docs_path):
        _write_md(docs_path, "mymodule/docs/user/guide.md", "# Guide")
        sources = [{"name": "mymodule", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert results == []

    def test_non_matching_file_is_residue(self, docs_path):
        _write_md(docs_path, "mymodule/docs/contributor/setup.md", "# Setup")
        sources = [{"name": "mymodule", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert len(results) == 1
        assert results[0].path == "docs/contributor/setup.md"
        assert results[0].residue_reason == "not_in_include_patterns"

    def test_readme_pattern_matches_readme(self, docs_path):
        _write_md(docs_path, "mymodule/README.md", "# README\nContent")
        sources = [{"name": "mymodule", "include_files": ["README.md", "docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert results == []

    def test_mixed_included_and_residue(self, docs_path):
        _write_md(docs_path, "mymodule/docs/user/page.md", "# Page")
        _write_md(docs_path, "mymodule/docs/internal/adr.md", "# ADR")
        sources = [{"name": "mymodule", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert len(results) == 1
        assert results[0].path == "docs/internal/adr.md"

    def test_nested_path_matches_wildcard_pattern(self, docs_path):
        """A file nested under a wildcard pattern dir should not be residue."""
        _write_md(docs_path, "mymodule/docs/user/sub/nested.md", "# Nested")
        sources = [{"name": "mymodule", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert results == []

    def test_no_include_files_means_everything_is_residue(self, docs_path):
        _write_md(docs_path, "mymodule/docs/user/page.md", "# Page")
        sources = [{"name": "mymodule", "include_files": []}]

        results = find_residue(docs_path, sources)

        assert len(results) == 1


class TestCandidateFields:
    def test_h1_extracted(self, docs_path):
        content = "# My Heading\n\nSome content here."
        _write_md(docs_path, "mymodule/docs/file.md", content)
        sources = [{"name": "mymodule", "include_files": []}]

        results = find_residue(docs_path, sources)

        assert results[0].h1 == "My Heading"

    def test_h1_none_when_missing(self, docs_path):
        _write_md(docs_path, "mymodule/docs/file.md", "No heading here.\nJust content.")
        sources = [{"name": "mymodule", "include_files": []}]

        results = find_residue(docs_path, sources)

        assert results[0].h1 is None

    def test_content_hash_is_sha256(self, docs_path):
        import hashlib

        content = "# Doc\nSome text."
        _write_md(docs_path, "mymodule/docs/file.md", content)
        sources = [{"name": "mymodule", "include_files": []}]

        results = find_residue(docs_path, sources)

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert results[0].content_hash == expected_hash

    def test_excerpt_truncated_for_long_content(self, docs_path):
        # Generate content much longer than 600 tokens
        long_content = "# Heading\n" + ("word " * 2000)
        _write_md(docs_path, "mymodule/docs/file.md", long_content)
        sources = [{"name": "mymodule", "include_files": []}]

        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        results = find_residue(docs_path, sources)

        token_count = len(enc.encode(results[0].excerpt))
        assert token_count <= _EXCERPT_TOKEN_LIMIT

    def test_repo_and_path_fields(self, docs_path):
        _write_md(docs_path, "eventing-manager/docs/internal/note.md", "# Note")
        sources = [{"name": "eventing-manager", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        assert results[0].repo == "eventing-manager"
        assert results[0].path == "docs/internal/note.md"

    def test_non_md_files_ignored(self, docs_path):
        _write_md(docs_path, "mymodule/docs/file.md", "# MD File")
        txt_path = os.path.join(docs_path, "mymodule", "docs", "file.txt")
        with open(txt_path, "w") as f:
            f.write("text file content")
        sources = [{"name": "mymodule", "include_files": []}]

        results = find_residue(docs_path, sources)

        # Only the .md file should appear
        assert len(results) == 1
        assert results[0].path == "docs/file.md"


class TestMultipleModules:
    def test_multiple_modules_mixed(self, docs_path):
        # module-a: known, one file in pattern, one outside
        _write_md(docs_path, "module-a/docs/user/page.md", "# Page")
        _write_md(docs_path, "module-a/docs/dev/setup.md", "# Setup")
        # module-b: not in sources
        _write_md(docs_path, "module-b/README.md", "# B Readme")

        sources = [{"name": "module-a", "include_files": ["docs/user/*"]}]

        results = find_residue(docs_path, sources)

        repos = {r.repo for r in results}
        assert repos == {"module-a", "module-b"}
        assert len(results) == _TWO_RESULTS

        module_a_result = next(r for r in results if r.repo == "module-a")
        assert module_a_result.residue_reason == "not_in_include_patterns"

        module_b_result = next(r for r in results if r.repo == "module-b")
        assert module_b_result.residue_reason == "new_repo"
