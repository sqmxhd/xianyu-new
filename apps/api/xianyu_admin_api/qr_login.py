"""Short-lived, server-side Xianyu QR login sessions."""

from __future__ import annotations

import json
import logging
import random
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

import requests
from apps.runtime_paths import resource_path
from integrations.xianyu_core.identity import DEFAULT_CLIENT_IDENTITY

from .account_network import AccountNetworkPolicyError, validate_account_network_route
from .face_verification import (
    FaceVerificationChallenge,
    FaceVerificationError,
    poll_face_verification,
    prepare_face_verification,
)
from .schemas import AccountBrowserIdentityPayload, ProxyConfigPayload


LOGIN_PAGE_URL = "https://passport.goofish.com/mini_login.htm"
QR_GENERATE_URL = "https://passport.goofish.com/newlogin/qrcode/generate.do"
QR_QUERY_URL = "https://passport.goofish.com/newlogin/qrcode/query.do"
LOGIN_TOKEN_URL = "https://passport.goofish.com/login_token/login.do"
MTOP_BASE_URL = "https://h5api.m.goofish.com/h5"
USER_AGENT = DEFAULT_CLIENT_IDENTITY.user_agent
PASSPORT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": DEFAULT_CLIENT_IDENTITY.sec_ch_ua,
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
MTOP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.goofish.com",
    "Referer": "https://www.goofish.com/",
    "Content-Type": "application/x-www-form-urlencoded",
}
TFSTK_SCRIPT = resource_path(
    "third_party", "XianYuApis", "utils", "gen_tfstk.js"
)
logger = logging.getLogger(__name__)


class QRLoginError(RuntimeError):
    pass


class _TimeoutSession(requests.Session):
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (5, 20)
        return super().request(method, url, **kwargs)


