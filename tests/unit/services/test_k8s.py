from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aioresponses import aioresponses

from services.data_sanitizer import DataSanitizer
from services.k8s import (
    AuthType,
    K8sAuthHeaders,
    K8sClient,
    K8sClientError,
    get_url_for_paged_request,
)
from utils.settings import K8S_API_PAGINATION_MAX_PAGE


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
    def test_get_decoded_certificate_authority_data(self, given_ca_data, expected_result):
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
    def test_get_decoded_client_certificate_data(self, given_client_cert_data, expected_result, expected_error):
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
    def test_get_decoded_client_key_data(self, given_client_key_data, expected_result, expected_exception):
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
    def test_validate_headers(self, description: str, k8s_headers: K8sAuthHeaders, expected_error_msg: str):
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
            (
                "Domain that contains allowed domain as substring (should be blocked)",
                "https://api.notexample.com",
                ["example.com"],
                False,
                None,
            ),
            ("Exact domain match", "https://example.com", ["example.com"], True, None),
            (
                "Port in URL should be handled correctly",
                "https://api.example.com:8080",
                ["example.com"],
                True,
                None,
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
            k8s_client.client_ssl_context = None
            return k8s_client

    def test_model_dump(self, k8s_client):
        assert k8s_client.model_dump() is None

    def test_lazy_initialization_of_dynamic_client(self):
        """Test that dynamic_client is lazily initialized on first access."""
        with patch("services.k8s.K8sClient._create_dynamic_client") as mock_create:
            mock_dynamic_client = Mock()
            mock_create.return_value = mock_dynamic_client

            # Create K8sClient instance
            with patch("services.k8s.K8sClient.__init__", return_value=None):
                k8s_client = K8sClient()
                k8s_client._dynamic_client = None  # Simulate lazy initialization state
                k8s_client._create_dynamic_client = mock_create

                # _create_dynamic_client should NOT be called during initialization
                mock_create.assert_not_called()

                # First access to dynamic_client property triggers initialization
                result = k8s_client.dynamic_client
                mock_create.assert_called_once()
                assert result == mock_dynamic_client

                # Second access should return cached instance, not call _create_dynamic_client again
                result2 = k8s_client.dynamic_client
                assert mock_create.call_count == 1  # Still only called once
                assert result2 == mock_dynamic_client

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
    def test_get_auth_headers(self, k8s_client, test_description, k8s_headers, expected_result):
        # given
        k8s_client.k8s_auth_headers = k8s_headers

        # when
        result = k8s_client._get_auth_headers()

        # then
        assert result == expected_result

    @pytest.mark.asyncio
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
    async def test_get_api_request_single_object(
        self, k8s_client, test_description, data_sanitizer, raw_data, expected_result
    ):
        # given
        k8s_client.api_server = "http://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.ca_temp_filename = "test-ca-file"
        k8s_client.data_sanitizer = data_sanitizer
        target_url = "/test/uri"
        mock_url = f"{k8s_client.k8s_auth_headers.x_cluster_url}{target_url}?limit=40"

        # when
        with aioresponses() as aio_mock_response:
            # set mock response for: 'http://api.example.com/test/uri?limit=40'
            aio_mock_response.get(
                mock_url,
                payload=raw_data,
                status=HTTPStatus.OK,
            )

            result = await k8s_client.execute_get_api_request(target_url)

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, data_sanitizer, raw_data_pages, expected_result, pagination_flow",
        [
            (
                "should sanitize items when sanitizer is set for paginated list response",
                Mock(sanitize=Mock(side_effect=[[{"sanitized": "data1"}, {"sanitized": "data2"}]])),
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
    async def test_get_api_request_list_with_pagination(
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

        monkeypatch.setattr("services.k8s.K8S_API_PAGINATION_MAX_PAGE", len(raw_data_pages) + 1)

        with aioresponses() as aio_mock_response:
            # Create response mocks based on pagination flow
            for i, page in enumerate(raw_data_pages):
                # The logic:
                # First request: No continue token needed (i-1 < 0)
                # Subsequent requests: Must include the continue token from the previous response to get the next page.
                # Example:
                #   - For page 0: continue_token = None (first request has no continue token)
                #   - For page 1: Gets continue token from raw_data_pages[0]["metadata"]["continue"]
                #   - For page 2: Gets continue token from raw_data_pages[1]["metadata"]["continue"]
                continue_token = None if i - 1 < 0 else raw_data_pages[i - 1].get("metadata", {}).get("continue", None)
                mock_url = get_url_for_paged_request(
                    f"{k8s_client.k8s_auth_headers.x_cluster_url}/test/uri",
                    continue_token,
                )
                aio_mock_response.get(
                    mock_url,
                    payload=page,
                    status=HTTPStatus.OK,
                )

            # when
            result = await k8s_client.execute_get_api_request("/test/uri")

        # then
        if data_sanitizer:
            assert data_sanitizer.sanitize.call_count == 1

        assert result == expected_result

    @pytest.mark.asyncio
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
    async def test_execute_get_api_request(
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
            with (
                aioresponses() as aio_mock_response,
                pytest.raises(
                    K8sClientError,
                    match=f"Failed to execute GET request to the Kubernetes API. Error: {error_message}",
                ),
            ):
                mock_url = get_url_for_paged_request(f"{k8s_client.k8s_auth_headers.x_cluster_url}/test/uri", "")
                aio_mock_response.get(
                    mock_url,
                    body=error_message,
                    status=error_status,
                )
                await k8s_client.execute_get_api_request("/test/uri")

        elif test_type == "pagination_limit":
            with (
                aioresponses() as aio_mock_response,
                pytest.raises(ValueError, match="Kubernetes API rate limit exceeded"),
            ):
                # Mock the responses for each page
                for i in range(pages_to_exceed_limit):
                    mock_url = get_url_for_paged_request(
                        f"{k8s_client.k8s_auth_headers.x_cluster_url}/test/uri",
                        (f"token-{i}" if i != 0 else ""),  # First page has no continue token.
                    )
                    payload = {
                        "items": [{"data": f"page-{i + 1}"}],
                        "metadata": {"continue": f"token-{i + 1}"},
                    }
                    aio_mock_response.get(
                        mock_url,
                        payload=payload,
                        status=HTTPStatus.OK,
                    )
                # when
                await k8s_client.execute_get_api_request("/test/uri")

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
    def test_list_resources(self, k8s_client, test_description, data_sanitizer, raw_data, expected_result):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_resource = Mock()
        mock_item = Mock()
        mock_item.to_dict.return_value = raw_data[0]
        mock_resource.items = [mock_item]

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value = mock_resource
        k8s_client._dynamic_client = mock_dynamic_client

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
    def test_get_resource(self, k8s_client, test_description, data_sanitizer, raw_data, expected_result):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value.to_dict.return_value = raw_data
        k8s_client._dynamic_client = mock_dynamic_client

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
            patch.object(k8s_client, "list_k8s_events_for_resource") as mock_list_events,
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
    def test_list_k8s_events(self, k8s_client, test_description, data_sanitizer, raw_data, expected_result):
        # given
        k8s_client.data_sanitizer = data_sanitizer

        mock_resource = Mock()
        mock_item = Mock()
        mock_item.to_dict.return_value = raw_data[0]
        mock_resource.items = [mock_item]

        mock_dynamic_client = Mock()
        mock_dynamic_client.resources.get.return_value.get.return_value = mock_resource
        k8s_client._dynamic_client = mock_dynamic_client

        # when
        result = k8s_client.list_k8s_events("default")

        # then
        if data_sanitizer:
            data_sanitizer.sanitize.assert_called_once_with(raw_data)
        assert result == expected_result

    @patch("services.k8s.K8sClient.__init__", return_value=None)
    @pytest.mark.asyncio
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
    async def test_get_group_version(self, mock_init, test_description, group_version, expected_uri):
        # given
        k8s_client = K8sClient(k8s_auth_headers=None, data_sanitizer=None)
        with patch("services.k8s.K8sClient.execute_get_api_request") as mock_execute_get_api_request:
            mock_execute_get_api_request.return_value = {}

            # when
            result = await k8s_client.get_group_version(group_version)

            # then
            assert result == {}
            mock_execute_get_api_request.assert_called_once_with(expected_uri), test_description

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mock_response_lines, expected_sanitized_logs",
        [
            # Test case 1: Email addresses should be redacted
            (
                [
                    "User logged in: john.doe@company.com",
                    "Processing request for admin@example.org",
                ],
                ["User logged in: {{EMAIL}}", "Processing request for {{EMAIL}}"],
            ),
            # Test case 2: Credit card numbers should be redacted
            (
                ["Payment processed: 378282246310005", "Card ending in 1234"],
                ["Payment processed: {{CREDIT_CARD}}", "Card ending in 1234"],
            ),
            # Test case 3: Social Security Numbers should be redacted
            (
                ["SSN: 123-45-6789", "Social Security: 001-01-0001"],
                [
                    "SSN: {{SOCIAL_SECURITY_NUMBER}}",
                    "Social Security: {{SOCIAL_SECURITY_NUMBER}}",
                ],
            ),
            # Test case 4: API keys and tokens should be redacted
            (
                [
                    "API_KEY=sk-1234567890abcdef1234567890abcdef",
                    "Bearer token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "Auth: Basic dXNlcjpwYXNzd29yZA==",
                ],
                [
                    "{{REDACTED}}",
                    "{{REDACTED}}",
                    "{{REDACTED}}",
                ],
            ),
            # Test case 6: Passwords in logs should be redacted
            (
                [
                    "password=secretpassword123",
                    "pwd: mypassword",
                    "LOGIN: user=admin password=admin123",
                ],
                [
                    "{{REDACTED}}",
                    "{{REDACTED}}",
                    "LOGIN: {{REDACTED}} {{REDACTED}}",
                ],
            ),
            # Test case 8: Database connection strings should be redacted
            (
                [
                    "DB_URL=postgresql://user:pass@localhost:5432/mydb",
                    "Connection: mysql://admin:secret@db.example.com/prod",
                ],
                [
                    "DB_URL=postgresql://{{REDACTED}}",
                    "Connection: mysql://admin:{{EMAIL}}/prod",
                ],
            ),
            # Test case 9: Mixed sensitive data in single log line
            (
                ["User john@example.com logged with user=admin password=admin123"],
                ["User {{EMAIL}} logged with {{REDACTED}} {{REDACTED}}"],
            ),
            # Test case 10: Normal logs without sensitive data should remain unchanged
            (
                [
                    "Application started successfully",
                    "Processing batch job #12345",
                    "Cache hit ratio: 85%",
                ],
                [
                    "Application started successfully",
                    "Processing batch job #12345",
                    "Cache hit ratio: 85%",
                ],
            ),
            # Test case 11: Multiple logs
            (
                [
                    "2025-06-30 14:12:34,184 - agents.summarization.summarization - DEBUG - Summarization node started",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base encoding",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base e",
                    "2025-06-30 14:12:34,184 - agents.Kyma - INFO  password=secret123",
                    "2025-06-30 14:12:34,184 - agents.Kyma - INFO  user_name=joe",
                    "2025-06-30 14:12:34,184 - agents.summarization.summarization - DEBUG - Summarization node started",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base encoding",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base e",
                ],
                [
                    "2025-06-30 14:12:34,184 - agents.summarization.summarization - DEBUG - Summarization node started",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base encoding",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base e",
                    "2025-06-30 14:12:34,184 - agents.Kyma - INFO  {{REDACTED}}",
                    "2025-06-30 14:12:34,184 - agents.Kyma - INFO  {{REDACTED}}",
                    "2025-06-30 14:12:34,184 - agents.summarization.summarization - DEBUG - Summarization node started",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base encoding",
                    "2025-06-30 14:12:34,184 - agents.common.utils - WARNING - Model 'gpt-4.1' not recognized by tiktoken, using cl100k_base e",
                ],
            ),
            # Test case 12: Empty logs
            ([], []),
            # Test case 13: Logs with only whitespace
            (["   ", "\t\n", ""], ["", "", ""]),
        ],
    )
    async def test_fetch_pod_logs(self, k8s_client, mock_response_lines, expected_sanitized_logs):
        """
        Test the functionality in fetch_pod_logs method.
        """

        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = DataSanitizer()

        with aioresponses() as aio_mock_response:
            # Mock both current and previous logs (new behavior: fetch both in parallel)
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            # Mock current logs (success)
            aio_mock_response.get(
                current_url,
                body="\n".join(mock_response_lines),
                status=HTTPStatus.OK,
            )

            # Mock previous logs (not available - common case)
            aio_mock_response.get(
                previous_url,
                body='{"message": "previous terminated container \\"app\\" in pod \\"test-pod\\" not found"}',
                status=HTTPStatus.BAD_REQUEST,
            )

            # when
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then
            # New format: shows both current and previous log sections with status
            result_str = "\n".join(result)

            # Should show current logs successfully
            assert "# Current logs: Successfully fetched" in result_str
            assert all(line in result_str for line in expected_sanitized_logs)

            # Should show previous logs not available
            assert "# Previous logs: Not available" in result_str

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "first_call_error_status, first_call_error_msg, second_call_logs, expected_logs",
        [
            # Test case: fallback to previous after container not found error
            (
                HTTPStatus.BAD_REQUEST,
                '{"message": "container my-container not found in pod test-pod"}',
                ["previous log line 1", "previous log line 2"],
                ["previous log line 1", "previous log line 2"],
            ),
            # Test case: fallback after CrashLoopBackOff
            (
                HTTPStatus.BAD_REQUEST,
                '{"message": "pod is in CrashLoopBackOff state"}',
                ["crash log 1", "crash log 2"],
                ["crash log 1", "crash log 2"],
            ),
            # Test case: fallback after pod terminated error
            (
                HTTPStatus.BAD_REQUEST,
                '{"message": "pod has terminated"}',
                ["terminated log 1"],
                ["terminated log 1"],
            ),
        ],
    )
    async def test_fetch_pod_logs_both_current_and_previous(
        self, k8s_client, first_call_error_status, first_call_error_msg, second_call_logs, expected_logs
    ):
        """Test that fetch_pod_logs fetches both current and previous logs in parallel."""
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        with aioresponses() as aio_mock_response:
            # Current logs fail
            current_logs_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            aio_mock_response.get(
                current_logs_url,
                body=first_call_error_msg,
                status=first_call_error_status,
            )

            # Previous logs succeed
            previous_logs_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )
            aio_mock_response.get(
                previous_logs_url,
                body="\n".join(second_call_logs),
                status=HTTPStatus.OK,
            )

            # Mock diagnostic context gathering - will be shown inline when current logs fail
            k8s_client._gather_pod_diagnostic_context = AsyncMock(return_value="Container is in CrashLoopBackOff state")

            # when
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then
            result_str = "\n".join(result)

            # Should show current logs not available with diagnostic info
            assert "# Current logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Container is in CrashLoopBackOff state" in result_str

            # Should show previous logs successfully
            assert "# Previous logs: Successfully fetched" in result_str
            assert all(line in result_str for line in expected_logs)

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_both_fail_with_diagnostics(self, k8s_client):
        """Test that when both current and previous logs fail, we get diagnostics."""
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        current_error_msg = '{"message": "container not ready"}'
        previous_error_msg = '{"message": "no previous container"}'

        with aioresponses() as aio_mock_response:
            # Current logs fail
            current_logs_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            aio_mock_response.get(
                current_logs_url,
                body=current_error_msg,
                status=HTTPStatus.BAD_REQUEST,
            )

            # Previous logs also fail
            previous_logs_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )
            aio_mock_response.get(
                previous_logs_url,
                body=previous_error_msg,
                status=HTTPStatus.NOT_FOUND,
            )

            # Mock the diagnostic context gathering methods
            k8s_client._gather_pod_diagnostic_context = AsyncMock(return_value="Pod diagnostic info here")

            # when: should return diagnostic info instead of raising
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify diagnostic information is in result
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Pod diagnostic info here" in result_str

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "retryable_status, error_message",
        [
            (HTTPStatus.TOO_MANY_REQUESTS, '{"message": "rate limit exceeded"}'),
            (HTTPStatus.INTERNAL_SERVER_ERROR, '{"message": "internal server error"}'),
            (HTTPStatus.BAD_GATEWAY, '{"message": "bad gateway"}'),
            (HTTPStatus.SERVICE_UNAVAILABLE, '{"message": "service unavailable"}'),
            (HTTPStatus.GATEWAY_TIMEOUT, '{"message": "gateway timeout"}'),
        ],
    )
    async def test_fetch_pod_logs_retry_on_retryable_errors(
        self, k8s_client, retryable_status, error_message, monkeypatch
    ):
        """Test that fetch_pod_logs retries on retryable errors (5xx, 429)."""
        # Mock asyncio.sleep to avoid waiting in tests
        mock_sleep = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        success_logs = ["log line 1", "log line 2"]

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            # Current logs: First two attempts fail with retryable error, third succeeds
            aio_mock_response.get(current_url, body=error_message, status=retryable_status)
            aio_mock_response.get(current_url, body=error_message, status=retryable_status)
            aio_mock_response.get(current_url, body="\n".join(success_logs), status=HTTPStatus.OK)

            # Previous logs: Not available (common case)
            aio_mock_response.get(
                previous_url,
                body='{"message": "no previous container"}',
                status=HTTPStatus.BAD_REQUEST,
            )

            # when
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then
            result_str = "\n".join(result)
            # Current logs should succeed after retries
            assert "# Current logs: Successfully fetched" in result_str
            assert all(line in result_str for line in success_logs)

            # Should have slept twice (after first and second failures)
            assert mock_sleep.call_count == 2  # noqa: PLR2004
            # Verify exponential backoff: 1s, 2s
            assert mock_sleep.call_args_list[0][0][0] == 1  # noqa: PLR2004
            assert mock_sleep.call_args_list[1][0][0] == 2  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_no_retry_on_non_retryable_errors(self, k8s_client, monkeypatch):
        """Test that fetch_pod_logs does NOT retry on non-retryable errors (4xx except 429)."""
        # Mock asyncio.sleep to verify it's not called
        mock_sleep = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        error_message = '{"message": "pod not found"}'

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            # Both current and previous fail with non-retryable 404 error
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.NOT_FOUND)
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.NOT_FOUND)

            # Mock diagnostic context gathering
            k8s_client._gather_pod_diagnostic_context = AsyncMock(return_value="Diagnostic info")

            # when: should return diagnostic info instead of raising
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify diagnostic information is in result
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Diagnostic info" in result_str

            # Should NOT have retried on either call (no sleep calls)
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_max_retries_exceeded(self, k8s_client, monkeypatch):
        """Test that fetch_pod_logs returns diagnostics after max retries."""
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        error_message = '{"message": "service unavailable"}'

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            # Current logs: all three attempts fail
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)

            # Previous logs: all three attempts also fail
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.SERVICE_UNAVAILABLE)

            # Mock diagnostic context gathering
            k8s_client._gather_pod_diagnostic_context = AsyncMock(return_value="Diagnostic info")

            # when: should return diagnostic info after max retries
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify diagnostic information is in result
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Failed to fetch" in result_str  # 503 error shows "Failed to fetch"
            assert "# Diagnostic Information:" in result_str
            assert "Diagnostic info" in result_str

            # Should have slept 4 times total (2 for current retries + 2 for previous retries)
            assert mock_sleep.call_count == 4  # noqa: PLR2004

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error_status, error_message, is_retryable",
        [
            # Authentication error - should NOT fallback, NOT retryable
            (HTTPStatus.UNAUTHORIZED, '{"message": "authentication error when accessing pod logs"}', False),
            # Authorization error - should NOT fallback, NOT retryable
            (HTTPStatus.FORBIDDEN, '{"message": "forbidden: user cannot access container logs"}', False),
            # Resource issue - should NOT fallback, NOT retryable
            (HTTPStatus.BAD_REQUEST, '{"message": "insufficient resources to schedule pod"}', False),
            # Generic pod not found - should NOT fallback, NOT retryable
            (HTTPStatus.NOT_FOUND, '{"message": "pod test-pod not found in namespace default"}', False),
            # API server error - should NOT fallback, but IS retryable (5xx)
            (HTTPStatus.INTERNAL_SERVER_ERROR, '{"message": "error processing request"}', True),
        ],
    )
    async def test_fetch_pod_logs_no_fallback_for_non_container_errors(
        self, k8s_client, error_status, error_message, is_retryable, monkeypatch
    ):
        """Test that fallback does NOT trigger for errors unrelated to container state."""
        # Mock asyncio.sleep to avoid waiting
        mock_sleep = AsyncMock()
        monkeypatch.setattr("asyncio.sleep", mock_sleep)

        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            if is_retryable:
                # For retryable errors (5xx), mock 3 attempts for both current and previous
                for _ in range(3):
                    aio_mock_response.get(current_url, body=error_message, status=error_status)
                    aio_mock_response.get(previous_url, body=error_message, status=error_status)
            else:
                # For non-retryable errors, only 1 attempt for both
                aio_mock_response.get(current_url, body=error_message, status=error_status)
                aio_mock_response.get(previous_url, body=error_message, status=error_status)

            # Mock diagnostic context gathering
            k8s_client._gather_pod_diagnostic_context = AsyncMock(return_value="Diagnostic info")

            # when: Should return diagnostic info
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify diagnostic information is in result
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            # Previous logs status depends on error code
            if error_status in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND):
                assert "# Previous logs: Not available (container has not been restarted)" in result_str
            else:
                assert "# Previous logs: Failed to fetch" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Diagnostic info" in result_str

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_includes_diagnostic_context_on_failure(self, k8s_client, monkeypatch):
        """Test that diagnostic context (events, status) is included when logs fail."""
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        # Mock pod events
        mock_events = [
            {
                "reason": "Failed",
                "message": "Back-off restarting failed container",
                "count": 5,
            },
            {
                "reason": "Killing",
                "message": "Stopping container app",
                "count": 1,
            },
        ]
        monkeypatch.setattr(k8s_client, "list_k8s_events_for_resource", Mock(return_value=mock_events))

        # Mock pod description
        mock_pod_description = {
            "status": {
                "containerStatuses": [
                    {
                        "name": "app",
                        "state": {
                            "waiting": {
                                "reason": "CrashLoopBackOff",
                                "message": "container failed to start",
                            }
                        },
                        "restartCount": 5,
                        "lastState": {
                            "terminated": {
                                "reason": "Error",
                                "exitCode": 1,
                            }
                        },
                    }
                ]
            }
        }
        monkeypatch.setattr(k8s_client, "describe_resource", Mock(return_value=mock_pod_description))

        error_message = '{"message": "container app is in CrashLoopBackOff state"}'

        with aioresponses() as aio_mock_response:
            # Both current and previous logs fail
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.BAD_REQUEST)

            previous_url = f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100&previous=true"
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.BAD_REQUEST)

            # when: should return diagnostic context
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify diagnostic context is included
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Recent Pod Events:" in result_str
            assert "Back-off restarting failed container" in result_str
            assert "Container 'app' Status:" in result_str
            assert "State: Waiting" in result_str
            assert "Reason: CrashLoopBackOff" in result_str
            assert "Restart Count: 5" in result_str
            assert "Last Termination Reason: Error" in result_str
            assert "Last Exit Code: 1" in result_str

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_diagnostic_context_with_failed_init_containers(self, k8s_client, monkeypatch):
        """Test diagnostic context includes failed init containers."""
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        # Mock pod events (empty for this test)
        monkeypatch.setattr(k8s_client, "list_k8s_events_for_resource", Mock(return_value=[]))

        # Mock pod description with failed init container
        mock_pod_description = {
            "status": {
                "containerStatuses": [
                    {
                        "name": "app",
                        "state": {"waiting": {"reason": "PodInitializing"}},
                        "restartCount": 0,
                    }
                ],
                "initContainerStatuses": [
                    {
                        "name": "init-db",
                        "ready": False,
                        "state": {
                            "terminated": {
                                "reason": "Error",
                                "exitCode": 2,
                            }
                        },
                    }
                ],
            }
        }
        monkeypatch.setattr(k8s_client, "describe_resource", Mock(return_value=mock_pod_description))

        error_message = '{"message": "container is waiting to start"}'

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.BAD_REQUEST)

            previous_url = f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100&previous=true"
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.BAD_REQUEST)

            # when: should return diagnostic info
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: verify init container info is included
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "Init Containers (Failed):" in result_str
            assert "init-db" in result_str
            assert "Terminated (Error, exit code: 2)" in result_str

    @pytest.mark.asyncio
    async def test_fetch_pod_logs_diagnostic_context_handles_missing_data(self, k8s_client, monkeypatch):
        """Test diagnostic context handles cases where events/status are unavailable."""
        k8s_client.api_server = "https://api.example.com"
        k8s_client.k8s_auth_headers = K8sAuthHeaders(
            x_cluster_url=k8s_client.api_server,
            x_cluster_certificate_authority_data="abc",
            x_k8s_authorization="test-token",
            x_client_certificate_data=None,
            x_client_key_data=None,
        )
        k8s_client.data_sanitizer = None

        # Mock empty/missing data
        monkeypatch.setattr(k8s_client, "list_k8s_events_for_resource", Mock(return_value=[]))
        monkeypatch.setattr(k8s_client, "describe_resource", Mock(return_value=None))

        error_message = '{"message": "pod not found"}'

        with aioresponses() as aio_mock_response:
            current_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log?container=app&tailLines=100"
            )
            previous_url = (
                f"{k8s_client.api_server}/api/v1/namespaces/default/pods/test-pod/log"
                "?container=app&tailLines=100&previous=true"
            )

            # Both fail
            aio_mock_response.get(current_url, body=error_message, status=HTTPStatus.NOT_FOUND)
            aio_mock_response.get(previous_url, body=error_message, status=HTTPStatus.NOT_FOUND)

            # when: should return diagnostic info
            result = await k8s_client.fetch_pod_logs(
                name="test-pod",
                namespace="default",
                container_name="app",
                tail_limit=100,
            )

            # then: should still have diagnostic section, even if empty
            result_str = "\n".join(result)
            assert "# Current logs: Not available" in result_str
            assert "# Previous logs: Not available" in result_str
            assert "# Diagnostic Information:" in result_str
            assert "No recent pod events found." in result_str
