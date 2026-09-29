import json
import os.path
import random
import re
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
    # clean() empties (not removes) tmp so the non-root container user can reuse it.
    assert os.path.isdir(given_tmp_dir)
    assert os.listdir(given_tmp_dir) == []
    assert os.path.exists(given_output_dir)

    # should have saved the files in the output directory.
    # all the saved files should be markdown files, plus manifest.json at the root.
    file_count = 0
    for root, _, files in os.walk(given_output_dir):
        for file_name in files:
            if root == given_output_dir and file_name == "manifest.json":
                continue
            file_count += 1
            assert file_name.endswith(".md")
    # should have saved at least one file.
    assert file_count > 0

    # manifest.json should record every source with repo_url, a real 40-char commit sha, and fetched_at.
    with open(os.path.join(given_output_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert set(manifest) == {"eventing-manager", "nats-manager"}
    for name, entry in manifest.items():
        assert entry["repo_url"] == f"https://github.com/kyma-project/{name}"
        assert re.fullmatch(r"[0-9a-f]{40}", entry["commit"]), entry
        assert entry["fetched_at"]
