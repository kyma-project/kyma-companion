from http import HTTPStatus
from unittest.mock import Mock

import pytest
from fastapi import Response

from main import SECURITY_HEADERS, security_headers_middleware


@pytest.fixture
def mock_request():
    request = Mock()
    request.method = "GET"
    request.url = Mock()
    request.url.path = "/api/test"
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


@pytest.mark.asyncio
class TestSecurityHeadersMiddleware:
    """Tests for security_headers_middleware."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTPStatus.OK,
            HTTPStatus.CREATED,
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.SERVICE_UNAVAILABLE,
        ],
    )
    async def test_all_security_headers_present_on_all_status_codes(self, mock_request, status_code):
        """All required security headers must be present regardless of status code."""

        async def call_next(_request):
            return Response(status_code=status_code)

        response = await security_headers_middleware(mock_request, call_next)

        assert response.status_code == status_code
        for header, value in SECURITY_HEADERS.items():
            assert response.headers.get(header) == value, (
                f"Expected header '{header}: {value}' on {status_code} response"
            )

    async def test_content_security_policy_value(self, mock_request):
        """CSP must include frame-ancestors, form-action, base-uri directives."""

        async def call_next(_request):
            return Response(status_code=HTTPStatus.OK)

        response = await security_headers_middleware(mock_request, call_next)
        csp = response.headers["Content-Security-Policy"]

        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "form-action 'none'" in csp
        assert "base-uri 'none'" in csp
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    async def test_hsts_value(self, mock_request):
        """HSTS must include max-age and includeSubDomains."""

        async def call_next(_request):
            return Response(status_code=HTTPStatus.OK)

        response = await security_headers_middleware(mock_request, call_next)
        hsts = response.headers["Strict-Transport-Security"]

        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    async def test_does_not_override_existing_response_body(self, mock_request):
        """Middleware must not alter the response body."""

        async def call_next(_request):
            return Response(content=b"hello", status_code=HTTPStatus.OK)

        response = await security_headers_middleware(mock_request, call_next)

        assert response.body == b"hello"

    async def test_security_headers_constant_contains_all_required_headers(self):
        """SECURITY_HEADERS dict must contain all required keys."""
        required = {
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "Referrer-Policy",
            "X-Content-Type-Options",
            "Cache-Control",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
        }
        assert required == set(SECURITY_HEADERS.keys())
