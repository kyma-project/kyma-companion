import os
from json import JSONDecodeError
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from utils.settings import (
    RAG_NUM_QUERIES,
    RAG_TOP_K,
    RETRIEVAL_MODE,
    RetrievalMode,
    load_env_from_json,
)


@pytest.mark.parametrize(
    "json_content, expected_env_variables",
    [
        (
            # Given: Malformed Json
            # Expected: Exception
            """
            { "VARIABLE_NAME": "value",
            """,
            None,
        ),
        (
            # Given: Valid JSON with two variables
            # Expected: Environment variables are set correctly
            """
            {
                "VARIABLE_NAME": "value",
                "VARIABLE_NAME2": "value2"
            }
            """,
            {"VARIABLE_NAME": "value", "VARIABLE_NAME2": "value2"},
        ),
        (
            # Given: Valid JSON with two variables and a model configuration
            # Expected: Environment variables are set correctly
            """
            {
                "VARIABLE_NAME": "value",
                "VARIABLE_NAME2": "value2",
                "models": [
                    {
                        "name": "single_model",
                        "deployment_id": "single_dep",
                        "temperature": 1
                    }
                ]
            }
            """,
            {"VARIABLE_NAME": "value", "VARIABLE_NAME2": "value2"},
        ),
    ],
)
def test_load_env_from_json(json_content, expected_env_variables):
    with (
        patch.dict(os.environ, {"CONFIG_PATH": "/mocked/config.json"}),
        patch("os.path.exists", return_value=True),
        patch.object(Path, "open", mock_open(read_data=json_content)),
        patch.object(Path, "is_file", return_value=bool(json_content)),
    ):
        if expected_env_variables is None:
            # Then: Expect an exception for malformed JSON
            with pytest.raises(JSONDecodeError):
                load_env_from_json()
        else:
            # When: loading the environment variables from the config.json file
            load_env_from_json()

            # Then: the environment variables are set as expected
            for key, value in expected_env_variables.items():
                assert os.getenv(key) == value

            # Clean up the environment variables
            for key in expected_env_variables:
                os.environ.pop(key)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("reranker", RetrievalMode.RERANKER),
        ("vector", RetrievalMode.VECTOR),
        ("fusion", RetrievalMode.FUSION),
    ],
)
def test_retrieval_mode_accepts_valid_values(value, expected):
    # The RETRIEVAL_MODE setting is cast through RetrievalMode; valid values map to enum members.
    assert RetrievalMode(value) == expected


def test_retrieval_mode_rejects_invalid_value():
    # An unknown mode raises at config-cast time, surfacing a clear error before startup.
    with pytest.raises(ValueError):
        RetrievalMode("bogus")


_EXPECTED_RAG_TOP_K = 5
_EXPECTED_RAG_NUM_QUERIES = 4


def test_retrieval_mode_defaults_to_reranker():
    # With no RETRIEVAL_MODE override, the exported constant is reranker.
    assert RETRIEVAL_MODE == RetrievalMode.RERANKER


def test_rag_pipeline_parameters_default():
    # Verify the exported constants match the intended defaults.
    assert RAG_TOP_K == _EXPECTED_RAG_TOP_K
    assert RAG_NUM_QUERIES == _EXPECTED_RAG_NUM_QUERIES
