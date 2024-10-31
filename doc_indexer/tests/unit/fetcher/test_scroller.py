import json
import os
import random
import shutil
import string
from unittest.mock import patch

import pytest
from fetcher.scroller import Scroller
from fetcher.source import DocumentsSource


def get_random_string(length) -> str:
    return "".join(random.choice(string.ascii_lowercase) for i in range(length))


@pytest.fixture
def new_tmp_dir(root_tests_path):
    """Create a new tmp directory and return the path."""
    new_tmp_dir = os.path.join(root_tests_path, "tmp", f"test-{get_random_string(6)}")
    # delete and recreate the directory.
    shutil.rmtree(new_tmp_dir, ignore_errors=True)
    os.makedirs(new_tmp_dir, exist_ok=True)
    # yield the path to the test.
    yield new_tmp_dir
    # remove the directory when the test is completed.
    shutil.rmtree(new_tmp_dir, ignore_errors=True)


@pytest.fixture()
def fixtures_path(root_tests_path) -> str:
    return f"{root_tests_path}/unit/fixtures"


@pytest.fixture()
def mock_os_walk(root_tests_path):
    with open(
        os.path.join(root_tests_path, "unit/fetcher", "sample_os_walk_output.json")
    ) as file:
        data = json.load(file)
    with patch("os.walk") as mock:
        mock.return_value = data
        yield mock


