"""A minimal Meta Graph API client using only the standard library."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

GRAPH_HOST = "https://graph.facebook.com"
USER_AGENT = "social-autopilot/0.1"


class GraphError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None, subcode: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.subcode = subcode

    @property
    def transient(self) -> bool:
        # 1/2: unknown/service errors, 4/17/32/613: rate limits, 5xx: server trouble.
        return (self.status or 0) >= 500 or self.code in (1, 2, 4, 17, 32, 613)


Transport = Callable[[str, str, dict[str, str]], tuple[int, bytes]]


def urllib_transport(method: str, url: str, params: dict[str, str]) -> tuple[int, bytes]:
    data = None
    if method == "GET":
        url = url + "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class Graph:
    def __init__(self, token: str, version: str, transport: Transport = urllib_transport, sleep=time.sleep):
        self._token = token
        self.version = version
        self._transport = transport
        self.sleep = sleep

    def get(self, path: str, retries: int = 3, **params: Any) -> dict:
        """GET is safe to repeat, so transient failures are retried."""
        for attempt in range(retries + 1):
            try:
                return self._call("GET", path, params)
            except GraphError as exc:
                if not exc.transient or attempt == retries:
                    raise
                self.sleep(2 ** attempt * 5)
        raise AssertionError("unreachable")

    def post(self, path: str, **params: Any) -> dict:
        """POST is never retried automatically: a lost response could otherwise publish twice."""
        return self._call("POST", path, params)

    def _call(self, method: str, path: str, params: dict[str, Any]) -> dict:
        url = f"{GRAPH_HOST}/{self.version}/{path.lstrip('/')}"
        clean = {k: _encode(v) for k, v in params.items() if v is not None}
        clean["access_token"] = self._token
        try:
            status, body = self._transport(method, url, clean)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GraphError(f"network error calling {path}: {exc}", status=599) from None
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            raise GraphError(f"{path}: non-JSON response (HTTP {status})", status=status) from None
        if status >= 400 or "error" in payload:
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            msg = err.get("error_user_msg") or err.get("message") or f"HTTP {status}"
            raise GraphError(
                f"{path}: {msg}",
                status=status,
                code=err.get("code"),
                subcode=err.get("error_subcode"),
            )
        return payload


def _encode(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def check_public_url(url: str) -> str | None:
    """Return a problem description if Meta would be unable to download this media URL."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            kind = resp.headers.get("Content-Type", "")
            if not kind.startswith(("image/jpeg", "video/")):
                return f"{url} is served as '{kind}', expected image/jpeg or a video"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return f"{url} is not reachable: {exc}"
    return None
