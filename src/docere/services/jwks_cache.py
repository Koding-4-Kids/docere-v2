"""JWKS key caching for LTI 1.3 JWT validation.

Uses PyJWT's built-in JWKClient with a per-URL cache.
Keys are cached for 1 hour (PyJWT default lifespan).
"""

from jwt import PyJWKClient

# Cache of JWKS clients keyed by URL
_jwks_clients: dict[str, PyJWKClient] = {}


def get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Get or create a cached PyJWKClient for the given JWKS URL.

    PyJWKClient handles key caching internally with a 5-minute lifespan
    by default. We also cache the client instance itself per URL.
    """
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=3600,  # 1 hour cache TTL
        )
    return _jwks_clients[jwks_url]


def clear_jwks_cache(jwks_url: str | None = None) -> None:
    """Force re-fetch of JWKS keys on next use.

    Call this if a platform rotates their signing keys and
    validation starts failing.
    """
    if jwks_url:
        _jwks_clients.pop(jwks_url, None)
    else:
        _jwks_clients.clear()
