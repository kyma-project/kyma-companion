from http import HTTPStatus
from unittest.mock import Mock

import pytest
from fastapi import Response
from starlette.responses import StreamingResponse

from main import MEDIA_TYPE_SSE, RELAXED_PATHS, SECURITY_HEADERS, security_headers_middleware


@pytest.fixture
def mock_request():
    request = Mock()
    request.method = "GET"
    request.url = Mock()
    request.url.path = "/api/test"
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


# ---------------------------------------------------------------------------
# Helpers: response factories
# ---------------------------------------------------------------------------


def _make_call_next(
    status_code=HTTPStatus.OK,
    content=None,
    media_type=None,
    headers=None,
):
    """Create an async ``call_next`` returning the configured response."""

    async def call_next(_request):
        if media_type == MEDIA_TYPE_SSE:

            async def stream():
                yield b""

            resp = StreamingResponse(stream(), media_type=media_type)
        else:
            kwargs = {"status_code": status_code}
            if content is not None:
                kwargs["content"] = content
            if media_type is not None:
                kwargs["media_type"] = media_type
            resp = Response(**kwargs)
        for k, v in (headers or {}).items():
            resp.headers[k] = v
        return resp

    return call_next


# ---------------------------------------------------------------------------
# Helpers: assertion functions (one per logical check)
# ---------------------------------------------------------------------------


def _assert_all_default_headers(response):
    """Every SECURITY_HEADERS entry is present with its default value."""
    for header, value in SECURITY_HEADERS.items():
        assert response.headers.get(header) == value, (
            f"Expected '{header}: {value}', got '{response.headers.get(header)}'"
        )


def _verify_headers_on_status(status_code):
    def verify(response):
        assert response.status_code == status_code
        _assert_all_default_headers(response)

    return verify


def _verify_csp_directives(response):
    csp = response.headers["Content-Security-Policy"]
    for directive in (
        "default-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'none'",
        "base-uri 'none'",
    ):
        assert directive in csp, f"Missing CSP directive: {directive}"
    for banned in ("unsafe-inline", "unsafe-eval"):
        assert banned not in csp, f"CSP must not contain {banned}"


def _verify_hsts(response):
    hsts = response.headers["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


def _verify_body_preserved(response):
    assert response.body == b"hello"


def _verify_existing_header_not_overridden(response):
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"
    for header, value in SECURITY_HEADERS.items():
        if header == "Content-Security-Policy":
            continue
        assert response.headers.get(header) == value


def _verify_required_header_keys(_response):
    assert {
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "Referrer-Policy",
        "X-Content-Type-Options",
        "Cache-Control",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
    } == set(SECURITY_HEADERS.keys())


def _verify_sse_skips_cache_control(response):
    assert "no-store" not in response.headers.get("Cache-Control", "")
    for header, value in SECURITY_HEADERS.items():
        if header == "Cache-Control":
            continue
        assert response.headers.get(header) == value


def _verify_non_sse_cache_control(response):
    assert response.headers["Cache-Control"] == "no-store"


def _verify_relaxed_path_skips_security_headers(response):
    """For relaxed (docs) paths, no security headers should be injected."""
    for header in SECURITY_HEADERS:
        assert header not in response.headers, f"Security header '{header}' should not be present on relaxed path"


# ---------------------------------------------------------------------------
# Status codes exercised for the "all-headers-present" cases
# ---------------------------------------------------------------------------

_STATUS_CODES = [
    HTTPStatus.OK,
    HTTPStatus.CREATED,
    HTTPStatus.BAD_REQUEST,
    HTTPStatus.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN,
    HTTPStatus.NOT_FOUND,
    HTTPStatus.UNPROCESSABLE_ENTITY,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.SERVICE_UNAVAILABLE,
]


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSecurityHeadersMiddleware:
    """Tests for security_headers_middleware."""

    @pytest.mark.parametrize(
        "description, call_next, verify",
        [
            *[
                pytest.param(
                    f"All security headers are present on {sc} responses",
                    _make_call_next(status_code=sc),
                    _verify_headers_on_status(sc),
                    id=f"all-headers-on-{sc}",
                )
                for sc in _STATUS_CODES
            ],
            pytest.param(
                "CSP includes required directives and excludes unsafe ones",
                _make_call_next(),
                _verify_csp_directives,
                id="csp-directives",
            ),
            pytest.param(
                "HSTS includes max-age and includeSubDomains",
                _make_call_next(),
                _verify_hsts,
                id="hsts-value",
            ),
            pytest.param(
                "Middleware does not alter the response body",
                _make_call_next(content=b"hello"),
                _verify_body_preserved,
                id="body-not-altered",
            ),
            pytest.param(
                "Middleware does not override headers already set by downstream",
                _make_call_next(
                    headers={"Content-Security-Policy": "default-src 'self'"},
                ),
                _verify_existing_header_not_overridden,
                id="existing-headers-preserved",
            ),
            pytest.param(
                "SECURITY_HEADERS constant contains all required keys",
                _make_call_next(),
                _verify_required_header_keys,
                id="constant-has-all-required-keys",
            ),
            pytest.param(
                "SSE responses do not get Cache-Control overridden with no-store",
                _make_call_next(media_type=MEDIA_TYPE_SSE),
                _verify_sse_skips_cache_control,
                id="sse-skips-cache-control",
            ),
            pytest.param(
                "Non-SSE responses get Cache-Control: no-store",
                _make_call_next(),
                _verify_non_sse_cache_control,
                id="non-sse-cache-control-no-store",
            ),
        ],
    )
    async def test_security_headers_middleware(self, mock_request, description, call_next, verify):
        """Verify security headers are correctly applied to every response."""
        response = await security_headers_middleware(mock_request, call_next)
        verify(response)

    @pytest.mark.parametrize("path", list(RELAXED_PATHS), ids=[p.strip("/") for p in RELAXED_PATHS])
    async def test_relaxed_paths_skip_security_headers(self, mock_request, path):
        """Verify that relaxed (docs) paths return responses without any security headers."""
        mock_request.url.path = path
        call_next = _make_call_next()
        response = await security_headers_middleware(mock_request, call_next)
        _verify_relaxed_path_skips_security_headers(response)
