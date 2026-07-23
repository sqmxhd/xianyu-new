"""Pure HTTP renewal for Xianyu login cookies."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests
from integrations.xianyu_core.identity import ClientIdentity, DEFAULT_CLIENT_IDENTITY

from .schemas import ProxyConfigPayload


HAS_LOGIN_URL = "https://passport.goofish.com/newlogin/hasLogin.do"
SILENT_HAS_LOGIN_URL = "https://passport.goofish.com/newlogin/silentHasLogin.do"
SET_LOGIN_SETTINGS_URL = "https://passport.goofish.com/ac/account/setLoginSettings.do"
MTOP_NAV_URL = (
    "https://h5api.m.goofish.com/h5/mtop.idle.web.user.page.nav/1.0/"
)
KEEPALIVE_URL = (
    "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.loginuser.get/1.0/"
)
USER_AGENT = DEFAULT_CLIENT_IDENTITY.user_agent
PASSPORT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Origin": "https://www.goofish.com",
    "Referer": "https://www.goofish.com/",
}
MTOP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.goofish.com",
    "Referer": "https://www.goofish.com/",
}


class CookieRenewalError(RuntimeError):
    """A renewal failure that is safe to persist and return to the UI."""

    def __init__(self, message: str, *, kind: str = "failed") -> None:
        super().__init__(message)
        self.kind = kind


class _TimeoutSession(requests.Session):
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (5, 20)
        return super().request(method, url, **kwargs)


@dataclass(frozen=True, slots=True)
class CookieRenewalResult:
    new_cookie: str
    updated_cookie_names: list[str] = field(default_factory=list)
    message: str = "Cookie 续期成功"


class CookieRenewalService:
    """Renew a Xianyu login using only the platform's HTTP endpoints."""

    def __init__(
        self,
        session_factory: Callable[[], requests.Session] = _TimeoutSession,
        access_token_validator: Callable[[requests.Session, dict[str, str]], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._access_token_validator = access_token_validator or self._validate_access_token

    def renew(
        self,
        cookie: str,
        proxy: ProxyConfigPayload | None = None,
        identity: ClientIdentity | None = None,
    ) -> CookieRenewalResult:
        client_identity = identity or DEFAULT_CLIENT_IDENTITY
        passport_headers = self._passport_headers(client_identity)
        mtop_headers = self._mtop_headers(client_identity)
        original = parse_cookie_header(cookie)
        original_unb = original.get("unb", "")
        if not original_unb:
            raise CookieRenewalError("Cookie 缺少 unb，需要重新登录", kind="auth_expired")

        http = self._session_factory()
        try:
            http.trust_env = False
            http.headers.update(
                {
                    "User-Agent": client_identity.user_agent,
                    "Accept-Language": client_identity.accept_language,
                }
            )
            for name, value in original.items():
                http.cookies.set(name, value, domain=".goofish.com", path="/")
            if proxy and proxy.enabled:
                proxy_url = self._proxy_url(proxy)
                http.proxies.update({"http": proxy_url, "https": proxy_url})

            step_messages: list[str] = []
            self._call_has_login(http, original, step_messages, passport_headers)
            self._call_silent_has_login(http, step_messages, passport_headers)
            self._call_set_login_settings(http, step_messages, passport_headers)
            self._refresh_mtop_cookie(http, mtop_headers)

            renewed = session_cookie_map(http)
            if renewed.get("unb") != original_unb:
                raise CookieRenewalError(
                    "续期返回的账户标识不一致，已拒绝覆盖原 Cookie",
                    kind="auth_expired",
                )
            if not renewed.get("_m_h5_tk"):
                raise CookieRenewalError(
                    "续期后缺少 _m_h5_tk，需要重新登录",
                    kind="auth_expired",
                )

            self._access_token_validator(http, renewed)
            renewed = session_cookie_map(http)
            if renewed.get("unb") != original_unb:
                raise CookieRenewalError(
                    "访问令牌校验返回了不同账户，已拒绝覆盖原 Cookie",
                    kind="auth_expired",
                )

            new_cookie = serialize_cookie_map(renewed)
            updated_names = sorted(
                name
                for name in set(original) | set(renewed)
                if original.get(name) != renewed.get(name)
            )
            detail = "、".join(step_messages) if step_messages else "登录状态已验证"
            return CookieRenewalResult(
                new_cookie=new_cookie,
                updated_cookie_names=updated_names,
                message=f"Cookie 续期成功（{detail}）",
            )
        except CookieRenewalError:
            raise
        except requests.exceptions.ProxyError as exc:
            raise CookieRenewalError("账户代理连接失败", kind="proxy_failed") from exc
        except requests.exceptions.Timeout as exc:
            raise CookieRenewalError("闲鱼续期接口请求超时", kind="failed") from exc
        except requests.exceptions.RequestException as exc:
            raise CookieRenewalError("闲鱼续期接口网络请求失败", kind="failed") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise CookieRenewalError("闲鱼续期接口返回异常", kind="failed") from exc
        finally:
            http.close()

    def keep_alive(
        self,
        cookie: str,
        proxy: ProxyConfigPayload | None = None,
        identity: ClientIdentity | None = None,
    ) -> CookieRenewalResult:
        """Run the low-cost loginuser probe and retain any Set-Cookie updates."""

        original = parse_cookie_header(cookie)
        original_unb = original.get("unb", "")
        token_cookie = original.get("_m_h5_tk", "")
        if not original_unb or not token_cookie:
            raise CookieRenewalError(
                "Cookie 缺少平台验证字段，需要重新登录",
                kind="auth_expired",
            )
        client_identity = identity or DEFAULT_CLIENT_IDENTITY
        mtop_headers = self._mtop_headers(client_identity)
        http = self._session_factory()
        try:
            http.trust_env = False
            http.headers.update(
                {
                    "User-Agent": client_identity.user_agent,
                    "Accept-Language": client_identity.accept_language,
                }
            )
            for name, value in original.items():
                http.cookies.set(name, value, domain=".goofish.com", path="/")
            if proxy and proxy.enabled:
                proxy_url = self._proxy_url(proxy)
                http.proxies.update({"http": proxy_url, "https": proxy_url})

            timestamp = str(int(time.time() * 1000))
            data_value = "{}"
            from integrations.xianyu_core.upstream import load_upstream_modules

            upstream = load_upstream_modules()
            response = http.post(
                KEEPALIVE_URL,
                params={
                    "jsv": "2.7.2",
                    "appKey": "34839810",
                    "t": timestamp,
                    "sign": upstream.generate_sign(
                        timestamp,
                        token_cookie.split("_", 1)[0],
                        data_value,
                    ),
                    "v": "1.0",
                    "type": "originaljson",
                    "accountSite": "xianyu",
                    "dataType": "json",
                    "timeout": "20000",
                    "api": "mtop.taobao.idlemessage.pc.loginuser.get",
                    "sessionOption": "AutoLoginOnly",
                    "spm_cnt": "a21ybx.im.0.0",
                },
                data={"data": data_value},
                headers=mtop_headers,
            )
            response.raise_for_status()
            _flatten_response_cookies(http, response)
            payload = response.json()
            ret = payload.get("ret") if isinstance(payload, dict) else None
            entries = ret if isinstance(ret, list) else [ret] if ret else []
            response_text = " ".join(str(entry) for entry in entries)
            if not any("SUCCESS" in str(entry).upper() for entry in entries):
                upper = response_text.upper()
                if "FAIL_SYS_SESSION_EXPIRED" in upper or "Session过期" in response_text:
                    raise CookieRenewalError(
                        "闲鱼平台会话已过期，需要重新登录",
                        kind="auth_expired",
                    )
                if any(marker in upper for marker in ("VALIDATE", "RGV587", "CAPTCHA")):
                    raise CookieRenewalError(
                        "闲鱼平台要求完成安全验证",
                        kind="verification_required",
                    )
                raise CookieRenewalError(
                    f"Cookie 轻量验证失败：{response_text[:200] or '平台返回异常'}",
                    kind="failed",
                )

            renewed = session_cookie_map(http)
            if renewed.get("unb") != original_unb:
                raise CookieRenewalError(
                    "轻量验证返回的账户标识不一致，已拒绝保存",
                    kind="auth_expired",
                )
            new_cookie = serialize_cookie_map(renewed)
            return CookieRenewalResult(
                new_cookie=new_cookie,
                updated_cookie_names=sorted(
                    name
                    for name in set(original) | set(renewed)
                    if original.get(name) != renewed.get(name)
                ),
                message="Cookie 轻量保活验证成功",
            )
        except CookieRenewalError:
            raise
        except requests.exceptions.ProxyError as exc:
            raise CookieRenewalError("账户代理连接失败", kind="proxy_failed") from exc
        except requests.exceptions.Timeout as exc:
            raise CookieRenewalError("Cookie 轻量验证请求超时", kind="failed") from exc
        except requests.exceptions.RequestException as exc:
            raise CookieRenewalError("Cookie 轻量验证网络请求失败", kind="failed") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise CookieRenewalError("Cookie 轻量验证返回异常", kind="failed") from exc
        finally:
            http.close()

    def _call_has_login(
        self,
        http: requests.Session,
        original: dict[str, str],
        messages: list[str],
        passport_headers: dict[str, str],
    ) -> None:
        now_ms = int(time.time() * 1000)
        response = http.post(
            HAS_LOGIN_URL,
            params={"appName": "xianyu", "fromSite": "77"},
            data={
                "hid": original["unb"],
                "ltl": "true",
                "appName": "xianyu",
                "appEntrance": "web",
                "_csrf_token": original.get("_tb_token_", ""),
                "umidToken": original.get("_uab_collina") or original.get("cna", ""),
                "hsiz": original.get("cookie2", ""),
                "bizParams": "taobaoBizLoginFrom=web&renderRefer=https%3A%2F%2Fwww.goofish.com%2F",
                "mainPage": "false",
                "isMobile": "false",
                "lang": "zh_CN",
                "returnUrl": "",
                "fromSite": "77",
                "isIframe": "true",
                "documentReferer": "https://www.goofish.com/",
                "defaultView": "hasLogin",
                "umidTag": "SERVER",
                "deviceId": "",
                "pageTraceId": f"21504{now_ms}{random.randint(100000, 999999)}",
            },
            headers={
                **passport_headers,
                "Content-Type": "application/x-www-form-urlencoded",
                **(
                    {"x-xsrf-token": original["XSRF-TOKEN"]}
                    if original.get("XSRF-TOKEN")
                    else {}
                ),
            },
            allow_redirects=False,
        )
        self._check_http_status(response, "hasLogin")
        _flatten_response_cookies(http, response)
        if self._business_success(response):
            messages.append("登录态确认")

    def _call_silent_has_login(
        self,
        http: requests.Session,
        messages: list[str],
        passport_headers: dict[str, str],
    ) -> None:
        response = http.post(
            SILENT_HAS_LOGIN_URL,
            params={
                "documentReferer": "https://www.goofish.com/",
                "appName": "xianyu",
                "appEntrance": "xianyu_sdkSilent",
                "fromSite": "0",
                "ltl": "true",
            },
            headers=passport_headers,
            allow_redirects=False,
        )
        self._check_http_status(response, "silentHasLogin")
        _flatten_response_cookies(http, response)
        if self._business_success(response):
            messages.append("静默登录刷新")

    def _call_set_login_settings(
        self,
        http: requests.Session,
        messages: list[str],
        passport_headers: dict[str, str],
    ) -> None:
        before = session_cookie_map(http)
        response = http.post(
            SET_LOGIN_SETTINGS_URL,
            params={"fromSite": "77", "appName": "xianyu", "bizEntrance": "web"},
            data={"status": "0"},
            headers={**passport_headers, "Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
        )
        self._check_http_status(response, "setLoginSettings")
        _flatten_response_cookies(http, response)
        after = session_cookie_map(http)
        if before != after:
            messages.append("长期登录刷新")

    @staticmethod
    def _refresh_mtop_cookie(
        http: requests.Session,
        mtop_headers: dict[str, str],
    ) -> None:
        api = "mtop.idle.web.user.page.nav"
        response = http.post(
            MTOP_NAV_URL,
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
            headers=mtop_headers,
        )
        response.raise_for_status()
        _flatten_response_cookies(http, response)

    @staticmethod
    def _validate_access_token(http: requests.Session, cookies: dict[str, str]) -> None:
        from integrations.xianyu_core.upstream import load_upstream_modules

        upstream = load_upstream_modules()
        api = upstream.XianyuApis(cookies, upstream.generate_device_id(cookies["unb"]))
        api.session.close()
        api.session = http
        token_response = api.get_token()
        token = (
            token_response.get("data", {}).get("accessToken")
            if isinstance(token_response, dict)
            else None
        )
        if not token:
            raise CookieRenewalError(
                "Cookie 无法获取闲鱼 access token，需要重新登录",
                kind="auth_expired",
            )

    @staticmethod
    def _passport_headers(identity: ClientIdentity) -> dict[str, str]:
        return {
            "User-Agent": identity.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": identity.accept_language,
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        }

    @staticmethod
    def _mtop_headers(identity: ClientIdentity) -> dict[str, str]:
        return {
            "User-Agent": identity.user_agent,
            "Accept": "application/json",
            "Accept-Language": identity.accept_language,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        }

    @staticmethod
    def _check_http_status(response: requests.Response, step: str) -> None:
        if response.status_code not in {200, 302, 303}:
            raise CookieRenewalError(f"{step} 返回 HTTP {response.status_code}")

    @staticmethod
    def _business_success(response: requests.Response) -> bool:
        try:
            payload = response.json()
        except ValueError:
            return False
        content = payload.get("content") if isinstance(payload, dict) else None
        return isinstance(content, dict) and bool(content.get("success"))

    @staticmethod
    def _proxy_url(proxy: ProxyConfigPayload) -> str:
        if not proxy.host or not proxy.port:
            raise CookieRenewalError("账户代理配置不完整", kind="proxy_failed")
        auth = ""
        if proxy.username:
            auth = quote(proxy.username, safe="")
            if proxy.password:
                auth += f":{quote(proxy.password, safe='')}"
            auth += "@"
        return f"{proxy.scheme}://{auth}{proxy.host}:{proxy.port}"


def parse_cookie_header(cookie: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in (cookie or "").replace("\r", "").replace("\n", "").split(";"):
        pair = item.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        name = name.strip()
        if name:
            parsed[name] = value.strip()
    return parsed


def _flatten_response_cookies(http: requests.Session, response: requests.Response) -> None:
    """Keep one value per name so host-only cookies can replace flattened input."""

    for response_cookie in list(response.cookies):
        for existing in list(http.cookies):
            if existing.name != response_cookie.name:
                continue
            try:
                http.cookies.clear(existing.domain, existing.path, existing.name)
            except KeyError:
                pass
        if response_cookie.value and not response_cookie.is_expired():
            http.cookies.set(
                response_cookie.name,
                response_cookie.value,
                domain=".goofish.com",
                path="/",
            )


def session_cookie_map(http: requests.Session) -> dict[str, str]:
    selected: dict[str, tuple[int, str]] = {}
    for cookie in http.cookies:
        domain = (cookie.domain or "").lower()
        if domain and not (domain.endswith("goofish.com") or domain.endswith("mmstat.com")):
            continue
        priority = 3 if domain == ".goofish.com" else 2 if domain.endswith("goofish.com") else 1
        existing = selected.get(cookie.name)
        if existing is None or priority >= existing[0]:
            selected[cookie.name] = (priority, cookie.value)
    return {name: value for name, (_, value) in selected.items() if value}


def serialize_cookie_map(cookies: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if name and value)
