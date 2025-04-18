from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from services.k8s import AuthType, K8sAuthHeaders, K8sClient


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


class TestK8sAuthHeaders:
    @pytest.mark.parametrize(
        "given_ca_data, expected_result",
        [
            (
                # "should be able to decode base64 encoded ca data",
                "dGhpcyBpcyBhIHRlc3QgY2EgZGF0YQ==",
                b"this is a test ca data",
            ),
        ],
    )
    def test_get_decoded_certificate_authority_data(
        self, given_ca_data, expected_result
    ):
        # given
        k8s_headers = K8sAuthHeaders(
            x_cluster_url="https://api.example.com",
            x_cluster_certificate_authority_data=given_ca_data,
            x_k8s_authorization=None,
            x_client_certificate_data=None,
            x_client_key_data=None,
        )

        # when
        decoded_ca_data = k8s_headers.get_decoded_certificate_authority_data()

        # then
        assert isinstance(decoded_ca_data, bytes)
        assert decoded_ca_data == expected_result

    @pytest.mark.parametrize(
        "given_client_cert_data, expected_result, expected_error",
        [
            (
                # "should decode base64 encoded client certificate data",
                "dGhpcyBpcyBhIHRlc3QgY2VydCBkYXRh",
                b"this is a test cert data",
                None,
            ),
            (
                # "should return None for empty client certificate data",
                None,
                "",
                ValueError,
            ),
        ],
    )
    def test_get_decoded_client_certificate_data(
        self, given_client_cert_data, expected_result, expected_error
    ):
        # given
        k8s_headers = K8sAuthHeaders(
            x_cluster_url="https://api.example.com",
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization=None,
            x_client_certificate_data=given_client_cert_data,
            x_client_key_data=None,
        )

        # when/then
        if expected_error:
            with pytest.raises(expected_error):
                k8s_headers.get_decoded_client_certificate_data()
        else:
            decoded_cert_data = k8s_headers.get_decoded_client_certificate_data()
            assert decoded_cert_data == expected_result

    @pytest.mark.parametrize(
        "given_client_key_data, expected_result, expected_exception",
        [
            (
                "dGhpcyBpcyBhIHRlc3Qga2V5IGRhdGE=",
                b"this is a test key data",
                None,
            ),
            (
                None,
                None,
                ValueError,
            ),
        ],
    )
    def test_get_decoded_client_key_data(
        self, given_client_key_data, expected_result, expected_exception
    ):
        # given
        k8s_headers = K8sAuthHeaders(
            x_cluster_url="https://api.example.com",
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization=None,
            x_client_certificate_data=None,
            x_client_key_data=given_client_key_data,
        )

        # when/then
        if expected_exception:
            with pytest.raises(expected_exception):
                k8s_headers.get_decoded_client_key_data()
        else:
            decoded_key_data = k8s_headers.get_decoded_client_key_data()
            assert decoded_key_data == expected_result

    @pytest.mark.parametrize(
        "x_k8s_authorization, x_client_certificate_data, x_client_key_data, expected_auth_type",
        [
            ("sample-token", None, None, AuthType.TOKEN),
            (None, "sample-cert", "sample-key", AuthType.CLIENT_CERTIFICATE),
            (None, None, None, AuthType.UNKNOWN),
        ],
    )
    def test_get_auth_type(
        self,
        x_k8s_authorization,
        x_client_certificate_data,
        x_client_key_data,
        expected_auth_type,
    ):
        # given
        k8s_headers = K8sAuthHeaders(
            x_cluster_url="https://api.example.com",
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization=x_k8s_authorization,
            x_client_certificate_data=x_client_certificate_data,
            x_client_key_data=x_client_key_data,
        )

        # when/then
        assert k8s_headers.get_auth_type() == expected_auth_type

    @pytest.mark.parametrize(
        "k8s_headers, expected_error_msg",
        [
            (
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data="abc",
                ),
                None,
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                ),
                None,
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data="abc",
                    x_client_key_data="abc",
                ),
                None,
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data="abc",
                ),
                "x-cluster-url header is required.",
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data="abc",
                ),
                "x-cluster-certificate-authority-data header is required.",
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data="abc",
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
            (
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data="abc",
                    x_client_key_data=None,
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
        ],
    )
    def test_validate_headers(self, k8s_headers, expected_error_msg):
        # given
        if expected_error_msg is not None:
            with pytest.raises(ValueError) as e:
                k8s_headers.validate_headers()
            assert expected_error_msg in str(e.value)
        else:
            assert k8s_headers.validate_headers() is None


