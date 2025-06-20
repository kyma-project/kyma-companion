from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from agents.common.constants import K8S_API_PAGINATION_MAX_PAGE
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
        "description, k8s_headers, expected_error_msg",
        [
            (
                "Valid headers with token",
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
                "Valid headers with client certificate and x_k8s_authorization",
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
                "Valid headers with client certificate and x_client_key_data",
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
                "missing x-cluster-url",
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
                "missing x-cluster-certificate-authority-data",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data="abc",
                ),
                "x-cluster-certificate-authority-data header is required.",
            ),
            (
                "missing required headers",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data=None,
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
            (
                "missing x_client_certificate_data header",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data=None,
                    x_client_key_data="abc",
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
            (
                "missing x_client_key_data header",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization=None,
                    x_client_certificate_data="abc",
                    x_client_key_data=None,
                ),
                "Either x-k8s-authorization header or "
                + "x-client-certificate-data and x-client-key-data headers are required.",
            ),
            (
                "all domains allowed for x_cluster_url",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data=None,
                    allowed_domains=[],  # No domains specified, should allow all
                ),
                None,
            ),
            (
                "allowed x_cluster_url domain",
                K8sAuthHeaders(
                    x_cluster_url="https://api.example.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data=None,
                    allowed_domains=["example.com"],
                ),
                None,
            ),
            (
                "not allowed x_cluster_url domain",
                K8sAuthHeaders(
                    x_cluster_url="https://api.custom.com",
                    x_cluster_certificate_authority_data="abc",
                    x_k8s_authorization="abc",
                    x_client_certificate_data="abc",
                    x_client_key_data=None,
                    allowed_domains=["example.com"],
                ),
                "Cluster URL https://api.custom.com is not allowed.",
            ),
        ],
    )
    def test_validate_headers(
        self, description: str, k8s_headers: K8sAuthHeaders, expected_error_msg: str
    ):
        # given
        if expected_error_msg is not None:
            with pytest.raises(ValueError) as e:
                k8s_headers.validate_headers()
            assert expected_error_msg in str(e.value), description
        else:
            assert k8s_headers.validate_headers() is None, description

    @pytest.mark.parametrize(
        "description, x_cluster_url, allowed_domains, expected_result, expected_error",
        [
            ("Allowed domain", "https://api.example.com", ["example.com"], True, None),
            (
                "Subdomain allowed",
                "https://k8s.cluster.example.com",
                ["example.com"],
                True,
                None,
            ),
            (
                "Not allowed domain",
                "https://api.notallowed.com",
                ["example.com"],
                False,
                None,
            ),
            (
                "Multiple allowed domains, one matches",
                "https://api.foo.org",
                ["example.com", "foo.org"],
                True,
                None,
            ),
            (
                "No allowed domains (should skip validation and allow)",
                "https://api.anything.com",
                [],
                True,
                None,
            ),
            (
                "Malformed URL (should raise ValueError)",
                "not-a-url",
                ["example.com"],
                False,
                ValueError,
            ),
            (
                "Hostname is None (should raise ValueError)",
                "http://",
                ["example.com"],
                False,
                ValueError,
            ),
        ],
    )
    def test_is_cluster_url_allowed(
        self,
        description,
        x_cluster_url,
        allowed_domains,
        expected_result,
        expected_error,
    ):
        headers = K8sAuthHeaders(
            x_cluster_url=x_cluster_url,
            x_cluster_certificate_authority_data="dGVzdA==",
            x_k8s_authorization="token",
            x_client_certificate_data=None,
            x_client_key_data=None,
            allowed_domains=allowed_domains,
        )

        # when/then
        if expected_error:
            with pytest.raises(expected_error):
                headers.is_cluster_url_allowed()
        else:
            assert headers.is_cluster_url_allowed() == expected_result, description


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
    def test_get_api_request_single_object(
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
        "test_description, data_sanitizer, raw_data_pages, expected_result, pagination_flow",
        [
            (
                "should sanitize items when sanitizer is set for paginated list response",
                Mock(
                    sanitize=Mock(
                        side_effect=[[{"sanitized": "data1"}, {"sanitized": "data2"}]]
                    )
                ),
                [
                    {"items": [{"raw": "data1"}], "metadata": {"continue": "token123"}},
                    {"items": [{"raw": "data2"}], "metadata": {}},
                ],
                [{"sanitized": "data1"}, {"sanitized": "data2"}],
                "multi-page",
            ),
            (
                "should return raw items when sanitizer is not set for paginated list response",
                None,
                [
                    {"items": [{"raw": "data1"}], "metadata": {"continue": "token123"}},
                    {"items": [{"raw": "data2"}], "metadata": {}},
                ],
                [{"raw": "data1"}, {"raw": "data2"}],
                "multi-page",
            ),
            (
                "should return raw items when sanitizer is not set for paginated list response",
                None,
                [
                    {"items": [{"raw": "data1"}], "metadata": {"continue": "token123"}},
                    {
                        "items": [{"raw": "data11"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data12"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data13"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data14"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data15"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data16"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data17"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data18"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data19"}],
                        "metadata": {"continue": "token123"},
                    },
                    {
                        "items": [{"raw": "data10"}],
                        "metadata": {"continue": "token123"},
                    },
                    {"items": [{"raw": "data2"}], "metadata": {}},
                ],
                [
                    {"raw": "data1"},
                    {"raw": "data11"},
                    {"raw": "data12"},
                    {"raw": "data13"},
                    {"raw": "data14"},
                    {"raw": "data15"},
                    {"raw": "data16"},
                    {"raw": "data17"},
                    {"raw": "data18"},
                    {"raw": "data19"},
                    {"raw": "data10"},
                    {"raw": "data2"},
                ],
                "multi-page",
            ),
            (
                "should return result for single page response",
                None,
                [{"metadata": {}}],
                {"metadata": {}},
                "single-page",
            ),
            (
                "should return empty items for single page list response",
                None,
                [{"items": [], "metadata": {}}],
                {"items": [], "metadata": {}},
                "single-page",
            ),
            (
                "should return sanitized items for single page list response",
                Mock(sanitize=Mock(return_value=[{"sanitized": "data"}])),
                [{"items": [{"raw": "data"}], "metadata": {}}],
                [{"sanitized": "data"}],
                "single-page",
            ),
            (
                "should return raw items for single page list response when sanitizer is not set",
                None,
                [{"items": [{"raw": "data"}], "metadata": {}}],
                [{"raw": "data"}],
                "single-page",
            ),
        ],
    )
    def test_get_api_request_list_with_pagination(
        self,
        k8s_client,
        test_description,
        data_sanitizer,
        raw_data_pages,
        expected_result,
        pagination_flow,
        monkeypatch,
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

        monkeypatch.setattr(
            "services.k8s.K8S_API_PAGINATION_MAX_PAGE", len(raw_data_pages) + 1
        )

        # Create response mocks based on pagination flow
        response_mocks = [
            Mock(status_code=HTTPStatus.OK, json=Mock(return_value=page))
            for page in raw_data_pages
        ]

        # when
        with patch("requests.get", side_effect=response_mocks):
            result = k8s_client.execute_get_api_request("/test/uri")

        # then
        if data_sanitizer:
            assert data_sanitizer.sanitize.call_count == 1

        assert result == expected_result

    @pytest.mark.parametrize(
        "test_description, test_type, error_status, error_message, pages_to_exceed_limit",
        [
            # HTTP Error test cases
            (
                "should raise ValueError when API returns non-OK status",
                "error",
                HTTPStatus.BAD_REQUEST,
                "Error message",
                None,
            ),
            (
                "should raise ValueError when API returns unauthorized status",
                "error",
                HTTPStatus.UNAUTHORIZED,
                "Unauthorized access",
                None,
            ),
            # Pagination limit test case
            (
                "should raise ValueError when pagination exceeds maximum pages",
                "pagination_limit",
                None,
                None,
                K8S_API_PAGINATION_MAX_PAGE + 1,
            ),
        ],
    )
    def test_execute_get_api_request(
        self,
        k8s_client,
        test_description,
        test_type,
        error_status,
        error_message,
        pages_to_exceed_limit,
    ):
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url="abc",
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.ca_temp_filename = "test-ca-file"
        k8s_client.data_sanitizer = None

        if test_type == "error":
            response_mock = Mock(status_code=error_status, text=error_message)

            with (
                patch("requests.get", return_value=response_mock),
                pytest.raises(
                    ValueError,
                    match=f"Failed to execute GET request to the Kubernetes API. Error: {error_message}",
                ),
            ):
                k8s_client.execute_get_api_request("/test/uri")

        elif test_type == "pagination_limit":

            response_mocks = []
            for i in range(pages_to_exceed_limit):
                mock = Mock(status_code=HTTPStatus.OK)
                if i < pages_to_exceed_limit - 1:
                    mock.json.return_value = {
                        "items": [{"data": f"page-{i}"}],
                        "metadata": {"continue": f"token-{i}"},
                    }
                else:
                    mock.json.return_value = {
                        "items": [{"data": f"page-{i}"}],
                        "metadata": {},
                    }
                response_mocks.append(mock)

            with (
                patch("requests.get", side_effect=response_mocks),
                pytest.raises(ValueError, match="Kubernetes API rate limit exceeded"),
            ):
                k8s_client.execute_get_api_request("/test/uri")

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

    @patch("services.k8s.K8sClient.__init__", return_value=None)
    @pytest.mark.parametrize(
        "test_description, group_version, expected_uri",
        [
            (
                "should call api/v1 when group_version is CoreV1",
                "v1",
                "api/v1",
            ),
            (
                "should call apis/<groupVersion> when group_version is different",
                "apps/v1",
                "apis/apps/v1",
            ),
        ],
    )
    def test_get_group_version(
        self, mock_init, test_description, group_version, expected_uri
    ):
        # given
        k8s_client = K8sClient(k8s_auth_headers=None, data_sanitizer=None)
        with patch(
            "services.k8s.K8sClient.execute_get_api_request"
        ) as mock_execute_get_api_request:
            mock_execute_get_api_request.return_value = {}

            # when
            result = k8s_client.get_group_version(group_version)

            # then
            assert result == {}
            mock_execute_get_api_request.assert_called_once_with(
                expected_uri
            ), test_description
