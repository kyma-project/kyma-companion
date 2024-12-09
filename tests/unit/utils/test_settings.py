# import os
# from json import JSONDecodeError
# from pathlib import Path
# from unittest.mock import mock_open, patch
#
# import pytest
#
# from utils.settings import load_env_from_json
#
#
# @pytest.mark.parametrize(
#     "json_content, expected_env_variables",
#     [
#         (
#             # Given: Malformed Json
#             # Expected: Exception
#             """
#             { "VARIABLE_NAME": "value",
#             """,
#             None,
#         ),
#         (
#             # Given: Valid JSON with two variables
#             # Expected: Environment variables are set correctly
#             """
#             {
#                 "VARIABLE_NAME": "value",
#                 "VARIABLE_NAME2": "value2"
#             }
#             """,
#             {"VARIABLE_NAME": "value", "VARIABLE_NAME2": "value2"},
#         ),
#         (
#             # Given: Valid JSON with two variables and a model configuration
#             # Expected: Environment variables are set correctly
#             """
#             {
#                 "VARIABLE_NAME": "value",
#                 "VARIABLE_NAME2": "value2",
#                 "models": [
#                     {
#                         "name": "single_model",
#                         "deployment_id": "single_dep",
#                         "temperature": 1
#                     }
#                 ]
#             }
#             """,
#             {"VARIABLE_NAME": "value", "VARIABLE_NAME2": "value2"},
#         ),
#     ],
# )
# def test_load_env_from_json(json_content, expected_env_variables):
#     with patch.dict(os.environ, {"AICORE_HOME": "/mocked/config.json"}), patch(
#         "os.path.exists", return_value=True
#     ), patch.object(Path, "open", mock_open(read_data=json_content)), patch.object(
#         Path, "is_file", return_value=bool(json_content)
#     ):
#
#         if expected_env_variables is None:
#             # Then: Expect an exception for malformed JSON
#             with pytest.raises(JSONDecodeError):
#                 load_env_from_json()
#         else:
#             # When: loading the environment variables from the config.json file
#             load_env_from_json()
#
#             # Then: the environment variables are set as expected
#             for key, value in expected_env_variables.items():
#                 assert os.getenv(key) == value
#
#             # Clean up the environment variables
#             for key in expected_env_variables:
#                 os.environ.pop(key)
