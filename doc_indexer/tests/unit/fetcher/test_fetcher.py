import os
from unittest.mock import Mock, patch

import pytest
from fetcher.fetcher import DocumentsFetcher

pytestmark = pytest.mark.unit


@pytest.fixture
def docs_sources_file_path(root_tests_path):
    """Return the path to the documents sources file."""
    return os.path.join(root_tests_path, "..", "docs_sources.json")


class TestDocumentsFetcher:
    def test_init(self, docs_sources_file_path):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"

        # when
        with (
            patch("fetcher.fetcher._empty_dir") as empty_dir_mock,
            patch("os.makedirs") as makedirs_mock,
        ):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )

        # then
        assert fetcher.output_dir == given_output_dir
        assert fetcher.tmp_dir == given_tmp_dir
        assert len(fetcher.sources) > 0

        makedirs_mock.assert_any_call(given_output_dir, exist_ok=True)
        makedirs_mock.assert_any_call(given_tmp_dir, exist_ok=True)

        empty_dir_mock.assert_any_call(given_output_dir)
        empty_dir_mock.assert_any_call(given_tmp_dir)

    def test_clean(self, docs_sources_file_path):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"
        with patch("fetcher.fetcher._empty_dir"), patch("os.makedirs"):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )

        # when
        with patch("fetcher.fetcher._empty_dir") as empty_dir_mock:
            fetcher.clean()

        # then
        empty_dir_mock.assert_called_with(given_tmp_dir)

    def test_run(self, docs_sources_file_path):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"
        with patch("fetcher.fetcher._empty_dir"), patch("os.makedirs"):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )
        fetcher.fetch_documents = Mock()
        fetcher.clean = Mock()

        # when
        fetcher.run()

        # then
        assert len(fetcher.sources) > 0
        assert fetcher.fetch_documents.call_count == len(fetcher.sources)
        fetcher.clean.assert_called_once()

    def test_fetch_documents(self, docs_sources_file_path):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"
        with patch("fetcher.fetcher._empty_dir"), patch("os.makedirs"):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )
            assert len(fetcher.sources) > 0

        # when
        with (
            patch("shutil.rmtree") as rmtree_mock,
            patch("os.makedirs") as makedirs_mock,
            patch("fetcher.fetcher.download_repo") as download_repo_mock,
            patch("fetcher.fetcher.Scroller") as scroller_mock,
        ):
            fetcher.fetch_documents(fetcher.sources[0])

        # then
        download_repo_mock.assert_called_once_with(fetcher.sources[0].url, given_tmp_dir)
        makedirs_mock.assert_called_once_with(os.path.join(given_output_dir, fetcher.sources[0].name), exist_ok=True)
        assert scroller_mock.call_count == 1
        scroller_mock.return_value.scroll.assert_called_once()
        rmtree_mock.assert_called_once()

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "invalid/name",
            "invalid\\name",
            "invalid name",
            "invalid.name",
            "invalid@name",
            "invalid#name",
            "invalid$name",
            "../traversal",
            "name with spaces",
            "special!chars",
            "semi;colon",
            "",
        ],
    )
    def test_fetch_documents_various_invalid_source_names(self, docs_sources_file_path, invalid_name):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"
        with patch("fetcher.fetcher._empty_dir"), patch("os.makedirs"):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )

        invalid_source = Mock()
        invalid_source.name = invalid_name
        invalid_source.source_type = fetcher.sources[0].source_type
        invalid_source.url = "https://example.com/repo.git"

        with (
            patch("fetcher.fetcher.download_repo") as download_repo_mock,
            patch("fetcher.fetcher.Scroller") as scroller_mock,
            patch("os.makedirs") as makedirs_mock,
        ):
            with pytest.raises(ValueError, match=r"Invalid source name"):
                fetcher.fetch_documents(invalid_source)

            download_repo_mock.assert_not_called()
            scroller_mock.assert_not_called()
            makedirs_mock.assert_not_called()

    @pytest.mark.parametrize(
        "valid_name",
        [
            "valid-name",
            "valid_name",
            "ValidName",
            "validname123",
            "UPPERCASE",
            "a",
            "test-repo_v2",
        ],
    )
    def test_fetch_documents_valid_source_names(self, docs_sources_file_path, valid_name):
        # given
        given_output_dir = "test/output_dir"
        given_tmp_dir = "test/tmp_dir"
        with patch("fetcher.fetcher._empty_dir"), patch("os.makedirs"):
            fetcher = DocumentsFetcher(
                source_file=docs_sources_file_path,
                output_dir=given_output_dir,
                tmp_dir=given_tmp_dir,
            )

        valid_source = Mock()
        valid_source.name = valid_name
        valid_source.source_type = fetcher.sources[0].source_type
        valid_source.url = "https://example.com/repo.git"

        with (
            patch("shutil.rmtree"),
            patch("os.makedirs"),
            patch("fetcher.fetcher.download_repo") as download_repo_mock,
            patch("fetcher.fetcher.Scroller") as scroller_mock,
        ):
            fetcher.fetch_documents(valid_source)

        download_repo_mock.assert_called_once_with(valid_source.url, given_tmp_dir)
        scroller_mock.assert_called_once()
        scroller_mock.return_value.scroll.assert_called_once()
