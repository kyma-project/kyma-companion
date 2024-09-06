from unittest.mock import patch

import pytest

from services.k8s import DataSanitizer, K8sClient


def sample_k8s_secret():
    return {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "data": {
            "config": "this is a test config",
        },
    }


def sample_k8s_sanitized_secret():
    return {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "data": {},
    }


def sample_k8s_pod():
    return {
        "kind": "Pod",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "spec": {
            "containers": [
                {
                    "name": "my-container",
                    "image": "my-image",
                },
            ],
        },
    }


class TestK8sClient:
    @pytest.mark.parametrize(
        "test_description, given_ca_data, expected_result",
        [
            (
                "should be able to decode base64 encoded ca data",
                "dGhpcyBpcyBhIHRlc3QgY2EgZGF0YQ==",
                b"this is a test ca data",
            ),
        ],
    )
    @patch("services.k8s.K8sClient.__init__", return_value=None)
    def test_get_decoded_ca_data(
        self, mock_init, test_description, given_ca_data, expected_result
    ):
        # given
        k8s_client = K8sClient()
        k8s_client.certificate_authority_data = given_ca_data

        # when
        decoded_ca_data = k8s_client._get_decoded_ca_data()

        # then
        assert isinstance(decoded_ca_data, bytes)
        assert decoded_ca_data == expected_result

    @pytest.mark.parametrize(
        "test_description, given_user_token, expected_result",
        [
            (
                "should return correct headers",
                "sample-token",
                {
                    "Authorization": "Bearer sample-token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            ),
        ],
    )
    @patch("services.k8s.K8sClient.__init__", return_value=None)
    def test_get_auth_headers(
        self, mock_init, test_description, given_user_token, expected_result
    ):
        # given
        k8s_client = K8sClient()
        k8s_client.user_token = given_user_token

        # when
        result = k8s_client._get_auth_headers()

        # then
        assert result == expected_result


class TestDataSanitizer:
    @pytest.mark.parametrize(
        "test_description, given_data, expected_data, expected_error",
        [
            (
                "should return error if object type is not list or dict",
                "It is a string",
                "",
                ValueError("Data must be a list or a dictionary."),
            ),
            (
                "should be able to sanitize a dict object and should remove data from secret",
                sample_k8s_secret(),
                sample_k8s_sanitized_secret(),
                None,
            ),
            (
                "should be able to sanitize a list object and should remove data from secret",
                [
                    sample_k8s_secret(),
                    sample_k8s_secret(),
                ],
                [
                    sample_k8s_sanitized_secret(),  # it should remove data from secret.
                    sample_k8s_sanitized_secret(),
                ],
                None,
            ),
            (
                "should be able to sanitize a Pod resource",
                sample_k8s_pod(),
                sample_k8s_pod(),  # for pods, it is not removing anything.
                None,
            ),
        ],
    )
    def test_sanitize(
        self, test_description, given_data, expected_data, expected_error
    ):
        # error cases:
        if expected_error is not None:
            err_msg = str(expected_error)
            with pytest.raises(ValueError, match=err_msg):
                DataSanitizer.sanitize(given_data)
            # exit test
            return

        # normal cases:
        got_data = DataSanitizer.sanitize(given_data)
        assert got_data == expected_data
