from unittest.mock import patch

import pytest

from services.k8s import K8sClient


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

    @patch("services.k8s.K8sClient.__init__", return_value=None)
    def test_model_dump(self, mock_init):
        k8s_client = K8sClient()
        assert k8s_client.model_dump() is None

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
