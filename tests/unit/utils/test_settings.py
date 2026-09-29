import os
from json import JSONDecodeError
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from decouple import config

from utils.settings import (
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


def test_retrieval_mode_defaults_to_fusion(monkeypatch):
    # With no RETRIEVAL_MODE configured, the setting resolves to fusion.
    monkeypatch.delenv("RETRIEVAL_MODE", raising=False)
    assert config("RETRIEVAL_MODE", default=RetrievalMode.FUSION, cast=RetrievalMode) == RetrievalMode.FUSION


def test_rag_pipeline_parameters_default(monkeypatch):
    # With nothing configured, the RAG pipeline keeps its previous hard-coded values.
    monkeypatch.delenv("RAG_TOP_K", raising=False)
    monkeypatch.delenv("RAG_NUM_QUERIES", raising=False)
    expected_top_k = 5
    expected_num_queries = 4
    assert config("RAG_TOP_K", default=expected_top_k, cast=int) == expected_top_k
    assert config("RAG_NUM_QUERIES", default=expected_num_queries, cast=int) == expected_num_queries
