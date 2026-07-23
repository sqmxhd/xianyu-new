"""Isolated loader for upstream XianYuApis helpers.

XianYuApis is pinned as vendored source under
``third_party/XianYuApis``. It uses top-level module names such as ``utils`` and
``message``; this loader imports only the required symbols and restores any
pre-existing modules with the same names afterwards.
"""

from __future__ import annotations

import importlib
import hashlib
import os
import random
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from .protocol_worker import get_protocol_decryptor


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UPSTREAM_ROOT = REPO_ROOT / "third_party" / "XianYuApis"

_UPSTREAM_MODULE_NAMES = (
    "goofish_apis",
    "utils",
    "utils.goofish_utils",
    "message",
    "message.types",
)
DEFAULT_PLATFORM_HTTP_TIMEOUT = (5, 20)
MAX_IM_TOKEN_ATTEMPTS = 2


def _install_default_http_timeout(session: Any) -> None:
    """Give upstream requests sessions a real connect/read deadline."""

    if getattr(session, "_xianyu_default_timeout_installed", False):
        return
    original_request: Callable[..., Any] = session.request

    def request_with_timeout(method: str, url: str, **kwargs: Any) -> Any:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = DEFAULT_PLATFORM_HTTP_TIMEOUT
        return original_request(method, url, **kwargs)

    session.request = request_with_timeout
    session._xianyu_default_timeout_installed = True


def _harden_upstream_api_class(base: type[Any]) -> type[Any]:
    class HardenedXianyuApis(base):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            _install_default_http_timeout(self.session)
            self._xianyu_token_attempt_state = threading.local()

        def get_token(self) -> Any:
            state = self._xianyu_token_attempt_state
            depth = int(getattr(state, "depth", 0))
            if depth >= MAX_IM_TOKEN_ATTEMPTS:
                raise RuntimeError(
                    "IM token request remained expired after bounded refresh attempts"
                )
            state.depth = depth + 1
            try:
                return super().get_token()
            finally:
                state.depth = depth

    HardenedXianyuApis.__name__ = base.__name__
    HardenedXianyuApis.__qualname__ = base.__qualname__
    HardenedXianyuApis.__module__ = base.__module__
    return HardenedXianyuApis


def _generate_mid() -> str:
    return f"{random.randrange(1000)}{int(time.time() * 1000)} 0"


def _generate_uuid() -> str:
    return f"-{int(time.time() * 1000)}1"


def _generate_device_id(user_id: str) -> str:
    return f"{str(uuid.uuid4()).upper()}-{user_id}"


def _generate_sign(timestamp: str, token: str, data: str) -> str:
    value = f"{token}&{timestamp}&34839810&{data}"
    return hashlib.md5(value.encode("utf-8")).hexdigest()  # noqa: S324 - platform signature


@dataclass(frozen=True, slots=True)
class UpstreamModules:
    """Symbols imported from XianYuApis and used by the adapter."""

    XianyuApis: type[Any]
    decrypt: Any
    generate_device_id: Any
    generate_mid: Any
    generate_sign: Any
    generate_uuid: Any
    get_session_cookies_str: Any
    trans_cookies: Any


@contextmanager
def _temporary_import_root(path: Path):
    path_str = str(path)
    previous_cwd = os.getcwd()
    previous_modules: dict[str, ModuleType | None] = {
        name: sys.modules.get(name) for name in _UPSTREAM_MODULE_NAMES
    }
    inserted = False
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous_cwd)
        if inserted:
            try:
                sys.path.remove(path_str)
            except ValueError:
                pass

        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def load_upstream_modules(upstream_root: Path | None = None) -> UpstreamModules:
    """Load required upstream symbols without leaking top-level module names."""

    root = (upstream_root or DEFAULT_UPSTREAM_ROOT).resolve()
    if not root.exists():
        raise FileNotFoundError(f"XianYuApis upstream root not found: {root}")

    with _temporary_import_root(root):
        goofish_apis = importlib.import_module("goofish_apis")
        goofish_utils = importlib.import_module("utils.goofish_utils")
        decrypt = get_protocol_decryptor(root / "static" / "goofish_js_version_2.js")

        # These are exact equivalents of the tiny helpers in the upstream JS
        # bundle. Keeping them in-process avoids spawning Node for every IM ACK.
        goofish_utils.generate_device_id = _generate_device_id
        goofish_utils.generate_mid = _generate_mid
        goofish_utils.generate_sign = _generate_sign
        goofish_utils.generate_uuid = _generate_uuid
        goofish_apis.generate_device_id = _generate_device_id
        goofish_apis.generate_sign = _generate_sign

        return UpstreamModules(
            XianyuApis=_harden_upstream_api_class(goofish_apis.XianyuApis),
            decrypt=decrypt,
            generate_device_id=_generate_device_id,
            generate_mid=_generate_mid,
            generate_sign=_generate_sign,
            generate_uuid=_generate_uuid,
            get_session_cookies_str=goofish_utils.get_session_cookies_str,
            trans_cookies=goofish_utils.trans_cookies,
        )