@dataclass(slots=True)
class QRLoginSession:
    account_id: str | None
    account_name: str | None
    proxy_id: str | None
    proxy: ProxyConfigPayload
    browser_identity: AccountBrowserIdentityPayload = field(
        default_factory=AccountBrowserIdentityPayload
    )
    remark: str | None = None
    automation_owner_user_id: str | None = None
    ttl_seconds: int = 180
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    code_content: str = ""
    token_t: str = ""
    token_ck: str = ""
    login_token: str = ""
    status: str = "pending"
    finalized: bool = False
    runtime_state: str | None = None
    error: str | None = None
    challenge_type: str = "none"
    _csrf_token: str = ""
    _cna: str = ""
    _cookie2: str = ""
    _query_base: dict[str, Any] = field(default_factory=dict)
    _login_form_data: dict[str, Any] = field(default_factory=dict)
    _face_challenge: FaceVerificationChallenge | None = None
    face_code_content: str = ""
    _validated_cookie: str = ""
    _http: requests.Session = field(default_factory=_TimeoutSession)
    _lock: Lock = field(default_factory=Lock)

    @property
    def expires_in(self) -> int:
        return max(0, int(self.created_at + self.ttl_seconds - time.time()))

    def start(self) -> None:
        try:
            validate_account_network_route(self.proxy_id, self.proxy)
        except AccountNetworkPolicyError as exc:
            raise QRLoginError(str(exc)) from exc
        self._http.trust_env = False
        identity = self._client_identity()
        self._http.headers.update(
            {
                "User-Agent": identity.user_agent,
                "Accept-Language": identity.accept_language,
            }
        )
        if self.proxy.enabled:
            proxy_url = self._proxy_url()
            self._http.proxies.update({"http": proxy_url, "https": proxy_url})

        self._initialize_cookies()
        self._load_login_page()
        self._generate_qr_code()

    def _client_identity(self):
        from .account_identity import resolve_client_identity

        return resolve_client_identity(self.browser_identity)

    @property
    def _passport_headers(self) -> dict[str, str]:
        identity = self._client_identity()
        return {
            "User-Agent": identity.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": identity.accept_language,
            "sec-ch-ua": identity.sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{identity.sec_ch_ua_platform}"',
        }

    @property
    def _mtop_headers(self) -> dict[str, str]:
        identity = self._client_identity()
        return {
            "User-Agent": identity.user_agent,
            "Accept": "application/json",
            "Accept-Language": identity.accept_language,
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def poll(self) -> str:
        with self._lock:
            if self.status in {"completed", "error", "expired"}:
                return self.status
            if self.expires_in <= 0:
                self.status = "expired"
                return self.status
            if self.status == "finalizing":
                return self.status
            if self.status == "browser_verification":
                return self.status
            if self.status == "verification_required":
                if self._face_challenge is None:
                    raise QRLoginError("face verification session is incomplete")
                try:
                    verified = poll_face_verification(
                        self._http,
                        self._face_challenge,
                        self._passport_headers,
                    )
                except FaceVerificationError as exc:
                    raise QRLoginError(str(exc)) from exc
                if verified:
                    self.status = "finalizing"
                return self.status

            response = self._http.post(
                f"{QR_QUERY_URL}?appName=xianyu&fromSite=77",
                data={**self._query_base, "t": self.token_t, "ck": self.token_ck},
                headers={
                    **self._passport_headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://passport.goofish.com",
                    "Referer": LOGIN_PAGE_URL,
                },
            )
            response.raise_for_status()
            content = response.json().get("content", {})
            data = content.get("data", {}) if isinstance(content, dict) else {}
            raw_status = str(data.get("qrCodeStatus") or "UNKNOWN").upper()
            if raw_status == "CONFIRMED":
                self.login_token = str(data.get("token") or data.get("lgToken") or "")
                iframe_redirect = data.get("iframeRedirect")
                if iframe_redirect is True or str(iframe_redirect).lower() == "true":
                    self.login_token = ""
                    redirect_url = str(data.get("iframeRedirectUrl") or "")
                    if not redirect_url:
                        raise QRLoginError("Xianyu requested face verification without a redirect URL")
                    try:
                        self._face_challenge = prepare_face_verification(
                            self._http,
                            redirect_url,
                            self._passport_headers,
                        )
                    except FaceVerificationError as exc:
                        raise QRLoginError(str(exc)) from exc
                    self.face_code_content = self._face_challenge.code_content
                    self.challenge_type = "face"
                    self.created_at = time.time()
                    self.ttl_seconds = 300
                    self.status = "verification_required"
                elif self.login_token or self._cookie_value("unb", (".goofish.com", "goofish.com")):
                    self.status = "finalizing"
                else:
                    raise QRLoginError("Xianyu confirmed login without credentials or verification data")
            elif raw_status in {"SCANED", "SCANNED"}:
                self.status = "scanned"
            elif raw_status in {"EXPIRED", "CANCELED", "CANCELLED"}:
                self.status = "expired"
            else:
                self.status = "pending"
            return self.status

    def finalize_credentials(self) -> str:
        with self._lock:
            if self.status != "finalizing":
                raise QRLoginError(f"QR login session cannot be finalized from {self.status}")
            if self.login_token:
                response = self._http.post(
                    LOGIN_TOKEN_URL,
                    params={
                        "token": self.login_token,
                        "subFlow": "DIALOG_CHECK_LOGIN_RPC",
                        "nextCode": "0018",
                        "bizScene": "qrcode",
                        "confirm": "true",
                    },
                    data={"deviceId": self._cna},
                    headers={
                        **self._passport_headers,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://passport.goofish.com",
                        "Referer": LOGIN_PAGE_URL,
                    },
                )
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                content = payload.get("content", {}) if isinstance(payload, dict) else {}
                if isinstance(content, dict) and content.get("success") is False:
                    raise QRLoginError("Xianyu rejected the QR login token exchange")

            self._refresh_login_cookies()
            self._validate_access_token()
            self._validated_cookie = self._serialize_goofish_cookies()
            return self._validated_cookie

    def mark_completed(self, runtime_state: str | None = None) -> None:
        with self._lock:
            self.finalized = True
            self.runtime_state = runtime_state
            self.status = "completed"
            self.error = None

    def begin_browser_verification(self, ttl_seconds: int) -> None:
        with self._lock:
            self.status = "browser_verification"
            if self.challenge_type == "none":
                self.challenge_type = "interactive"
            self.created_at = time.time()
            self.ttl_seconds = ttl_seconds
            self.error = None

    def finalize_browser_credentials(self, cookies: list[dict[str, Any]]) -> str:
        """Validate browser cookies through the same platform token check as HTTP login."""
        with self._lock:
            self._http.cookies.clear()
            for cookie in cookies:
                name = str(cookie.get("name") or "")
                value = str(cookie.get("value") or "")
                domain = str(cookie.get("domain") or "")
                if not name or not value or not (
                    domain.endswith("goofish.com") or domain.endswith("mmstat.com")
                ):
                    continue
                self._http.cookies.set(
                    name,
                    value,
                    domain=domain,
                    path=str(cookie.get("path") or "/"),
                )
            self._refresh_login_cookies()
            self._validate_access_token()
            self._validated_cookie = self._serialize_goofish_cookies()
            return self._validated_cookie

    def fail(self, error: str) -> None:
        self.status = "error"
        self.error = error

    def close(self) -> None:
        self._http.close()

    def _initialize_cookies(self) -> None:
        response = self._http.get("https://log.mmstat.com/eg.js")
        response.raise_for_status()
        self._cna = self._cookie_value("cna", (".mmstat.com", "mmstat.com"))
        if self._cna:
            self._http.cookies.set("cna", self._cna, domain=".goofish.com", path="/")

        for api in (
            "mtop.taobao.idlehome.home.webpc.feed",
            "mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
        ):
            response = self._http.post(
                f"{MTOP_BASE_URL}/{api}/1.0/",
                params={
                    "jsv": "2.7.2",
                    "appKey": "34839810",
                    "t": str(int(time.time() * 1000)),
                    "sign": "",
                    "v": "1.0",
                    "type": "originaljson",
                    "dataType": "json",
                    "timeout": "20000",
                    "api": api,
                    "sessionOption": "AutoLoginOnly",
                    "spm_cnt": "a21ybx.home.0.0",
                },
                data="data=%7B%7D",
                headers=self._mtop_headers,
            )
            response.raise_for_status()

        tfstk = self._generate_tfstk()
        if tfstk:
            self._http.cookies.set("tfstk", tfstk, domain=".goofish.com", path="/")
        self._cookie2 = self._cookie_value("cookie2", (".goofish.com", "goofish.com"))

    def _load_login_page(self) -> None:
        response = self._http.get(
            LOGIN_PAGE_URL,
            params={
                "lang": "zh_cn",
                "appName": "xianyu",
                "appEntrance": "web",
                "styleType": "vertical",
                "bizParams": "",
                "notLoadSsoView": "false",
                "notKeepLogin": "false",
                "isMobile": "false",
                "qrCodeFirst": "false",
                "stie": "77",
                "rnd": str(random.random()),
            },
            headers={
                **self._passport_headers,
                "Referer": "https://www.goofish.com/",
                "sec-fetch-site": "same-site",
                "sec-fetch-dest": "iframe",
                "sec-fetch-mode": "navigate",
            },
        )
        response.raise_for_status()
        try:
            view_data = self._extract_view_data(response.text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise QRLoginError("Xianyu login page did not provide valid login form data") from exc
        login_form_data = view_data.get("loginFormData")
        if not isinstance(login_form_data, dict) or not login_form_data:
            raise QRLoginError("Xianyu login page did not provide login form data")
        self._login_form_data = dict(login_form_data)
        self._login_form_data["umidTag"] = "SERVER"
        self._csrf_token = self._cookie_value(
            "XSRF-TOKEN", ("passport.goofish.com", ".passport.goofish.com")
        )

    def _generate_qr_code(self) -> None:
        common = dict(self._login_form_data)
        response = self._http.get(
            QR_GENERATE_URL,
            params=common,
            headers={**self._passport_headers, "Referer": LOGIN_PAGE_URL},
        )
        response.raise_for_status()
        content = response.json().get("content", {})
        if not isinstance(content, dict) or not content.get("success"):
            raise QRLoginError("Xianyu rejected QR code generation")
        data = content.get("data", {})
        self.token_t = str(data.get("t") or "")
        self.token_ck = str(data.get("ck") or "")
        self.code_content = str(data.get("codeContent") or "")
        if not self.token_t or not self.token_ck or not self.code_content:
            raise QRLoginError("Xianyu returned incomplete QR login data")
        self._query_base = common

    def _refresh_login_cookies(self) -> None:
        api = "mtop.idle.web.user.page.nav"
        response = self._http.post(
            f"{MTOP_BASE_URL}/{api}/1.0/",
            params={
                "jsv": "2.7.2",
                "appKey": "34839810",
                "t": str(int(time.time() * 1000)),
                "sign": "",
                "v": "1.0",
                "type": "originaljson",
                "dataType": "json",
                "timeout": "20000",
                "api": api,
                "sessionOption": "AutoLoginOnly",
                "spm_cnt": "a21ybx.home.0.0",
            },
            data="data=%7B%7D",
            headers=self._mtop_headers,
        )
        response.raise_for_status()

    def _validate_access_token(self) -> None:
        cookie_map = self._goofish_cookie_map()
        missing = [key for key in ("unb", "_m_h5_tk") if not cookie_map.get(key)]
        if missing:
            raise QRLoginError(f"confirmed login is missing required cookies: {', '.join(missing)}")

        from integrations.xianyu_core.upstream import load_upstream_modules

        upstream = load_upstream_modules()
        api = upstream.XianyuApis(cookie_map, upstream.generate_device_id(cookie_map["unb"]))
        api.session.close()
        api.session = self._http
        token_response = api.get_token()
        token = (
            token_response.get("data", {}).get("accessToken")
            if isinstance(token_response, dict)
            else None
        )
        if not token:
            raise QRLoginError("confirmed login could not obtain a Xianyu access token")

    def _serialize_goofish_cookies(self) -> str:
        cookies = self._goofish_cookie_map()
        if not cookies.get("unb"):
            raise QRLoginError("validated login did not contain unb")
        return "; ".join(f"{key}={value}" for key, value in cookies.items())

    def _goofish_cookie_map(self) -> dict[str, str]:
        selected: dict[str, tuple[int, str]] = {}
        for cookie in self._http.cookies:
            domain = (cookie.domain or "").lower()
            if not (domain.endswith("goofish.com") or domain.endswith("mmstat.com")):
                continue
            priority = 3 if domain == ".goofish.com" else 2 if domain.endswith("goofish.com") else 1
            existing = selected.get(cookie.name)
            if existing is None or priority >= existing[0]:
                selected[cookie.name] = (priority, cookie.value)
        return {name: value for name, (_, value) in selected.items() if value}

    def _cookie_value(self, name: str, domains: tuple[str, ...]) -> str:
        for domain in domains:
            for cookie in self._http.cookies:
                if cookie.name == name and cookie.domain == domain:
                    return cookie.value
        for cookie in self._http.cookies:
            if cookie.name == name:
                return cookie.value
        return ""

    @staticmethod
    def _generate_tfstk() -> str:
        if not TFSTK_SCRIPT.exists():
            return ""
        try:
            result = subprocess.run(
                ["node", str(TFSTK_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("tfstk generation failed: %s", exc)
            return ""
        return result.stdout.strip()

    def _proxy_url(self) -> str:
        if not self.proxy.host or not self.proxy.port:
            raise QRLoginError("selected proxy is incomplete")
        auth = ""
        if self.proxy.username:
            auth = quote(self.proxy.username, safe="")
            if self.proxy.password:
                auth += f":{quote(self.proxy.password, safe='')}"
            auth += "@"
        return f"{self.proxy.scheme}://{auth}{self.proxy.host}:{self.proxy.port}"

    @staticmethod
    def _extract_view_data(document: str) -> dict[str, Any]:
        assignment = re.search(r"window\.viewData\s*=", document)
        if assignment is None:
            raise ValueError("window.viewData was not found")
        object_index = document.find("{", assignment.end())
        if object_index < 0:
            raise ValueError("window.viewData object was not found")
        value, _ = json.JSONDecoder().raw_decode(document[object_index:])
        if not isinstance(value, dict):
            raise ValueError("window.viewData is not an object")
        return value
