"""MOSAIC GraphRAG Python SDK client.

A zero-dependency (standard library only) client for the MOSAIC public
REST API. Covers the verification workflow:

    login -> ask questions against a pre-built knowledge base

Usage:
    from mosaic_client import MosaicClient

    client = MosaicClient("https://<mosaic-api-host>")
    client.login(username="demo", password="<password>")
    result = client.answer(database="medical",
                           question="What is the most common type of skin cancer?",
                           domain="medical",
                           question_type="Fact Retrieval")
    print(result["answer"])

Connection settings can also come from the environment:
``MOSAIC_BASE_URL``, ``MOSAIC_USERNAME``, ``MOSAIC_PASSWORD``
(see :meth:`MosaicClient.from_env`).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Dict, Optional

__all__ = [
    "MosaicClient",
    "MosaicError",
    "DOMAINS",
    "QUESTION_TYPES",
    "DEFAULT_BASE_URL",
]

__version__ = "0.1.0"

# TODO: replace with the real public endpoint once it is deployed.
DEFAULT_BASE_URL = "https://api.mosaic.example.com"

API_PREFIX = "/api/mosaic"

DOMAINS = ("medical", "novel", "generic")
QUESTION_TYPES = (
    "Fact Retrieval",
    "Complex Reasoning",
    "Contextual Summarize",
    "Creative Generation",
)

# Transient statuses that are safe to retry (the answer call is read-only).
_RETRY_STATUSES = {429, 502, 503, 504}


class MosaicError(RuntimeError):
    """Raised when the API returns a non-zero code or a transport error occurs.

    Attributes:
        status: HTTP status code, if the error came from an HTTP response.
        code: API envelope ``code``, if the server returned one.
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class MosaicClient:
    """Thin REST client with automatic cookie-session handling.

    Args:
        base_url: API root, e.g. ``https://api.mosaic.example.com``.
        timeout: per-request timeout in seconds (answer generation can be slow).
        max_retries: retries for transient failures (429/502/503/504, network
            errors). Uses exponential backoff starting at ``retry_backoff``.
        retry_backoff: initial backoff in seconds.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: int = 300,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        self._credentials: Optional[Dict[str, str]] = None

    @classmethod
    def from_env(cls, **kwargs: Any) -> "MosaicClient":
        """Build a client from ``MOSAIC_*`` environment variables.

        Logs in automatically when ``MOSAIC_USERNAME`` and ``MOSAIC_PASSWORD``
        are both set.
        """
        client = cls(os.environ.get("MOSAIC_BASE_URL", DEFAULT_BASE_URL), **kwargs)
        username = os.environ.get("MOSAIC_USERNAME")
        password = os.environ.get("MOSAIC_PASSWORD")
        if username and password:
            client.login(username, password)
        return client

    # ------------------------------------------------------------------ core

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = self.base_url + path

        attempt = 0
        while True:
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")
                if error.code in _RETRY_STATUSES and attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_backoff * 2 ** (attempt - 1))
                    continue
                raise MosaicError(
                    f"HTTP {error.code} on {method} {url}: {detail[:500]}",
                    status=error.code,
                ) from error
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_backoff * 2 ** (attempt - 1))
                    continue
                raise MosaicError(f"request failed: {method} {url}: {error}") from error
            except json.JSONDecodeError as error:
                raise MosaicError(f"invalid JSON from {method} {url}: {error}") from error

    @staticmethod
    def _unwrap(body: Dict[str, Any]) -> Dict[str, Any]:
        if body.get("code") != 0:
            raise MosaicError(str(body.get("message", body)), code=body.get("code"))
        return body.get("payload", {})

    def _authed(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None):
        """Call an authenticated route, re-logging in once if the session expired."""
        try:
            return self._unwrap(self._request(method, path, payload))
        except MosaicError as error:
            if error.status != 401 or not self._credentials:
                raise
            self.login(**self._credentials)
            return self._unwrap(self._request(method, path, payload))

    # ----------------------------------------------------------------- auth

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Exchange credentials for the API session cookie.

        All ``/api/mosaic/*`` calls require this session; the client keeps it
        automatically and transparently re-authenticates once on HTTP 401.
        """
        body = self._request(
            "POST", f"{API_PREFIX}/login", {"username": username, "password": password}
        )
        if body.get("code") != 0:
            raise MosaicError(
                "login failed: " + str(body.get("message", body)), code=body.get("code")
            )
        self._credentials = {"username": username, "password": password}
        return body.get("payload", {})

    def version(self) -> Dict[str, Any]:
        """Return the deployed service version (no auth; useful as a health check)."""
        return self._request("GET", "/api/version")

    # ------------------------------------------------------------------- QA

    def answer(
        self,
        database: str,
        question: str,
        *,
        domain: str = "medical",
        question_type: str = "Fact Retrieval",
        top_k: int = 10,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ask a question against a knowledge base.

        Args:
            database: knowledge base to query. Pre-built benchmark knowledge
                bases: ``medical`` and ``novel``.
            question: natural-language question.
            domain: ``medical`` | ``novel`` | ``generic``.
            question_type: one of ``Fact Retrieval``, ``Complex Reasoning``,
                ``Contextual Summarize``, ``Creative Generation``.
            top_k: number of retrieved documents to ground the answer.
            query_id: optional caller-side id, echoed back for traceability.

        Returns:
            ``{"answer": str,
               "retrieval": {"documents": [{uid, rank, score, content} ...], ...},
               "answering": {...}}``
        """
        if domain not in DOMAINS:
            raise ValueError(f"domain must be one of {DOMAINS}, got {domain!r}")
        if question_type not in QUESTION_TYPES:
            raise ValueError(
                f"question_type must be one of {QUESTION_TYPES}, got {question_type!r}"
            )
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")

        payload: Dict[str, Any] = {
            "database": database,
            "question": question,
            "domain": domain,
            "question_type": question_type,
            "top_k": top_k,
        }
        if query_id is not None:
            payload["query_id"] = query_id
        return self._authed("POST", f"{API_PREFIX}/answer", payload)
