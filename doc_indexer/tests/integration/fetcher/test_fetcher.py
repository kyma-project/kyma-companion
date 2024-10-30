import os.path
import random
import shutil
import string
from pathlib import Path

import pytest
from fetcher.fetcher import DocumentsFetcher

current_dir = Path(__file__).parent


def get_random_string(length) -> str:
    return "".join(random.choice(string.ascii_lowercase) for i in range(length))


@pytest.fixture
def new_tmp_dir():
    """Create a new tmp directory and return the path."""
    new_tmp_dir = os.path.join(current_dir, "tmp", f"test-{get_random_string(6)}")
    # delete and recreate the directory.
    shutil.rmtree(new_tmp_dir, ignore_errors=True)
    os.makedirs(new_tmp_dir, exist_ok=True)
    # yield the path to the test.
    yield new_tmp_dir
    # remove the directory when the test is completed.
    shutil.rmtree(new_tmp_dir, ignore_errors=True)


def test_fetcher(new_tmp_dir):
    # given
    given_source_file = os.path.join(current_dir, "test_docs_sources.json")
    given_output_dir = os.path.join(new_tmp_dir, "data/output")
    given_tmp_dir = os.path.join(new_tmp_dir, "data/tmp")

    # delete the directories if they exist.
    shutil.rmtree(given_output_dir, ignore_errors=True)
    shutil.rmtree(given_tmp_dir, ignore_errors=True)

    # create an instance of the fetcher.
    fetcher = DocumentsFetcher(
        source_file=given_source_file,
        output_dir=given_output_dir,
        tmp_dir=given_tmp_dir,
    )

    # when: run the fetcher.
    fetcher.run()

    # then
    # should have deleted the tmp directory.
    assert not os.path.exists(given_tmp_dir)
    # should have created the output directory.
    assert os.path.exists(given_output_dir)

    # should have saved the files in the output directory.
    # all the saved files should be markdown files.
    file_count = 0
    for _, _, files in os.walk(given_output_dir):
        file_count += len(files)
        for file_name in files:
            assert file_name.endswith(".md")
    # should have saved at least one file.
    assert file_count > 0
