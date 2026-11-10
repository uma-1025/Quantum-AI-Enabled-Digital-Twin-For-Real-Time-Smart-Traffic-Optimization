"""Thin HTTP client: the dashboard talks to the FastAPI backend ONLY through these calls."""
from __future__ import annotations

import os

import requests

API_URL = os.environ.get("VAC_API_URL", "http://127.0.0.1:8000").rstrip("/")


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _request(method: str, path: str, timeout: float = 15, **kw):
    url = f"{API_URL}{path}"
    try:
        r = requests.request(method, url, timeout=timeout, **kw)
    except requests.ConnectionError:
        raise ApiError(f"Cannot reach the backend at {API_URL}. Start it with: "
                       f"uvicorn backend.main:app --host 127.0.0.1 --port 8000")
    except requests.Timeout:
        raise ApiError(f"The backend did not answer within {timeout}s ({path}).")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        if isinstance(detail, list):  # pydantic validation errors
            detail = "; ".join(str(d.get("msg", d)) for d in detail)
        raise ApiError(str(detail), r.status_code)
    ctype = r.headers.get("content-type", "")
    return r.json() if "application/json" in ctype else r.content


def get(path: str, **params):
    return _request("GET", path, params=params or None)


def post(path: str, payload: dict | None = None):
    return _request("POST", path, json=payload or {})


def delete(path: str):
    return _request("DELETE", path)


def download(path: str, timeout: float = 120) -> bytes:
    return _request("GET", path, timeout=timeout)


def try_get(path: str, **params):
    """Return (data, error_message). 404 'no data yet' is returned as (None, msg)."""
    try:
        return get(path, **params), None
    except ApiError as exc:
        return None, str(exc)