class TestK8sClient:
    @pytest.fixture
    def k8s_client(self):
        with patch("services.k8s.K8sClient.__init__", return_value=None):
            k8s_client = K8sClient()
            return k8s_client

    def test_model_dump(self, k8s_client):
        assert k8s_client.model_dump() is None

    @pytest.mark.parametrize(
        "test_description, k8s_headers, expected_result",
        [
            (
                "should return correct headers when user token is set",
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="sample-token",
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                ),
                {
                    "Authorization": "Bearer sample-token",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            ),
            (
                "should return correct headers when user token is not set",
                K8sAuthHeaders(
                    x_cluster_url="abc",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                ),
                {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            ),
        ],
    )
    def test_get_auth_headers(
        self, k8s_client, test_description, k8s_headers, expected_result
    ):
        # given
        k8s_client.k8s_auth_headers = k8s_headers

        # when
        result = k8s_client._get_auth_headers()

        # then
        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data, expected_result",
        [
            (
                "should sanitize data when sanitizer is set",
                Mock(sanitize=Mock(return_value={"sanitized": "data"})),
                {"raw": "data"},
                {"sanitized": "data"},
            ),
            (
                "should return raw data when sanitizer is not set",
                None,
                {"raw": "data"},
                {"raw": "data"},
            ),
        ],
    )
    def test_get_api_request(
        self, k8s_client, test_description, data_sanitizer, raw_data, expected_result
    ):
        # given
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url="abc",
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.ca_temp_filename = "test-ca-file"
        k8s_client.data_sanitizer = data_sanitizer

        response_mock = Mock(
            status_code=HTTPStatus.OK, json=Mock(return_value=raw_data)
        )

        # when
        with patch("requests.get", return_value=response_mock):
            result = k8s_client.execute_get_api_request("/test/uri")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data, expected_result",
        [
            (
                "should sanitize data when sanitizer is set",
                Mock(sanitize=Mock(return_value=[{"sanitized": "data"}])),
                [{"raw": "data"}],
                [{"sanitized": "data"}],
            ),
            (
                "should return raw data when sanitizer is not set",
                None,
                [{"raw": "data"}],
                [{"raw": "data"}],
            ),
        ],
    )
    def test_list_resources(
        self, k8s_client, test_description, data_sanitizer, raw_data, expected_result
    ):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_resource = Mock()
        mock_item = Mock()
        mock_item.to_dict.return_value = raw_data[0]
        mock_resource.items = [mock_item]

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value = mock_resource
        k8s_client.dynamic_client = mock_dynamic_client

        # when
        result = k8s_client.list_resources("v1", "Pod", "default")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data, expected_result",
        [
            (
                "should sanitize data when sanitizer is set",
                Mock(sanitize=Mock(return_value={"sanitized": "data"})),
                {"raw": "data"},
                {"sanitized": "data"},
            ),
            (
                "should return raw data when sanitizer is not set",
                None,
                {"raw": "data"},
                {"raw": "data"},
            ),
        ],
    )
    def test_get_resource(
        self, k8s_client, test_description, data_sanitizer, raw_data, expected_result
    ):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = (
            raw_data
        )
        k8s_client.dynamic_client = mock_dynamic_client

        # when
        result = k8s_client.get_resource("v1", "Pod", "test-pod", "default")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data, raw_events, expected_result",
        [
            (
                "should sanitize data when sanitizer is set",
                Mock(sanitize=Mock(return_value={"sanitized": "data", "events": []})),
                {"raw": "data"},
                [{"involvedObject": "test", "event": "data"}],
                {"sanitized": "data", "events": []},
            ),
            (
                "should return raw data when sanitizer is not set",
                None,
                {"raw": "data"},
                [{"involvedObject": "test", "event": "data"}],
                {"raw": "data", "events": [{"event": "data"}]},
            ),
        ],
    )
    def test_describe_resource(
        self,
        k8s_client,
        test_description,
        data_sanitizer,
        raw_data,
        raw_events,
        expected_result,
    ):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        # Mock get_resource and list_k8s_events_for_resource
        with (
            patch.object(k8s_client, "get_resource") as mock_get_resource,
            patch.object(
                k8s_client, "list_k8s_events_for_resource"
            ) as mock_list_events,
        ):
            mock_get_resource.return_value = raw_data
            mock_list_events.return_value = raw_events

            # when
            result = k8s_client.describe_resource("v1", "Pod", "test-pod", "default")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once()
        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data, expected_result",
        [
            (
                "should sanitize data when sanitizer is set",
                Mock(sanitize=Mock(return_value=[{"sanitized": "event"}])),
                [{"raw": "event"}],
                [{"sanitized": "event"}],
            ),
            (
                "should return raw data when sanitizer is not set",
                None,
                [{"raw": "event"}],
                [{"raw": "event"}],
            ),
        ],
    )
    def test_list_k8s_events(
        self, k8s_client, test_description, data_sanitizer, raw_data, expected_result
    ):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_resource = Mock()
        mock_item = Mock()
        mock_item.to_dict.return_value = raw_data[0]
        mock_resource.items = [mock_item]

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value = mock_resource
        k8s_client.dynamic_client = mock_dynamic_client

        # when
        result = k8s_client.list_k8s_events("default")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result