class TestScroller:
    def test_init(self):
        # given
        given_dir_path = "test/dir_path"
        given_output_dir = "test/output_dir"
        given_source = DocumentsSource(
            name="test_scroller", source_type="Github", url="https://test.scroller"
        )

        # when
        scroller = Scroller(given_dir_path, given_output_dir, given_source)

        # then
        # the constructor should have set the member variables.
        assert scroller.dir_path == given_dir_path
        assert scroller.output_dir == given_output_dir
        assert scroller.source == given_source

    def test_save_file(self, new_tmp_dir):
        """Test the _save_file method of the Scroller class."""
        # given
        # create a new file which should be copied by the 'scroller._save_file'.
        given_file_dir = "sample/abc"
        given_file_name = "test_file.md"
        os.makedirs(os.path.join(new_tmp_dir, given_file_dir), exist_ok=True)
        file_path = os.path.join(new_tmp_dir, given_file_dir, given_file_name)
        with open(file_path, "w") as file:
            file.write("Hello, World!")
        # make sure that the file is created and exists.
        assert os.path.exists(file_path)

        # the file should not exist in output directory before method call.
        given_output_dir = os.path.join(new_tmp_dir, "output")
        output_file_path = os.path.join(
            given_output_dir, given_file_dir, given_file_name
        )
        assert not os.path.exists(output_file_path)

        scroller = Scroller(
            dir_path=new_tmp_dir,
            output_dir=given_output_dir,
            source=DocumentsSource(
                name="test_scroller", source_type="Github", url="https://test.scroller"
            ),
        )
        # when
        scroller._save_file(given_file_dir, given_file_name)

        # then
        # the file should be copied to the output directory.
        # the file_dir should be the same.
        assert os.path.exists(output_file_path)

    @pytest.mark.parametrize(
        "given_file_path, given_exclude_files, expected_output, expected_exception",
        [
            # Test case when exclude_files is None: Should raise an exception.
            (
                "test/dir_path/sample1.md",
                None,
                False,
                ValueError("exclude_files is None."),
            ),
            # Test case when file_path is not in exclude_files.
            (
                "test/dir_path/sample1.md",
                [],
                False,
                None,
            ),
            # Test case when file_path is in exclude_files.
            (
                "test/dir_path/sample1.md",
                [
                    "test/dir_path/sample1.md",
                    "test/dir_path/sample2.md",
                ],
                True,
                None,
            ),
            # Test case when file_path matches a pattern in exclude_files.
            (
                "test/dir_path/_sidebar.md",
                [
                    "*/_sidebar.md",
                    "test/dir_path/sample2.md",
                ],
                True,
                None,
            ),
            # Test case when file_path matches a pattern in exclude_files.
            (
                "test/dir_path/_sidebar.md",
                [
                    "test/*",
                ],
                True,
                None,
            ),
        ],
    )
    def test_should_exclude_file(
        self,
        given_file_path: str,
        given_exclude_files: str | None,
        expected_output: bool,
        expected_exception: Exception,
    ):
        # given
        scroller = Scroller(
            dir_path="tmp",
            output_dir="tmp/output",
            source=DocumentsSource(
                name="test_scroller",
                source_type="Github",
                url="https://test.scroller",
                exclude_files=given_exclude_files,
            ),
        )

        # when
        if expected_exception is not None:
            with pytest.raises(Exception) as exc_info:
                scroller._should_exclude_file(given_file_path)
            assert isinstance(exc_info.value, type(expected_exception))
            assert str(exc_info.value) == str(expected_exception)
        else:
            assert scroller._should_exclude_file(given_file_path) == expected_output

    @pytest.mark.parametrize(
        "given_file_path, given_include_files, expected_output, expected_exception",
        [
            # Test case when include_files is None: Should raise an exception.
            (
                "test/dir_path/sample1.md",
                None,
                False,
                ValueError("include_files is None."),
            ),
            # Test case when file_path is not in include_files.
            (
                "test/dir_path/sample1.md",
                [],
                False,
                None,
            ),
            # Test case when file_path is in include_files.
            (
                "test/dir_path/sample1.md",
                [
                    "test/dir_path/sample1.md",
                    "test/dir_path/sample2.md",
                ],
                True,
                None,
            ),
            # Test case when file_path matches a pattern in include_files.
            (
                "test/dir_path/README.md",
                [
                    "*/README.md",
                    "test/dir_path/sample2.md",
                ],
                True,
                None,
            ),
            # Test case when file_path matches a pattern in include_files.
            (
                "test/dir_path/_sidebar.md",
                [
                    "test/*",
                ],
                True,
                None,
            ),
        ],
    )
    def test_should_include_file(
        self,
        given_file_path: str,
        given_include_files: str | None,
        expected_output: bool,
        expected_exception: Exception,
    ):
        # given
        scroller = Scroller(
            dir_path="tmp",
            output_dir="tmp/output",
            source=DocumentsSource(
                name="test_scroller",
                source_type="Github",
                url="https://test.scroller",
                include_files=given_include_files,
            ),
        )

        # when
        if expected_exception is not None:
            with pytest.raises(Exception) as exc_info:
                scroller._should_include_file(given_file_path)
            assert isinstance(exc_info.value, type(expected_exception))
            assert str(exc_info.value) == str(expected_exception)
        else:
            assert scroller._should_include_file(given_file_path) == expected_output

    @pytest.mark.parametrize(
        "given_scroller, expected_files",
        [
            # Test case when include_files and exclude_files are None: should not exclude any file.
            (
                Scroller(
                    dir_path="/kyma-project/kyma-companion/doc_indexer/docs",
                    output_dir="tmp/output",
                    source=DocumentsSource(
                        name="test_scroller",
                        source_type="Github",
                        url="https://test.scroller",
                        include_files=None,
                        exclude_files=None,
                    ),
                ),
                [
                    "double_nested_dirs/_sidebar.md",
                    "double_nested_dirs/test-folder-1/sample-1.md",
                    "double_nested_dirs/test-folder-1/test-folder-2/sample-1.md",
                    "single_doc/sample-1.md",
                    "test_docs/test-folder-2/sample-1.md",
                    "test_docs/test-folder-2/sample-2.md",
                    "test_docs/test-folder-2/sample-3.md",
                    "test_docs/test-folder-1/sample-1.md",
                ],
            ),
            # Test case when include_files is specified
            (
                Scroller(
                    dir_path="/kyma-project/kyma-companion/doc_indexer/docs",
                    output_dir="tmp/output",
                    source=DocumentsSource(
                        name="test_scroller",
                        source_type="Github",
                        url="https://test.scroller",
                        include_files=[
                            "single_doc/sample-1.md",
                            "test_docs/test-folder-2/*",
                        ],
                        exclude_files=None,
                    ),
                ),
                [
                    "single_doc/sample-1.md",
                    "test_docs/test-folder-2/sample-1.md",
                    "test_docs/test-folder-2/sample-2.md",
                    "test_docs/test-folder-2/sample-3.md",
                ],
            ),
            # Test case when exclude_files is specified.
            (
                Scroller(
                    dir_path="/kyma-project/kyma-companion/doc_indexer/docs",
                    output_dir="tmp/output",
                    source=DocumentsSource(
                        name="test_scroller",
                        source_type="Github",
                        url="https://test.scroller",
                        include_files=None,
                        exclude_files=[
                            "single_doc/sample-1.md",
                            "double_nested_dirs/*",
                        ],
                    ),
                ),
                [
                    "test_docs/test-folder-2/sample-1.md",
                    "test_docs/test-folder-2/sample-2.md",
                    "test_docs/test-folder-2/sample-3.md",
                    "test_docs/test-folder-1/sample-1.md",
                ],
            ),
            # Test case when txt and md files are allowed file types.
            (
                Scroller(
                    dir_path="/kyma-project/kyma-companion/doc_indexer/docs",
                    output_dir="tmp/output",
                    source=DocumentsSource(
                        name="test_scroller",
                        source_type="Github",
                        url="https://test.scroller",
                        include_files=["double_nested_dirs/test-folder-1/*"],
                        exclude_files=None,
                        filter_file_types=["txt", "md"],
                    ),
                ),
                [
                    "double_nested_dirs/test-folder-1/sample-1.md",
                    "double_nested_dirs/test-folder-1/text-file-1.txt",
                    "double_nested_dirs/test-folder-1/test-folder-2/sample-1.md",
                ],
            ),
        ],
    )
    def test_scroll(self, mock_os_walk, given_scroller: Scroller, expected_files: list):
        # given

        output_files = []

        def mock_save_file(file_dir: str, file_name: str):
            output_files.append(os.path.join(file_dir, file_name))

        given_scroller._save_file = mock_save_file

        # when
        given_scroller.scroll()

        # then
        assert len(output_files) == len(expected_files)
        assert output_files == expected_files
