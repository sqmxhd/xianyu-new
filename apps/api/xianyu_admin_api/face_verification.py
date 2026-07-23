"""Pure-HTTP handling for Xianyu QR-login identity verification."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests


PASSPORT_ORIGIN = "https://passport.goofish.com"
FACE_CHECK_URL = f"{PASSPORT_ORIGIN}/iv/photoVerify/check.do"


class FaceVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FaceVerificationChallenge:
    htoken: str
    code_content: str
    referer: str


def prepare_face_verification(
    http: requests.Session,
    redirect_url: str,
    headers: dict[str, str],
) -> FaceVerificationChallenge:
    """Follow the verification entry pages and extract the phone QR content."""
    entry_url = _passport_url(redirect_url)
    response = http.get(entry_url, headers=headers)
    response.raise_for_status()
    normal_html = response.text

    htoken_match = re.search(r"htoken=([A-Za-z0-9_-]+)", normal_html)
    if not htoken_match:
        raise FaceVerificationError("Xianyu face verification did not provide htoken")
    htoken = htoken_match.group(1)

    modes_match = re.search(
        r"window\.location\.href\s*=\s*[\"']([^\"']*?/iv/mini/verify_modes\.htm\?[^\"']*)[\"']",
        normal_html,
    )
    if not modes_match:
        raise FaceVerificationError("Xianyu face verification did not provide a verification mode URL")
    modes_url = html.unescape(modes_match.group(1))
    if modes_url.endswith("_umidfg="):
        modes_url += "1"
    modes_url = _passport_url(urljoin(entry_url, modes_url))

    response = http.get(modes_url, headers=headers)
    response.raise_for_status()
    _validate_response_url(response, modes_url)

    qr_match = re.search(
        r"new\s+Qrcode\(\{\s*text:\s*\"((?:\\.|[^\"])*)\"",
        response.text,
    )
    if not qr_match:
        raise FaceVerificationError("Xianyu face verification did not provide a QR code")
    try:
        code_content = json.loads(f'"{qr_match.group(1)}"')
    except json.JSONDecodeError as exc:
        raise FaceVerificationError("Xianyu returned an invalid face verification QR code") from exc
    if not isinstance(code_content, str) or not code_content:
        raise FaceVerificationError("Xianyu returned an empty face verification QR code")
    code_content = html.unescape(code_content)

    referer = str(getattr(response, "url", "") or modes_url)
    return FaceVerificationChallenge(htoken=htoken, code_content=code_content, referer=referer)


def poll_face_verification(
    http: requests.Session,
    challenge: FaceVerificationChallenge,
    headers: dict[str, str],
) -> bool:
    """Poll once and finish the server-side login redirect when verification passes."""
    response = http.get(
        FACE_CHECK_URL,
        params={"htoken": challenge.htoken},
        headers={
            **headers,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": challenge.referer,
        },
    )
    response.raise_for_status()
    try:
        payload: Any = response.json()
    except ValueError as exc:
        raise FaceVerificationError("Xianyu face verification returned a non-JSON response") from exc
    content = payload.get("content", {}) if isinstance(payload, dict) else {}
    code = str(content.get("code") or "") if isinstance(content, dict) else ""
    if code == "0":
        return False
    if code != "3":
        return False

    completion_url = str(content.get("url") or "")
    if not completion_url:
        raise FaceVerificationError("Xianyu confirmed face verification without a completion URL")
    completion_url = _passport_url(urljoin(PASSPORT_ORIGIN, completion_url))
    response = http.get(completion_url, headers=headers)
    response.raise_for_status()
    _validate_response_url(response, completion_url)
    return True


def _passport_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "passport.goofish.com"
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise FaceVerificationError("Xianyu returned an unsafe face verification URL")
    return value


def _validate_response_url(response: requests.Response, fallback: str) -> None:
    final_url = str(getattr(response, "url", "") or fallback)
    parsed = urlsplit(final_url)
    hostname = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not (hostname == "goofish.com" or hostname.endswith(".goofish.com"))
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise FaceVerificationError("Xianyu face verification redirected to an unsafe URL")
