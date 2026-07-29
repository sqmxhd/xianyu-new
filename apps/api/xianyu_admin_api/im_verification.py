"""Human-in-the-loop verification and account-scoped visual browser sessions."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import shutil
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import quote

from integrations.xianyu_core.identity import ClientIdentity
from integrations.xianyu_core.upstream import load_upstream_modules

from .account_network import (
    AccountNetworkPolicyError,
    account_network_mode,
    validate_account_network_route,
)
from .browser_profiles import BrowserProfileBusyError, browser_profile_storage
from .browser_binaries import (
    BrowserBinaryError,
    browser_binary_manager,
    standard_browser_binary_manager,
)
from .platform_runtime import (
    is_root_process,
    iter_process_arguments,
    system_browser_candidates,
)
from .account_identity import resolve_client_identity
from .cookie_renewal import CookieRenewalError
from .executors import run_browser_blocking, run_platform_blocking, run_qr_blocking
from .qr_login import LOGIN_PAGE_URL, QRLoginError, QRLoginSession
from .schemas import (
    AccountBrowserSessionPayload,
    BrowserFingerprintSnapshotPayload,
    BrowserProfilePayload,
    IMVerificationPayload,
    ProxyConfigPayload,
    XianyuQRBrowserVerificationPayload,
)
from .settings import settings
from .socks_bridge import SocksBridge
from .store import AccountRecord, AccountStore


logger = logging.getLogger(__name__)


FINGERPRINT_PROBE_SCRIPT = r"""
async (options = {}) => {
  const digest = (value) => {
    const text = String(value ?? '');
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (`00000000${(hash >>> 0).toString(16)}`).slice(-8);
  };
  const safe = async (callback, fallback = null) => {
    try { return await callback(); } catch (_) { return fallback; }
  };

  const canvasHash = await safe(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 80;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 320, 80);
    gradient.addColorStop(0, '#f60');
    gradient.addColorStop(1, '#069');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 320, 80);
    ctx.font = '18px Arial';
    ctx.fillStyle = 'rgba(255,255,255,.86)';
    ctx.fillText('Xianyu fingerprint 你好 0123456789', 8, 34);
    ctx.strokeStyle = '#6cf';
    ctx.beginPath();
    ctx.arc(270, 40, 24, 0, Math.PI * 2);
    ctx.stroke();
    return digest(canvas.toDataURL());
  });

  const webgl = await safe(async () => {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return { vendor: null, renderer: null, hash: null };
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    const vendor = extension
      ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL)
      : gl.getParameter(gl.VENDOR);
    const renderer = extension
      ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER);
    const details = [
      vendor,
      renderer,
      gl.getParameter(gl.VERSION),
      gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
      gl.getParameter(gl.MAX_TEXTURE_SIZE),
      gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
    ];
    return { vendor: String(vendor || ''), renderer: String(renderer || ''), hash: digest(details.join('|')) };
  }, { vendor: null, renderer: null, hash: null });

  const audioHash = await safe(async () => {
    const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    if (!Offline) return null;
    const context = new Offline(1, 44100, 44100);
    const oscillator = context.createOscillator();
    const compressor = context.createDynamicsCompressor();
    oscillator.type = 'triangle';
    oscillator.frequency.value = 10000;
    compressor.threshold.value = -50;
    compressor.knee.value = 40;
    compressor.ratio.value = 12;
    compressor.attack.value = 0;
    compressor.release.value = 0.25;
    oscillator.connect(compressor);
    compressor.connect(context.destination);
    oscillator.start(0);
    const rendered = await context.startRendering();
    const samples = rendered.getChannelData(0);
    const values = [];
    for (let index = 0; index < samples.length; index += 97) values.push(samples[index].toFixed(7));
    return digest(values.join(','));
  });

  const fontResult = await safe(async () => {
    const candidates = [
      'Arial', 'Arial Unicode MS', 'Calibri', 'Cambria', 'Consolas',
      'Courier New', 'Helvetica', 'Microsoft YaHei', 'PingFang SC',
      'Segoe UI', 'SimSun', 'Times New Roman', 'Ubuntu', 'Noto Sans CJK SC'
    ];
    const detected = [];
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const sample = 'mmmmmmmmmmlliWW0123456789';
    const bases = ['monospace', 'sans-serif', 'serif'];
    const baseline = new Map();
    for (const base of bases) {
      ctx.font = `72px ${base}`;
      baseline.set(base, ctx.measureText(sample).width);
    }
    for (const font of candidates) {
      const available = bases.some((base) => {
        ctx.font = `72px "${font}",${base}`;
        return ctx.measureText(sample).width !== baseline.get(base);
      });
      if (available) detected.push(font);
    }
    return { detected, hash: digest(detected.join('|')) };
  }, { detected: [], hash: null });

  const clientRectsHash = await safe(async () => {
    const element = document.createElement('div');
    element.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:237.5px;font:15.25px Arial;letter-spacing:.17px';
    element.innerHTML = '<span>ClientRects 你好</span><span style="font-size:19.5px">0123456789</span>';
    document.documentElement.appendChild(element);
    const values = [...element.querySelectorAll('span')].flatMap((item) =>
      [...item.getClientRects()].flatMap((rect) =>
        [rect.x, rect.y, rect.width, rect.height].map((number) => Number(number).toFixed(4))
      )
    );
    element.remove();
    return digest(values.join('|'));
  });

  const webrtcApiAvailable = typeof RTCPeerConnection === 'function';
  const webrtc = await safe(async () => {
    if (!webrtcApiAvailable) {
      return { types: [], addresses: [], gatheringState: 'unavailable', privateCandidate: false, publicCandidate: false, blocked: true };
    }
    const iceServers = options.stunUrl ? [{ urls: options.stunUrl }] : [];
    const peer = new RTCPeerConnection({ iceServers });
    const types = new Set();
    const addresses = new Set();
    let privateCandidate = false;
    let publicCandidate = false;
    peer.createDataChannel('probe');
    peer.onicecandidate = (event) => {
      const item = event.candidate;
      const candidate = item && item.candidate;
      const match = candidate && candidate.match(/ typ ([a-z]+)/i);
      if (match) types.add(match[1].toLowerCase());
      const address = String((item && item.address) || (candidate && candidate.split(' ')[4]) || '').toLowerCase();
      const isPrivate = /^(10\.|127\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(address)
        || /^(fc|fd|fe80):/.test(address);
      const isMdns = address.endsWith('.local');
      if (isPrivate) privateCandidate = true;
      const isIPv4 = /^\d+\.\d+\.\d+\.\d+$/.test(address);
      const isIPv6 = address.includes(':') && /^[0-9a-f:]+$/i.test(address);
      if (address && !isPrivate && !isMdns && (isIPv4 || isIPv6)) {
        publicCandidate = true;
        addresses.add(address);
      }
    };
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    await Promise.race([
      new Promise((resolve) => {
        if (peer.iceGatheringState === 'complete') resolve(undefined);
        else peer.addEventListener('icegatheringstatechange', () => {
          if (peer.iceGatheringState === 'complete') resolve(undefined);
        });
      }),
      new Promise((resolve) => setTimeout(resolve, options.stunUrl ? 1800 : 500)),
    ]);
    const gatheringState = peer.iceGatheringState;
    peer.close();
    return { types: [...types].sort(), addresses: [...addresses].sort(), gatheringState, privateCandidate, publicCandidate, blocked: false };
  }, { types: [], addresses: [], gatheringState: 'failed', privateCandidate: false, publicCandidate: false, blocked: true });

  const automationWindowMarkers = Object.getOwnPropertyNames(window)
    .filter((name) => /playwright|puppeteer|selenium|webdriver|__pw/i.test(name))
    .slice(0, 20);
  const notificationPermission = await safe(async () => {
    if (!navigator.permissions || typeof navigator.permissions.query !== 'function') return null;
    const result = await navigator.permissions.query({ name: 'notifications' });
    return result && result.state ? result.state : null;
  });
  const iframeWebdriver = await safe(async () => {
    const frame = document.createElement('iframe');
    frame.style.display = 'none';
    document.documentElement.appendChild(frame);
    const value = frame.contentWindow && frame.contentWindow.navigator
      ? frame.contentWindow.navigator.webdriver
      : null;
    frame.remove();
    return typeof value === 'boolean' ? value : null;
  });
  const workerWebdriver = await safe(async () => {
    if (typeof Worker !== 'function') return null;
    const source = 'self.postMessage(typeof navigator.webdriver === "boolean" ? navigator.webdriver : null)';
    const workerUrl = URL.createObjectURL(new Blob([source], { type: 'text/javascript' }));
    try {
      return await new Promise((resolve) => {
        const worker = new Worker(workerUrl);
        const timer = setTimeout(() => { worker.terminate(); resolve(null); }, 500);
        worker.onmessage = (event) => {
          clearTimeout(timer);
          worker.terminate();
          resolve(typeof event.data === 'boolean' ? event.data : null);
        };
        worker.onerror = () => { clearTimeout(timer); worker.terminate(); resolve(null); };
      });
    } finally {
      URL.revokeObjectURL(workerUrl);
    }
  });
  const cdpStackProbeDetected = await safe(async () => {
    let detected = false;
    const error = new Error('cdp-probe');
    Object.defineProperty(error, 'stack', {
      configurable: true,
      get() { detected = true; return 'cdp-probe'; },
    });
    console.debug(error);
    await new Promise((resolve) => setTimeout(resolve, 80));
    return detected;
  }, null);

  const uaData = navigator.userAgentData;
  return {
    observedPlatform: navigator.platform || null,
    userAgent: navigator.userAgent,
    uaChPlatform: uaData ? uaData.platform : null,
    uaChBrands: uaData && Array.isArray(uaData.brands)
      ? uaData.brands.map((item) => `${item.brand}/${item.version}`)
      : [],
    language: navigator.language || null,
    languages: Array.isArray(navigator.languages) ? [...navigator.languages] : [],
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
    hardwareConcurrency: Number.isFinite(navigator.hardwareConcurrency) ? navigator.hardwareConcurrency : null,
    deviceMemory: Number.isFinite(navigator.deviceMemory) ? navigator.deviceMemory : null,
    canvasHash,
    webglVendor: webgl.vendor,
    webglRenderer: webgl.renderer,
    webglHash: webgl.hash,
    audioHash,
    fontsHash: fontResult.hash,
    detectedFonts: fontResult.detected,
    clientRectsHash,
    webrtcApiAvailable,
    webrtcBlocked: Boolean(webrtc.blocked),
    webrtcCandidateTypes: webrtc.types,
    webrtcCandidateAddresses: webrtc.addresses,
    webrtcGatheringState: webrtc.gatheringState,
    webrtcPrivateCandidateDetected: Boolean(webrtc.privateCandidate),
    webrtcPublicCandidateDetected: Boolean(webrtc.publicCandidate),
    navigatorWebdriver: typeof navigator.webdriver === 'boolean' ? navigator.webdriver : null,
    automationWindowMarkers,
    hasWindowChrome: Boolean(window.chrome),
    pluginsCount: navigator.plugins ? navigator.plugins.length : null,
    notificationPermission,
    iframeWebdriver,
    workerWebdriver,
    cdpStackProbeDetected,
  };
}
"""


class IMVerificationError(RuntimeError):
    pass


class IMVerificationBusyError(IMVerificationError):
    pass


@dataclass(slots=True)
class _TokenResult:
    token: str | None
    verification_url: str | None
    reason_code: str | None
    session_expired: bool
    updated_cookie: str | None


@dataclass(slots=True)
class _ActiveSession:
    verification_id: str
    purpose: str
    account_id: str | None
    context: Any
    page: Any
    bridge: SocksBridge | None
    expires_at: float
    temporary_profile: Path | None = None
    qr_session: QRLoginSession | None = None
    baseline_cookie: str | None = None
    timeout_task: asyncio.Task[None] | None = None
    desktop: "_VisualDesktop | None" = None
    last_activity_at: float | None = None
    max_expires_at: float | None = None


@dataclass(slots=True)
class _VisualDesktop:
    slot: int
    display: str
    vnc_port: int
    cdp_port: int | None
    xvfb: asyncio.subprocess.Process | None = None
    window_manager: asyncio.subprocess.Process | None = None
    vnc: asyncio.subprocess.Process | None = None


@dataclass(frozen=True, slots=True)
class _VNCTicket:
    verification_id: str
    user_id: str
    expires_at: float
    vnc_port: int


@dataclass(frozen=True, slots=True)
class _CookieCheck:
    state: str
    cookie: str
    result: Any | None = None
    message: str | None = None
    error_kind: str | None = None


@dataclass(frozen=True, slots=True)
class _CookieReconcileResult:
    sync_status: str
    browser_status: str
    local_status: str
    message: str


class IMVerificationManager:
    """Own one reserved verification desktop and a bounded account desktop pool."""

    def __init__(
        self,
        store: AccountStore,
        runtime_manager: Any,
        cookie_coordinator: Any | None = None,
    ) -> None:
        self._store = store
        self._runtime = runtime_manager
        self._cookie_coordinator = cookie_coordinator
        self._lock = asyncio.Lock()
        # QR login and risk verification keep a reserved desktop so account VNC
        # sessions cannot prevent an account from recovering its login state.
        self._active: _ActiveSession | None = None
        self._account_actives: dict[str, _ActiveSession] = {}
        self._playwright: Any | None = None
        self._xvfb: asyncio.subprocess.Process | None = None
        self._window_manager: asyncio.subprocess.Process | None = None
        self._vnc: asyncio.subprocess.Process | None = None
        self._tickets: dict[str, _VNCTicket] = {}
        self._qr_verifications: dict[str, XianyuQRBrowserVerificationPayload] = {}
        self._account_browser_sessions: dict[str, AccountBrowserSessionPayload] = {}
        self._account_browser_by_account: dict[str, str] = {}

    def browser_path(self, identity: ClientIdentity | None = None) -> str | None:
        if identity is not None and identity.browser_engine == "fingerprint_chromium":
            try:
                return str(
                    browser_binary_manager.resolve_fingerprint_executable(
                        identity.browser_version
                    )
                )
            except BrowserBinaryError:
                return None
        if identity is not None and identity.browser_binary_source == "managed":
            try:
                return str(
                    standard_browser_binary_manager.resolve_executable(
                        identity.browser_version
                    )
                )
            except BrowserBinaryError:
                return None
        configured = settings.im_verification_browser_path
        if configured:
            return configured if Path(configured).is_file() else None
        for candidate in system_browser_candidates():
            if Path(candidate).is_file():
                return candidate
        return None

    def availability_error(self, identity: ClientIdentity | None = None) -> str | None:
        if not settings.im_verification_browser_enabled:
            return "人工验证浏览器未启用"
        if os.name == "nt":
            return "Windows 原生版暂不支持内嵌 VNC 浏览器，请使用 Linux 或 Docker 部署"
        if self.browser_path(identity) is None:
            if identity is not None and identity.browser_engine == "fingerprint_chromium":
                return "账户指定的 Fingerprint Chromium 未安装或不可用"
            if identity is not None and identity.browser_binary_source == "managed":
                return f"账户指定的标准 Chrome {identity.browser_version} 未安装或不可用"
            return "未安装可用的 Chrome/Chromium"
        if shutil.which("Xvfb") is None:
            return "未安装 Xvfb"
        if shutil.which("x11vnc") is None:
            return "未安装 x11vnc"
        if importlib.util.find_spec("playwright") is None:
            return "未安装 Playwright Python 依赖"
        if is_root_process() and not settings.im_verification_allow_no_sandbox:
            return "浏览器服务正在以 root 运行，且未允许 no-sandbox 模式"
        return None

    @property
    def active_visual_account_id(self) -> str | None:
        ids = self.active_visual_account_ids
        return ids[0] if ids else None

    @property
    def has_active_visual_sessions(self) -> bool:
        return bool(
            self._active is not None
            or self._account_actives
            or any(
                payload.status in {"starting", "ready"}
                for payload in self._account_browser_sessions.values()
            )
        )

    @property
    def active_visual_account_ids(self) -> list[str]:
        ids = [
            payload.account_id
            for payload in self._account_browser_sessions.values()
            if payload.status in {"starting", "ready"}
        ]
        ids.extend(
            [
            active.account_id
            for active in self._account_actives.values()
            if active.account_id
            ]
        )
        if self._active is not None and self._active.account_id:
            ids.append(self._active.account_id)
        return list(dict.fromkeys(ids))

    def _account_active_for_account(self, account_id: str) -> _ActiveSession | None:
        return next(
            (
                active
                for active in self._account_actives.values()
                if active.account_id == account_id
            ),
            None,
        )

    def _active_for_verification(self, verification_id: str) -> _ActiveSession | None:
        if self._active is not None and self._active.verification_id == verification_id:
            return self._active
        return self._account_actives.get(verification_id)

    def _all_actives(self) -> tuple[_ActiveSession, ...]:
        reserved = (self._active,) if self._active is not None else ()
        return (*reserved, *self._account_actives.values())

    async def prepare_account_identity_change(self, account_id: str) -> None:
        """Close only the account browser affected by an identity change."""

        async with self._lock:
            active = self._account_active_for_account(account_id)
            if active is not None:
                session_id = self._account_browser_session_id(active)
                await self._close_account_active_locked(active)
                if session_id is not None:
                    current = self._account_browser_sessions.get(session_id)
                    if current is not None:
                        self._account_browser_sessions[session_id] = current.model_copy(
                            update={
                                "status": "closed",
                                "message": "账户浏览器身份已更新，环境已停止",
                                "vnc_available": False,
                                "cdp_available": False,
                                "idle_expires_at": None,
                                "max_expires_at": None,
                                "expires_at": None,
                            }
                        )
            if self._active is not None and self._active.account_id == account_id:
                await self._close_active_locked()

    async def shutdown(self) -> None:
        async with self._lock:
            for active in tuple(self._account_actives.values()):
                await self._close_account_active_locked(active)
            await self._close_active_locked()
            if self._playwright is not None:
                with suppress(Exception):
                    await self._playwright.stop()
                self._playwright = None
            for process in (self._vnc, self._window_manager, self._xvfb):
                if process is not None and process.returncode is None:
                    process.terminate()
            for process in (self._vnc, self._window_manager, self._xvfb):
                if process is not None and process.returncode is None:
                    with suppress(Exception):
                        await asyncio.wait_for(process.wait(), timeout=3)
            self._vnc = None
            self._window_manager = None
            self._xvfb = None
            self._tickets.clear()
            self._qr_verifications.clear()
            self._account_browser_sessions.clear()
            self._account_browser_by_account.clear()

    async def status_for_account(self, account_id: str) -> IMVerificationPayload | None:
        payload = await self._store.get_latest_im_verification(account_id)
        return self._decorate(payload)

    async def qr_status(self, session_id: str) -> XianyuQRBrowserVerificationPayload:
        async with self._lock:
            payload = self._qr_verifications.get(session_id)
            if payload is None:
                payload = XianyuQRBrowserVerificationPayload(session_id=session_id)
            return self._decorate_qr(payload)

    async def account_browser_status(
        self, account_id: str
    ) -> AccountBrowserSessionPayload | None:
        async with self._lock:
            session_id = self._account_browser_by_account.get(account_id)
            if session_id is None:
                return None
            payload = self._account_browser_sessions.get(session_id)
            return self._decorate_account_browser(payload)

    async def touch_account_browser_session(
        self,
        session_id: str,
    ) -> AccountBrowserSessionPayload:
        async with self._lock:
            active, payload = self._require_ready_account_browser_locked(session_id)
            return self._touch_account_browser_locked(active, payload)

    async def paste_account_browser_text(
        self,
        session_id: str,
        text: str,
    ) -> AccountBrowserSessionPayload:
        if not text.strip():
            raise IMVerificationError("粘贴内容不能为空")
        if len(text) > 20_000:
            raise IMVerificationError("粘贴内容不能超过 20000 个字符")
        async with self._lock:
            active, payload = self._require_ready_account_browser_locked(session_id)
            keyboard = getattr(active.page, "keyboard", None)
            insert_text = getattr(keyboard, "insert_text", None)
            if not callable(insert_text):
                raise IMVerificationError("当前浏览器不支持文本粘贴")
            try:
                await insert_text(text)
            except Exception as exc:
                raise IMVerificationError("文本粘贴失败，请先点击网页输入框") from exc
            return self._touch_account_browser_locked(active, payload)

    def _require_ready_account_browser_locked(
        self,
        session_id: str,
    ) -> tuple[_ActiveSession, AccountBrowserSessionPayload]:
        verification_id = self._account_browser_verification_id(session_id)
        active = self._account_actives.get(verification_id)
        payload = self._account_browser_sessions.get(session_id)
        if active is None or payload is None or payload.status != "ready":
            raise IMVerificationError("账户浏览器会话未运行")
        return active, payload

    def _touch_account_browser_locked(
        self,
        active: _ActiveSession,
        payload: AccountBrowserSessionPayload,
    ) -> AccountBrowserSessionPayload:
        now = time.time()
        max_expires_at = active.max_expires_at or active.expires_at
        if max_expires_at <= now:
            raise IMVerificationError("账户浏览器会话已达到最长运行时间")
        idle_seconds = max(
            60,
            int(
                getattr(
                    settings,
                    "account_browser_idle_seconds",
                    getattr(settings, "account_browser_session_seconds", 1800),
                )
            ),
        )
        idle_expires_at = min(now + idle_seconds, max_expires_at)
        active.last_activity_at = now
        active.expires_at = idle_expires_at
        if active.timeout_task is not None:
            active.timeout_task.cancel()
        session_id = self._account_browser_session_id(active)
        assert session_id is not None
        active.timeout_task = asyncio.create_task(
            self._expire_session(active.verification_id, idle_expires_at),
            name=f"account-browser-timeout:{session_id}",
        )
        updated = payload.model_copy(
            update={
                "last_activity_at": datetime.fromtimestamp(now, UTC),
                "idle_expires_at": datetime.fromtimestamp(idle_expires_at, UTC),
                "max_expires_at": datetime.fromtimestamp(max_expires_at, UTC),
                "expires_at": datetime.fromtimestamp(idle_expires_at, UTC),
            }
        )
        self._account_browser_sessions[session_id] = updated
        return self._decorate_account_browser(updated) or updated

    async def detect_account_browser_fingerprint(
        self,
        session_id: str,
    ) -> AccountBrowserSessionPayload:
        async with self._lock:
            verification_id = self._account_browser_verification_id(session_id)
            active = self._account_actives.get(verification_id)
            payload = self._account_browser_sessions.get(session_id)
            if (
                active is None
                or active.account_id is None
                or payload is None
                or payload.status != "ready"
            ):
                raise IMVerificationError("账户浏览器会话未运行，无法执行指纹检测")
            account = await self._store.get_account(active.account_id)
            if account is None:
                raise IMVerificationError("账户不存在")
            self._account_browser_sessions[session_id] = payload.model_copy(
                update={
                    "fingerprint_detection_status": "collecting",
                    "fingerprint_detection_error": None,
                }
            )
            snapshot = await self._capture_browser_fingerprint_snapshot(
                active.page,
                account.client_identity,
                proxy_enabled=account.proxy.enabled,
                expected_proxy_ips=await self._account_proxy_exit_ips(account),
            )
            if snapshot is None:
                failed = self._account_browser_sessions[session_id].model_copy(
                    update={
                        "fingerprint_detection_status": "failed",
                        "fingerprint_detection_error": "检测脚本未返回有效结果",
                    }
                )
                self._account_browser_sessions[session_id] = failed
                return self._decorate_account_browser(failed) or failed
            persisted = await self._store.save_account_browser_fingerprint_snapshot(
                active.account_id,
                snapshot,
            )
            if persisted is not None:
                snapshot = persisted
            ready = self._account_browser_sessions[session_id].model_copy(
                update={
                    "fingerprint_snapshot": snapshot,
                    "fingerprint_detection_status": "ready",
                    "fingerprint_detection_error": None,
                }
            )
            self._account_browser_sessions[session_id] = ready
            return self._decorate_account_browser(ready) or ready

    async def list_active_account_browsers(
        self,
    ) -> list[AccountBrowserSessionPayload]:
        async with self._lock:
            result: list[AccountBrowserSessionPayload] = []
            for payload in self._account_browser_sessions.values():
                if payload.status not in {"starting", "ready"}:
                    continue
                decorated = self._decorate_account_browser(payload)
                if decorated is not None:
                    result.append(decorated)
            return result

    async def list_browser_profiles(self) -> list[BrowserProfilePayload]:
        accounts = {account.account_id: account for account in await self._store.list_accounts()}
        profiles = await run_browser_blocking(browser_profile_storage.list_profiles)
        async with self._lock:
            actives_by_key = {
                profile_key: active
                for active in self._all_actives()
                if (profile_key := self._active_profile_key(active)) is not None
            }
            result: list[BrowserProfilePayload] = []
            for profile in profiles:
                account_id = profile.owner_account_id
                if account_id is None and profile.profile_type == "account":
                    if profile.directory_name in accounts:
                        account_id = profile.directory_name
                account = accounts.get(account_id or "")
                active = actives_by_key.get(profile.profile_key)
                is_active = active is not None
                if is_active:
                    status = "running"
                elif profile.in_use:
                    status = "busy"
                elif profile.profile_type == "qr":
                    status = "temporary"
                elif account is None:
                    status = "orphaned"
                else:
                    status = "stopped"
                profile_type = (
                    "qr"
                    if profile.profile_type == "qr"
                    else "account" if account is not None else "orphan"
                )
                result.append(
                    BrowserProfilePayload(
                        profile_key=profile.profile_key,
                        directory_name=profile.directory_name,
                        profile_type=profile_type,
                        account_id=account.account_id if account is not None else account_id,
                        account_name=(
                            account.display_name
                            if account is not None
                            else profile.owner_account_name
                        ),
                        account_exists=account is not None,
                        size_bytes=profile.size_bytes,
                        created_at=profile.created_at,
                        updated_at=profile.updated_at,
                        status=status,  # type: ignore[arg-type]
                        session_id=self._active_session_id(active) if active else None,
                        session_purpose=active.purpose if is_active and active else None,
                        vnc_available=is_active,
                        current_url=(
                            str(active.page.url or "") or None
                            if is_active and active is not None
                            else None
                        ),
                        manageable=profile.manageable,
                        browser_engine=profile.browser_engine,  # type: ignore[arg-type]
                        config_revision=profile.config_revision,
                    )
                )
            return sorted(
                result,
                key=lambda item: (
                    item.status != "running",
                    item.account_name or item.directory_name,
                ),
            )

    async def stop_browser_profile(self, profile_key: str) -> bool:
        async with self._lock:
            active = next(
                (
                    item
                    for item in self._all_actives()
                    if self._active_profile_key(item) == profile_key
                ),
                None,
            )
            if active is None:
                return await run_browser_blocking(
                    browser_profile_storage.stop_profile_processes,
                    profile_key,
                )

            purpose = active.purpose
            verification_id = active.verification_id
            qr_session = active.qr_session
            if purpose == "account_browser":
                reconcile = await self._close_account_active_locked(active)
            else:
                reconcile = None
                await self._close_active_locked()
            if purpose == "account_browser":
                session_id = verification_id.removeprefix("account-browser:")
                payload = self._account_browser_sessions.get(session_id)
                if payload is not None:
                    self._account_browser_sessions[session_id] = payload.model_copy(
                        update={
                            "status": "closed",
                            "message": (
                                reconcile.message
                                if reconcile is not None
                                else "浏览器会话已由目录管理停止"
                            ),
                            "vnc_available": False,
                            "cdp_available": False,
                            "idle_expires_at": None,
                            "max_expires_at": None,
                            "expires_at": None,
                            **self._cookie_reconcile_payload_updates(reconcile),
                        }
                    )
            elif purpose == "qr_login":
                session_id = verification_id.removeprefix("qr:")
                if qr_session is not None:
                    qr_session.fail("远程登录浏览器已由目录管理停止")
                self._qr_verifications[session_id] = self._qr_payload(
                    session_id,
                    "cancelled",
                    "远程登录浏览器已由目录管理停止",
                    None,
                )
            else:
                await self._store.set_im_verification_state(
                    verification_id,
                    "cancelled",
                    "人工安全验证浏览器已由目录管理停止",
                )
            return True

    async def clear_browser_profile(self, profile_key: str) -> bool:
        async with self._lock:
            if any(
                self._active_profile_key(active) == profile_key
                for active in self._all_actives()
            ):
                raise IMVerificationBusyError("该浏览器目录正在运行，请先停止会话")
            try:
                return await run_browser_blocking(
                    browser_profile_storage.delete_profile,
                    profile_key,
                )
            except BrowserProfileBusyError as exc:
                raise IMVerificationBusyError(
                    "该浏览器目录仍被进程占用，请先停止会话"
                ) from exc

    async def clear_account_browser_profile(self, account_id: str) -> bool:
        async with self._lock:
            if any(active.account_id == account_id for active in self._all_actives()):
                raise IMVerificationBusyError("该账户浏览器正在运行，请先结束会话")
            try:
                return await run_browser_blocking(
                    browser_profile_storage.delete_account,
                    account_id,
                )
            except BrowserProfileBusyError as exc:
                raise IMVerificationBusyError(
                    "账户浏览器 Profile 正在被使用，请先结束会话"
                ) from exc

    async def prepare_account_deletion(self, account_id: str) -> None:
        async with self._lock:
            active = self._account_active_for_account(account_id)
            if active is None:
                active = (
                    self._active
                    if self._active is not None and self._active.account_id == account_id
                    else None
                )
            if active is None:
                return
            purpose = active.purpose
            verification_id = active.verification_id
            if purpose == "account_browser":
                await self._close_account_active_locked(active)
            else:
                await self._close_active_locked()
            if purpose == "account_browser":
                session_id = verification_id.removeprefix("account-browser:")
                payload = self._account_browser_sessions.get(session_id)
                if payload is not None:
                    self._account_browser_sessions[session_id] = payload.model_copy(
                        update={
                            "status": "closed",
                            "message": "账户删除，浏览器会话已关闭",
                            "vnc_available": False,
                            "cdp_available": False,
                            "idle_expires_at": None,
                            "max_expires_at": None,
                            "expires_at": None,
                        }
                    )
            elif purpose == "qr_login":
                session_id = verification_id.removeprefix("qr:")
                self._qr_verifications[session_id] = self._qr_payload(
                    session_id,
                    "cancelled",
                    "账户删除，远程登录验证已取消",
                    None,
                )
            else:
                await self._store.set_im_verification_state(
                    verification_id,
                    "cancelled",
                    "账户删除，人工安全验证已取消",
                )

    async def forget_account_browser(self, account_id: str) -> None:
        async with self._lock:
            session_id = self._account_browser_by_account.pop(account_id, None)
            if session_id is not None:
                self._account_browser_sessions.pop(session_id, None)

    async def start_account_browser(
        self,
        account: AccountRecord,
        user_id: str,
    ) -> AccountBrowserSessionPayload:
        del user_id  # The authenticated actor is recorded by the API audit middleware.
        async with self._lock:
            error = self.availability_error(account.client_identity)
            if error:
                raise IMVerificationError(error)
            cookie_map = load_upstream_modules().trans_cookies(account.cookie)
            if not str(cookie_map.get("unb") or ""):
                raise IMVerificationError("账户 Cookie 缺少 unb，无法打开账户网页")
            self._validate_account_network(account)
            existing = self._account_active_for_account(account.account_id)
            if existing is not None:
                active_session_id = self._account_browser_session_id(existing)
                if active_session_id is not None:
                    current = self._account_browser_sessions.get(active_session_id)
                    if current is not None:
                        return self._decorate_account_browser(current)
            if self._active is not None and self._active.account_id == account.account_id:
                raise IMVerificationBusyError("该账户正在进行登录或安全验证，请完成后再开启 VNC")
            max_sessions = max(1, int(getattr(settings, "account_browser_max_sessions", 3)))
            if len(self._account_actives) >= max_sessions:
                raise IMVerificationBusyError(
                    f"账户 VNC 并发数已达到上限 {max_sessions}，请先结束一个会话"
                )

            session_id = uuid.uuid4().hex
            verification_id = self._account_browser_verification_id(session_id)
            now = time.time()
            idle_seconds = max(
                60,
                int(
                    getattr(
                        settings,
                        "account_browser_idle_seconds",
                        getattr(settings, "account_browser_session_seconds", 1800),
                    )
                ),
            )
            max_session_seconds = max(
                idle_seconds,
                int(
                    getattr(
                        settings,
                        "account_browser_max_session_seconds",
                        max(idle_seconds, 28800),
                    )
                ),
            )
            max_expires_at = now + max_session_seconds
            expires_at = min(now + idle_seconds, max_expires_at)
            previous_session_id = self._account_browser_by_account.get(account.account_id)
            if previous_session_id is not None:
                self._account_browser_sessions.pop(previous_session_id, None)
            payload = self._account_browser_payload(
                session_id,
                account.account_id,
                "starting",
                "正在启动账户网页浏览器",
                account.proxy.enabled,
                now,
                expires_at,
                last_activity_at=now,
                max_expires_at=max_expires_at,
            )
            self._account_browser_sessions[session_id] = payload
            self._account_browser_by_account[account.account_id] = session_id

            context: Any | None = None
            bridge: SocksBridge | None = None
            desktop: _VisualDesktop | None = None
            try:
                desktop = await self._start_account_visual_desktop_locked()
                bridge = await self._start_proxy_bridge(account)
                context = await self._launch_account_browser(
                    account,
                    bridge,
                    enable_cdp=settings.account_browser_cdp_enabled,
                    display=desktop.display,
                    cdp_port=desktop.cdp_port,
                )
                page = await self._prepare_visual_page(context)
                await self._inject_account_cookies(context, account)
                try:
                    await page.goto(
                        "https://www.goofish.com/",
                        wait_until="domcontentloaded",
                        timeout=30_000,
                    )
                except Exception as exc:
                    if not page.url or page.url == "about:blank":
                        raise IMVerificationError("闲鱼网页打开失败") from exc
                self._account_browser_sessions[session_id] = payload.model_copy(
                    update={
                        "current_url": page.url or "https://www.goofish.com/",
                        "fingerprint_detection_status": "collecting",
                    }
                )
                fingerprint_snapshot = await self._capture_browser_fingerprint_snapshot(
                    page,
                    account.client_identity,
                    proxy_enabled=account.proxy.enabled,
                    expected_proxy_ips=await self._account_proxy_exit_ips(account),
                )
                if fingerprint_snapshot is not None:
                    save_snapshot = getattr(
                        self._store,
                        "save_account_browser_fingerprint_snapshot",
                        None,
                    )
                    if callable(save_snapshot):
                        try:
                            persisted = await save_snapshot(
                                account.account_id,
                                fingerprint_snapshot,
                            )
                            if persisted is not None:
                                fingerprint_snapshot = persisted
                        except Exception as exc:
                            logger.warning(
                                "Unable to persist browser fingerprint snapshot for %s: %s",
                                account.account_id,
                                exc,
                            )
                detection_status = "ready" if fingerprint_snapshot is not None else "failed"
                detection_error = (
                    None if fingerprint_snapshot is not None else "检测脚本未返回有效结果"
                )
                if settings.account_browser_cdp_enabled:
                    assert desktop.cdp_port is not None
                    await self._wait_for_cdp(desktop.cdp_port)

                ready_at = time.time()
                expires_at = min(ready_at + idle_seconds, max_expires_at)
                active = _ActiveSession(
                    verification_id=verification_id,
                    purpose="account_browser",
                    account_id=account.account_id,
                    context=context,
                    page=page,
                    bridge=bridge,
                    expires_at=expires_at,
                    baseline_cookie=account.cookie,
                    desktop=desktop,
                    last_activity_at=ready_at,
                    max_expires_at=max_expires_at,
                )
                self._account_actives[verification_id] = active
                active.timeout_task = asyncio.create_task(
                    self._expire_session(verification_id, expires_at),
                    name=f"account-browser-timeout:{session_id}",
                )
                ready = self._account_browser_payload(
                    session_id,
                    account.account_id,
                    "ready",
                    "浏览器已就绪，Cookie 和账户代理已应用",
                    account.proxy.enabled,
                    now,
                    expires_at,
                    current_url=page.url or "https://www.goofish.com/",
                    cdp_available=settings.account_browser_cdp_enabled,
                    fingerprint_snapshot=fingerprint_snapshot,
                    fingerprint_detection_status=detection_status,
                    fingerprint_detection_error=detection_error,
                    last_activity_at=ready_at,
                    max_expires_at=max_expires_at,
                )
                self._account_browser_sessions[session_id] = ready
                return self._decorate_account_browser(ready)
            except Exception as exc:
                if context is not None:
                    with suppress(Exception):
                        await context.close()
                if bridge is not None:
                    await bridge.close()
                if desktop is not None:
                    await self._stop_visual_desktop(desktop)
                failed = self._account_browser_payload(
                    session_id,
                    account.account_id,
                    "failed",
                    str(exc),
                    account.proxy.enabled,
                    now,
                    None,
                )
                self._account_browser_sessions[session_id] = failed
                if isinstance(exc, (IMVerificationError, IMVerificationBusyError)):
                    raise
                raise IMVerificationError(str(exc)) from exc

    async def close_account_browser(
        self, session_id: str
    ) -> AccountBrowserSessionPayload:
        async with self._lock:
            payload = self._account_browser_sessions.get(session_id)
            if payload is None:
                raise IMVerificationError("平台账户浏览器会话不存在")
            verification_id = self._account_browser_verification_id(session_id)
            active = self._account_actives.get(verification_id)
            if active is not None:
                closing = payload.model_copy(
                    update={"status": "closing", "message": "正在关闭浏览器"}
                )
                self._account_browser_sessions[session_id] = closing
                reconcile = await self._close_account_active_locked(active)
            else:
                reconcile = None
            reconcile_updates = (
                {
                    "cookie_sync_status": reconcile.sync_status,
                    "browser_cookie_status": reconcile.browser_status,
                    "local_cookie_status": reconcile.local_status,
                }
                if reconcile is not None
                else {}
            )
            closed = payload.model_copy(
                update={
                    "status": "closed",
                    "message": (
                        reconcile.message
                        if reconcile is not None
                        else "浏览器会话已关闭"
                    ),
                    "vnc_available": False,
                    "cdp_available": False,
                    "idle_expires_at": None,
                    "max_expires_at": None,
                    "expires_at": None,
                    **reconcile_updates,
                }
            )
            self._account_browser_sessions[session_id] = closed
            return self._decorate_account_browser(closed)

    async def issue_account_browser_vnc_ticket(
        self, session_id: str, user_id: str
    ) -> tuple[str, int]:
        return await self.issue_vnc_ticket(
            self._account_browser_verification_id(session_id), user_id
        )

    async def start_qr_login(
        self,
        session: QRLoginSession,
        account: AccountRecord | None,
        user_id: str,
    ) -> XianyuQRBrowserVerificationPayload:
        if self._lock.locked():
            raise IMVerificationBusyError("人工验证服务正在处理其他启动请求")
        async with self._lock:
            client_identity = (
                account.client_identity
                if account is not None
                else resolve_client_identity(session.browser_identity)
            )
            error = self.availability_error(client_identity)
            if error:
                raise IMVerificationError(error)
            try:
                validate_account_network_route(session.proxy_id, session.proxy)
            except AccountNetworkPolicyError as exc:
                raise IMVerificationError(str(exc)) from exc
            verification_id = self._qr_verification_id(session.session_id)
            if account is not None and self._account_active_for_account(account.account_id):
                raise IMVerificationBusyError("该账户 VNC 会话正在运行，请先结束会话再登录")
            if self._active is not None:
                if self._active.verification_id == verification_id:
                    return self._decorate_qr(self._qr_verifications[session.session_id])
                raise IMVerificationBusyError("已有账户正在进行人工安全验证")

            expires_at = time.time() + settings.im_verification_session_seconds
            self._qr_verifications[session.session_id] = self._qr_payload(
                session.session_id,
                "starting",
                "正在启动远程登录浏览器",
                expires_at,
            )
            session.begin_browser_verification(settings.im_verification_session_seconds)
            context: Any | None = None
            bridge: SocksBridge | None = None
            temporary_profile: Path | None = None
            try:
                await self._ensure_visual_desktop()
                bridge = await self._start_proxy_bridge_config(
                    session.proxy,
                    proxy_id=session.proxy_id,
                )
                if account is not None:
                    profile_key = account.account_id
                    await self._prepare_account_browser_profile(account)
                else:
                    profile_key = f"_qr/{session.session_id}"
                    temporary_profile = await run_browser_blocking(
                        browser_profile_storage.prepare_qr,
                        session.session_id,
                        None,
                    )
                context = await self._launch_browser(
                    profile_key,
                    bridge,
                    identity=client_identity,
                )
                if account is not None:
                    await self._inject_account_cookies(context, account)
                else:
                    await context.clear_cookies()
                page = await self._prepare_visual_page(context)
                login_url = (
                    f"{LOGIN_PAGE_URL}?lang=zh_cn&appName=xianyu&appEntrance=web"
                    "&styleType=vertical&notKeepLogin=false&qrCodeFirst=true&site=77"
                )
                try:
                    await page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
                except Exception as exc:
                    if not page.url or page.url == "about:blank":
                        raise IMVerificationError("闲鱼登录页面打开失败") from exc

                active = _ActiveSession(
                    verification_id=verification_id,
                    purpose="qr_login",
                    account_id=account.account_id if account is not None else None,
                    context=context,
                    page=page,
                    bridge=bridge,
                    expires_at=expires_at,
                    temporary_profile=temporary_profile,
                    qr_session=session,
                    baseline_cookie=account.cookie if account is not None else None,
                )
                self._active = active
                active.timeout_task = asyncio.create_task(
                    self._expire_session(verification_id, expires_at),
                    name=f"qr-login-verification-timeout:{session.session_id}",
                )
                ready = self._qr_payload(
                    session.session_id,
                    "ready",
                    "远程浏览器已就绪，可完成扫码、人脸或滑块验证",
                    expires_at,
                )
                self._qr_verifications[session.session_id] = ready
                return self._decorate_qr(ready)
            except Exception as exc:
                if context is not None:
                    with suppress(Exception):
                        await context.close()
                if bridge is not None:
                    await bridge.close()
                if temporary_profile is not None:
                    with suppress(OSError):
                        shutil.rmtree(temporary_profile)
                failed = self._qr_payload(
                    session.session_id,
                    "failed",
                    str(exc),
                    None,
                )
                self._qr_verifications[session.session_id] = failed
                if isinstance(exc, IMVerificationError):
                    raise
                raise IMVerificationError(str(exc)) from exc

    async def prepare_qr_login_completion(
        self,
        session: QRLoginSession,
        account: AccountRecord | None,
    ) -> str:
        async with self._lock:
            verification_id = self._qr_verification_id(session.session_id)
            active = self._active
            if (
                active is None
                or active.verification_id != verification_id
                or active.purpose != "qr_login"
            ):
                raise IMVerificationError("远程登录浏览器未运行或已过期")
            self._qr_verifications[session.session_id] = self._qr_payload(
                session.session_id,
                "completing",
                "正在检查并验证登录凭据",
                active.expires_at,
            )
            try:
                cookies = await active.context.cookies(
                    [
                        "https://www.goofish.com/",
                        "https://h5api.m.goofish.com/",
                        "https://passport.goofish.com/",
                        "https://log.mmstat.com/",
                    ]
                )
                cookie = await run_qr_blocking(session.finalize_browser_credentials, cookies)
                new_unb = str(load_upstream_modules().trans_cookies(cookie).get("unb") or "")
                if account is not None and account.cookie:
                    expected_unb = str(
                        load_upstream_modules().trans_cookies(account.cookie).get("unb") or ""
                    )
                    if expected_unb and new_unb != expected_unb:
                        raise IMVerificationError("扫码登录的闲鱼账号与当前账户不一致")
                return cookie
            except Exception as exc:
                self._qr_verifications[session.session_id] = self._qr_payload(
                    session.session_id,
                    "ready",
                    str(exc),
                    active.expires_at,
                )
                if isinstance(exc, (IMVerificationError, QRLoginError)):
                    raise IMVerificationError(str(exc)) from exc
                raise IMVerificationError(str(exc)) from exc

    async def finish_qr_login(
        self,
        session_id: str,
        message: str = "登录凭据已保存，账户连接已启动",
    ) -> XianyuQRBrowserVerificationPayload:
        async with self._lock:
            verification_id = self._qr_verification_id(session_id)
            if self._active is not None and self._active.verification_id == verification_id:
                await self._close_active_locked()
            payload = self._qr_payload(session_id, "completed", message, None)
            self._qr_verifications[session_id] = payload
            return self._decorate_qr(payload)

    async def restore_qr_login_ready(
        self,
        session_id: str,
        message: str,
    ) -> XianyuQRBrowserVerificationPayload:
        async with self._lock:
            verification_id = self._qr_verification_id(session_id)
            active = self._active
            if active is None or active.verification_id != verification_id:
                raise IMVerificationError("远程登录浏览器未运行或已过期")
            payload = self._qr_payload(session_id, "ready", message, active.expires_at)
            self._qr_verifications[session_id] = payload
            return self._decorate_qr(payload)

    async def cancel_qr_login(self, session_id: str) -> XianyuQRBrowserVerificationPayload:
        async with self._lock:
            verification_id = self._qr_verification_id(session_id)
            if self._active is not None and self._active.verification_id == verification_id:
                await self._close_active_locked()
            payload = self._qr_payload(session_id, "cancelled", "远程登录验证已取消", None)
            self._qr_verifications[session_id] = payload
            return self._decorate_qr(payload)

    async def start(
        self,
        account: AccountRecord,
        verification: IMVerificationPayload,
        user_id: str,
    ) -> IMVerificationPayload:
        async with self._lock:
            error = self.availability_error(account.client_identity)
            if error:
                raise IMVerificationError(error)
            self._validate_account_network(account)
            if self._account_active_for_account(account.account_id) is not None:
                raise IMVerificationBusyError("该账户 VNC 会话正在运行，请先结束会话再进行安全验证")
            if self._active is not None:
                if self._active.verification_id == verification.verification_id:
                    current = await self._store.get_im_verification(verification.verification_id)
                    assert current is not None
                    return self._decorate(current)
                raise IMVerificationBusyError("已有账户正在进行人工安全验证")

            updated = await self._store.set_im_verification_state(
                verification.verification_id,
                "starting",
                "正在启动账户专属浏览器",
                started_by_user_id=user_id,
                expires_in_seconds=settings.im_verification_session_seconds,
            )
            if updated is None:
                raise IMVerificationError("验证记录不存在")

            context: Any | None = None
            bridge: SocksBridge | None = None
            try:
                await self._ensure_visual_desktop()
                bridge = await self._start_proxy_bridge(account)
                context = await self._launch_account_browser(account, bridge)
                page = await self._prepare_visual_page(context)
                await self._inject_account_cookies(context, account)

                verification_url = await self._store.get_im_verification_url(
                    verification.verification_id
                )
                url_is_fresh = bool(
                    verification_url
                    and verification.expires_at
                    and verification.expires_at.timestamp() > time.time() + 30
                )
                if not url_is_fresh:
                    token_result = await run_platform_blocking(self._request_token_once, account)
                    if token_result.updated_cookie:
                        await self._persist_refreshed_cookie(account, token_result.updated_cookie)
                    if token_result.token:
                        await self._store.save_im_token(
                            account.account_id,
                            token_result.token,
                            int(time.time() * 1000) + 4 * 60 * 60 * 1000,
                        )
                        await context.close()
                        context = None
                        if bridge is not None:
                            await bridge.close()
                            bridge = None
                        return await self._resume_without_browser(verification.verification_id, account.account_id)
                    if token_result.session_expired:
                        await self._store.set_runtime_state(
                            account.account_id,
                            "auth_expired",
                            "闲鱼登录会话已过期，请重新扫码登录",
                        )
                        raise IMVerificationError("闲鱼登录会话已过期，请重新扫码登录")
                    verification_url = token_result.verification_url
                    if verification_url:
                        refreshed = await self._store.record_im_verification(
                            account.account_id,
                            token_result.reason_code or "INTERACTIVE_VERIFICATION_REQUIRED",
                            verification_url,
                        )
                        if refreshed is not None:
                            verification = refreshed
                if not verification_url:
                    raise IMVerificationError("平台未返回可用的安全验证地址")

                try:
                    await page.goto(
                        verification_url,
                        wait_until="domcontentloaded",
                        timeout=30_000,
                    )
                except Exception as exc:
                    if not page.url or page.url == "about:blank":
                        raise IMVerificationError("安全验证页面打开失败") from exc

                expires_at = time.time() + settings.im_verification_session_seconds
                active = _ActiveSession(
                    verification_id=verification.verification_id,
                    purpose="im_recovery",
                    account_id=account.account_id,
                    context=context,
                    page=page,
                    bridge=bridge,
                    expires_at=expires_at,
                    baseline_cookie=account.cookie,
                )
                self._active = active
                active.timeout_task = asyncio.create_task(
                    self._expire_session(verification.verification_id, expires_at),
                    name=f"im-verification-timeout:{verification.verification_id}",
                )
                ready = await self._store.set_im_verification_state(
                    verification.verification_id,
                    "ready",
                    "浏览器已就绪，等待人工完成验证",
                    expires_in_seconds=settings.im_verification_session_seconds,
                )
                assert ready is not None
                return self._decorate(ready)
            except Exception as exc:
                if context is not None:
                    with suppress(Exception):
                        await context.close()
                if bridge is not None:
                    await bridge.close()
                failed = await self._store.set_im_verification_state(
                    verification.verification_id,
                    "failed",
                    str(exc),
                )
                if isinstance(exc, IMVerificationError):
                    raise
                raise IMVerificationError(str(exc)) from exc

    async def complete(self, verification_id: str) -> IMVerificationPayload:
        async with self._lock:
            active = self._active
            if (
                active is None
                or active.verification_id != verification_id
                or active.purpose != "im_recovery"
            ):
                raise IMVerificationError("人工验证会话未运行或已过期")
            await self._store.set_im_verification_state(
                verification_id, "completing", "正在读取验证凭证并恢复 IM"
            )
            if active.account_id is None:
                raise IMVerificationError("安全验证账户不存在")
            account = await self._store.get_account(active.account_id)
            if account is None:
                raise IMVerificationError("账户不存在")
            try:
                cookies = await active.context.cookies(
                    ["https://www.goofish.com/", "https://h5api.m.goofish.com/"]
                )
                browser_unb = next(
                    (str(cookie.get("value") or "") for cookie in cookies if cookie.get("name") == "unb"),
                    "",
                )
                current = load_upstream_modules().trans_cookies(account.cookie)
                if browser_unb and browser_unb != str(current.get("unb") or ""):
                    raise IMVerificationError("浏览器账户与当前闲鱼账户不一致")
                x5_cookies = {
                    str(cookie.get("name")): str(cookie.get("value") or "")
                    for cookie in cookies
                    if cookie.get("name")
                    and (
                        str(cookie.get("name")).lower().startswith("x5")
                        or "x5sec" in str(cookie.get("name")).lower()
                    )
                    and cookie.get("value")
                }
                if not x5_cookies:
                    raise IMVerificationError("页面操作后未检测到 x5 安全验证凭证")
                merged = dict(current)
                merged.update(x5_cookies)
                new_cookie = "; ".join(f"{key}={value}" for key, value in merged.items())
                persisted = await self._store.compare_and_set_account_cookie(
                    account.account_id,
                    account.cookie,
                    new_cookie,
                    source="im_verification",
                )
                if not persisted:
                    raise IMVerificationError("账户 Cookie 已被其他任务更新，请重新开始验证")
                await self._store.save_im_token(account.account_id, "", 0)
                await self._close_active_locked()

                latest = await self._store.get_account(account.account_id)
                if latest is None:
                    raise IMVerificationError("账户不存在")
                result = await self._runtime.start(latest, force_restart=True)
                if result.runtime.state == "online":
                    completed = await self._store.set_im_verification_state(
                        verification_id,
                        "completed",
                        "安全验证已通过，闲鱼 IM 已恢复在线",
                        x5_cookie_names=list(x5_cookies),
                    )
                    assert completed is not None
                    return self._decorate(completed)
                current_verification = await self._store.get_im_verification(verification_id)
                if current_verification is not None and current_verification.status == "required":
                    return self._decorate(current_verification)
                raise IMVerificationError(result.runtime.message or "安全凭证已保存，但 IM 恢复失败")
            except Exception as exc:
                if self._active is not None and self._active.verification_id == verification_id:
                    await self._close_active_locked()
                failed = await self._store.set_im_verification_state(
                    verification_id,
                    "failed",
                    str(exc),
                )
                if isinstance(exc, IMVerificationError):
                    raise
                raise IMVerificationError(str(exc)) from exc

    async def cancel(self, verification_id: str) -> IMVerificationPayload:
        async with self._lock:
            if self._active is not None and self._active.verification_id == verification_id:
                await self._close_active_locked()
            payload = await self._store.set_im_verification_state(
                verification_id, "cancelled", "人工安全验证已取消"
            )
            if payload is None:
                raise IMVerificationError("验证记录不存在")
            return self._decorate(payload)

    async def issue_vnc_ticket(
        self, verification_id: str, user_id: str
    ) -> tuple[str, int]:
        async with self._lock:
            active = self._active_for_verification(verification_id)
            if active is None:
                raise IMVerificationError("VNC 浏览器未就绪")
            if active.purpose == "account_browser":
                session_id = self._account_browser_session_id(active)
                payload = (
                    self._account_browser_sessions.get(session_id)
                    if session_id is not None
                    else None
                )
                if payload is None or payload.status != "ready":
                    raise IMVerificationError("账户浏览器会话未运行")
                self._touch_account_browser_locked(active, payload)
            ticket = uuid.uuid4().hex + uuid.uuid4().hex
            ttl = 60
            self._tickets[ticket] = _VNCTicket(
                verification_id=verification_id,
                user_id=user_id,
                expires_at=time.time() + ttl,
                vnc_port=(
                    active.desktop.vnc_port
                    if active.desktop is not None
                    else settings.im_verification_vnc_port
                ),
            )
            return ticket, ttl

    async def consume_vnc_ticket(self, ticket: str) -> int | None:
        async with self._lock:
            value = self._tickets.pop(ticket, None)
            if value is None:
                return None
            if value.expires_at <= time.time():
                return None
            if self._active_for_verification(value.verification_id) is None:
                return None
            return value.vnc_port

    async def _start_account_visual_desktop_locked(self) -> _VisualDesktop:
        base_display_text = settings.im_verification_display.removeprefix(":").split(".", 1)[0]
        if not base_display_text.isdigit():
            raise IMVerificationError("VNC Display 配置无效")
        base_display = int(base_display_text)
        used_slots = {
            active.desktop.slot
            for active in self._account_actives.values()
            if active.desktop is not None
        }
        max_sessions = max(1, int(getattr(settings, "account_browser_max_sessions", 3)))
        search_limit = max(max_sessions * 4, 12)
        for slot in range(1, search_limit + 1):
            if slot in used_slots:
                continue
            display = f":{base_display + slot}"
            display_socket = Path(f"/tmp/.X11-unix/X{base_display + slot}")
            vnc_port = settings.im_verification_vnc_port + slot
            cdp_port = (
                settings.account_browser_cdp_port + slot
                if settings.account_browser_cdp_enabled
                else None
            )
            ports = [vnc_port, *([cdp_port] if cdp_port is not None else [])]
            if display_socket.exists() or any(
                port < 1 or port > 65535 for port in ports
            ):
                continue
            if not all([await self._port_is_available(port) for port in ports]):
                continue
            desktop = _VisualDesktop(
                slot=slot,
                display=display,
                vnc_port=vnc_port,
                cdp_port=cdp_port,
            )
            try:
                desktop.xvfb = await asyncio.create_subprocess_exec(
                    "Xvfb",
                    display,
                    "-screen",
                    "0",
                    "1365x768x24",
                    "-nolisten",
                    "tcp",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.sleep(0.6)
                if desktop.xvfb.returncode is not None:
                    raise IMVerificationError(f"账户 VNC Display {display} 启动失败")
                if shutil.which("fluxbox"):
                    desktop.window_manager = await asyncio.create_subprocess_exec(
                        "fluxbox",
                        "-display",
                        display,
                        "-no-toolbar",
                        "-no-slit",
                        env={**os.environ, "DISPLAY": display},
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.sleep(0.2)
                    if desktop.window_manager.returncode is not None:
                        raise IMVerificationError(f"账户 VNC 窗口管理器 {display} 启动失败")
                desktop.vnc = await asyncio.create_subprocess_exec(
                    "x11vnc",
                    "-display",
                    display,
                    "-localhost",
                    "-forever",
                    "-shared",
                    "-rfbport",
                    str(vnc_port),
                    "-nopw",
                    "-noxdamage",
                    "-quiet",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.sleep(0.4)
                if desktop.vnc.returncode is not None:
                    raise IMVerificationError(f"账户 VNC 服务端口 {vnc_port} 启动失败")
                return desktop
            except Exception:
                await self._stop_visual_desktop(desktop)
                raise
        raise IMVerificationBusyError("没有可用的 VNC Display/VNC/CDP 资源，请检查残留进程")

    @staticmethod
    async def _port_is_available(port: int) -> bool:
        try:
            server = await asyncio.start_server(
                lambda _reader, writer: writer.close(),
                "127.0.0.1",
                port,
            )
        except OSError:
            return False
        server.close()
        await server.wait_closed()
        return True

    @staticmethod
    async def _stop_visual_desktop(desktop: _VisualDesktop) -> None:
        processes = (desktop.vnc, desktop.window_manager, desktop.xvfb)
        for process in processes:
            if process is not None and process.returncode is None:
                with suppress(ProcessLookupError):
                    process.terminate()
        for process in processes:
            if process is None or process.returncode is not None:
                continue
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                with suppress(Exception):
                    await process.wait()

    async def _ensure_visual_desktop(self) -> None:
        display = settings.im_verification_display
        display_number = display.removeprefix(":").split(".", 1)[0]
        display_socket = Path(f"/tmp/.X11-unix/X{display_number}")
        if not display_socket.exists():
            self._xvfb = await asyncio.create_subprocess_exec(
                "Xvfb",
                display,
                "-screen",
                "0",
                "1365x768x24",
                "-nolisten",
                "tcp",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.sleep(0.6)
            if self._xvfb.returncode is not None:
                raise IMVerificationError("Xvfb 启动失败")
        if self._window_manager is None and shutil.which("fluxbox"):
            self._window_manager = await asyncio.create_subprocess_exec(
                "fluxbox",
                "-display",
                display,
                "-no-toolbar",
                "-no-slit",
                env={**os.environ, "DISPLAY": display},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.sleep(0.2)
            if self._window_manager.returncode is not None:
                raise IMVerificationError("Fluxbox 窗口管理器启动失败")
        if self._vnc is None or self._vnc.returncode is not None:
            self._vnc = await asyncio.create_subprocess_exec(
                "x11vnc",
                "-display",
                display,
                "-localhost",
                "-forever",
                "-shared",
                "-rfbport",
                str(settings.im_verification_vnc_port),
                "-nopw",
                "-noxdamage",
                "-quiet",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.sleep(0.4)
            if self._vnc.returncode is not None:
                raise IMVerificationError("VNC 服务启动失败")

    async def _launch_account_browser(
        self,
        account: AccountRecord,
        bridge: SocksBridge | None,
        *,
        enable_cdp: bool = False,
        display: str | None = None,
        cdp_port: int | None = None,
    ) -> Any:
        await self._prepare_account_browser_profile(account)
        return await self._launch_browser(
            account.account_id,
            bridge,
            identity=account.client_identity,
            enable_cdp=enable_cdp,
            display=display,
            cdp_port=cdp_port,
        )

    async def _prepare_account_browser_profile(self, account: AccountRecord) -> None:
        profile_key = browser_profile_storage.account_profile_key(account.account_id)
        if await run_browser_blocking(browser_profile_storage.profile_in_use, profile_key):
            raise IMVerificationBusyError(
                "该账户浏览器目录仍被进程占用，请先在浏览器目录管理中停止"
            )
        await run_browser_blocking(
            browser_profile_storage.prepare_account,
            account.account_id,
            account.display_name,
            account.browser_identity.browser_engine,
            account.browser_identity.config_revision,
        )

    async def _launch_browser(
        self,
        profile_key: str,
        bridge: SocksBridge | None,
        *,
        identity: ClientIdentity | None = None,
        enable_cdp: bool = False,
        display: str | None = None,
        cdp_port: int | None = None,
    ) -> Any:
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
        profile_root = Path(settings.im_verification_profile_dir)
        profile = profile_root / profile_key
        profile.mkdir(parents=True, exist_ok=True)
        profile.chmod(0o700)
        self._remove_stale_profile_locks(profile)
        effective_identity = identity or ClientIdentity()
        effective_display = display or settings.im_verification_display
        executable_path = self.browser_path(effective_identity)
        if executable_path is None:
            raise IMVerificationError("账户指定的浏览器内核未安装或不可用")
        posix_locale = effective_identity.language.replace("-", "_")
        primary_language = posix_locale.split("_", 1)[0]
        posix_language_priority = (
            f"{posix_locale}:{primary_language}:en_US:en"
        )
        args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-quic",
            f"--lang={effective_identity.language}",
            f"--accept-lang={effective_identity.accept_language}",
            "--start-maximized",
        ]
        if effective_identity.restrict_webrtc_to_proxy:
            args.extend(
                (
                    "--disable-non-proxied-udp",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                )
            )
        if effective_identity.browser_engine == "fingerprint_chromium":
            if effective_identity.fingerprint_seed is None:
                raise IMVerificationError("Fingerprint Chromium 缺少稳定指纹 Seed")
            args.extend(
                (
                    f"--fingerprint={effective_identity.fingerprint_seed}",
                    f"--fingerprint-platform={effective_identity.platform}",
                    f"--fingerprint-platform-version={effective_identity.platform_version}",
                    f"--fingerprint-brand={effective_identity.brand}",
                    f"--fingerprint-brand-version={effective_identity.normalized_browser_version}",
                    f"--timezone={effective_identity.timezone}",
                    "--enable-blink-features=FakeShadowRoot",
                )
            )
            if effective_identity.hardware_concurrency is not None:
                args.append(
                    f"--fingerprint-hardware-concurrency={effective_identity.hardware_concurrency}"
                )
            disabled_modules = effective_identity.disabled_spoofing_modules
            if disabled_modules:
                args.append(f"--disable-spoofing={','.join(disabled_modules)}")
        options: dict[str, Any] = {
            "headless": False,
            "executable_path": executable_path,
            "no_viewport": True,
            "locale": effective_identity.language,
            "timezone_id": effective_identity.timezone,
            "env": {
                **os.environ,
                "DISPLAY": effective_display,
                "LANG": f"{posix_locale}.UTF-8",
                "LANGUAGE": posix_language_priority,
                "LC_ALL": f"{posix_locale}.UTF-8",
                "TZ": effective_identity.timezone,
            },
            "args": args,
        }
        if effective_identity.browser_engine == "system_chromium":
            options["user_agent"] = effective_identity.user_agent
            options["extra_http_headers"] = {
                "Accept-Language": effective_identity.accept_language,
                "Sec-CH-UA": effective_identity.sec_ch_ua,
                "Sec-CH-UA-Platform": f'"{effective_identity.sec_ch_ua_platform}"',
            }
        if is_root_process() and settings.im_verification_allow_no_sandbox:
            options["args"].extend(("--no-sandbox", "--disable-setuid-sandbox"))
        if enable_cdp:
            effective_cdp_port = cdp_port or settings.account_browser_cdp_port
            options["args"].extend(
                (
                    "--remote-debugging-address=127.0.0.1",
                    f"--remote-debugging-port={effective_cdp_port}",
                )
            )
        if bridge is not None:
            assert bridge.port is not None
            options["proxy"] = {"server": f"socks5://127.0.0.1:{bridge.port}"}
        context = await self._playwright.chromium.launch_persistent_context(
            str(profile), **options
        )
        if effective_identity.disable_webrtc:
            await self._install_webrtc_block(context)
        if effective_identity.browser_engine == "system_chromium":
            await self._install_system_platform_compatibility(context, effective_identity)
        return context

    @staticmethod
    async def _install_webrtc_block(context: Any) -> None:
        """Disable page-level WebRTC while the network policy blocks direct UDP."""

        add_init_script = getattr(context, "add_init_script", None)
        if not callable(add_init_script):
            return
        script = """
            (() => {
              const blocked = [
                'RTCPeerConnection',
                'webkitRTCPeerConnection',
                'RTCDataChannel',
                'RTCIceTransport',
                'RTCDtlsTransport',
                'RTCSctpTransport'
              ];
              for (const name of blocked) {
                try {
                  Object.defineProperty(globalThis, name, {
                    configurable: false,
                    enumerable: false,
                    value: undefined,
                    writable: false
                  });
                } catch (_) { /* browser policy remains the network safety layer */ }
              }
            })();
        """
        await add_init_script(script=script)

    @staticmethod
    async def _install_system_platform_compatibility(
        context: Any,
        identity: ClientIdentity,
    ) -> None:
        add_init_script = getattr(context, "add_init_script", None)
        if not callable(add_init_script):
            return
        navigator_platform = {
            "windows": "Win32",
            "macos": "MacIntel",
            "linux": "Linux x86_64",
        }.get(identity.platform, "Win32")
        brands = [dict(item) for item in identity.user_agent_brands]
        metadata = {
            "platform": identity.sec_ch_ua_platform,
            "platformVersion": identity.platform_version,
            "architecture": "x86",
            "bitness": "64",
            "mobile": False,
            "uaFullVersion": identity.normalized_browser_version,
            "brands": brands,
            "fullVersionList": [
                {
                    **item,
                    "version": (
                        item["version"]
                        if item["brand"] == "Not/A)Brand"
                        else identity.normalized_browser_version
                    ),
                }
                for item in brands
            ],
        }
        script = f"""
            (() => {{
              const platform = {json.dumps(navigator_platform)};
              const metadata = {json.dumps(metadata, ensure_ascii=False)};
              const define = (target, name, getter) => {{
                try {{ Object.defineProperty(target, name, {{ configurable: true, get: getter }}); }}
                catch (_) {{ /* best-effort compatibility emulation */ }}
              }};
              define(Navigator.prototype, 'platform', () => platform);
              const uaData = navigator.userAgentData;
              if (uaData) {{
                define(uaData, 'platform', () => metadata.platform);
                define(uaData, 'mobile', () => metadata.mobile);
                define(uaData, 'brands', () => metadata.brands.map((item) => ({{ ...item }})));
                const original = typeof uaData.getHighEntropyValues === 'function'
                  ? uaData.getHighEntropyValues.bind(uaData)
                  : null;
                if (original) {{
                  const getHighEntropyValues = async (hints) => {{
                    const result = await original(hints);
                    for (const hint of hints || []) {{
                      if (Object.prototype.hasOwnProperty.call(metadata, hint)) result[hint] = metadata[hint];
                    }}
                    result.brands = metadata.brands.map((item) => ({{ ...item }}));
                    return result;
                  }};
                  define(uaData, 'getHighEntropyValues', () => getHighEntropyValues);
                }}
              }}
            }})();
        """
        await add_init_script(script=script)

    async def _prepare_visual_page(self, context: Any) -> Any:
        page = context.pages[0] if context.pages else await context.new_page()
        await self._maximize_browser_window(context, page)
        return page

    @staticmethod
    def _normalize_ip_value(value: Any) -> str | None:
        normalized = str(value or "").strip().strip("[]")
        if not normalized:
            return None
        if "%" in normalized:
            normalized = normalized.split("%", 1)[0]
        try:
            return str(ip_address(normalized))
        except ValueError:
            return None

    @staticmethod
    def _compare_proxy_exit_ips(
        observed_ips: set[str],
        expected_ips: set[str],
    ) -> tuple[bool | None, set[int]]:
        """Compare matching address families without treating a missing baseline as a leak."""

        if not observed_ips or not expected_ips:
            return None, {
                ip_address(item).version for item in observed_ips
            }
        observed_by_family = {
            version: {
                item for item in observed_ips if ip_address(item).version == version
            }
            for version in (4, 6)
        }
        expected_by_family = {
            version: {
                item for item in expected_ips if ip_address(item).version == version
            }
            for version in (4, 6)
        }
        missing_families = {
            version
            for version in (4, 6)
            if observed_by_family[version] and not expected_by_family[version]
        }
        comparable_families = {
            version
            for version in (4, 6)
            if observed_by_family[version] and expected_by_family[version]
        }
        if any(
            not observed_by_family[version].issubset(expected_by_family[version])
            for version in comparable_families
        ):
            return False, missing_families
        if missing_families or not comparable_families:
            return None, missing_families
        return True, set()

    async def _account_proxy_exit_ips(self, account: AccountRecord) -> set[str]:
        if not account.proxy_id:
            return set()
        get_proxy = getattr(self._store, "get_proxy", None)
        if not callable(get_proxy):
            return set()
        try:
            proxy = await get_proxy(account.proxy_id)
        except Exception as exc:
            logger.warning(
                "Unable to load proxy exit addresses for browser probe %s: %s",
                account.account_id,
                exc,
            )
            return set()
        if proxy is None:
            return set()

        stored_result: set[str] = set()
        for field_name in ("exit_ip", "exit_ipv4", "exit_ipv6"):
            normalized = self._normalize_ip_value(getattr(proxy, field_name, None))
            if normalized:
                stored_result.add(normalized)

        checked_at = getattr(proxy, "exit_checked_at", None)
        if isinstance(checked_at, datetime):
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=UTC)
            age_seconds = max(0.0, (datetime.now(UTC) - checked_at).total_seconds())
            if (
                stored_result
                and age_seconds
                <= getattr(
                    settings,
                    "browser_fingerprint_proxy_exit_ttl_seconds",
                    600,
                )
            ):
                return stored_result

        test_proxy = getattr(self._runtime, "test_proxy", None)
        to_config = getattr(proxy, "to_config", None)
        if not callable(test_proxy) or not callable(to_config):
            return stored_result
        try:
            tested = await test_proxy(to_config())
        except Exception as exc:
            logger.warning(
                "Unable to refresh proxy exit addresses for browser probe %s: %s",
                account.account_id,
                exc,
            )
            return set()
        if not getattr(tested, "ok", False):
            logger.warning(
                "Proxy exit refresh failed for browser probe %s: %s",
                account.account_id,
                getattr(tested, "message", "unknown error"),
            )
            return set()

        refreshed_result: set[str] = set()
        for field_name in ("exit_ip", "exit_ipv4", "exit_ipv6"):
            normalized = self._normalize_ip_value(getattr(tested, field_name, None))
            if normalized:
                refreshed_result.add(normalized)

        record_proxy_test = getattr(self._store, "record_proxy_test", None)
        connection_signature = getattr(proxy, "connection_signature", None)
        if callable(record_proxy_test):
            try:
                await record_proxy_test(
                    account.proxy_id,
                    ok=True,
                    message=str(getattr(tested, "message", "代理出口已刷新")),
                    latency_ms=getattr(tested, "latency_ms", None),
                    exit_ip=getattr(tested, "exit_ip", None),
                    exit_ipv4=getattr(tested, "exit_ipv4", None),
                    exit_ipv6=getattr(tested, "exit_ipv6", None),
                    exit_country=getattr(tested, "exit_country", None),
                    exit_region=getattr(tested, "exit_region", None),
                    exit_city=getattr(tested, "exit_city", None),
                    exit_isp=getattr(tested, "exit_isp", None),
                    exit_ipv6_country=getattr(tested, "exit_ipv6_country", None),
                    exit_ipv6_continent=getattr(tested, "exit_ipv6_continent", None),
                    platform_status=getattr(tested, "platform_status_code", None),
                    expected_connection=(
                        connection_signature()
                        if callable(connection_signature)
                        else None
                    ),
                )
            except Exception:
                logger.warning(
                    "Unable to persist refreshed proxy exit for browser probe %s",
                    account.account_id,
                    exc_info=True,
                )
        return refreshed_result

    @staticmethod
    async def _browser_context_exit_ips(page: Any) -> set[str]:
        """Resolve public egress IPs through the running browser context."""

        request_context = getattr(page, "request", None)
        get = getattr(request_context, "get", None)
        if not callable(get):
            return set()

        result: set[str] = set()
        for probe_url in getattr(settings, "proxy_ip_check_urls", ()):
            response: Any | None = None
            try:
                response = await get(
                    probe_url,
                    timeout=8_000,
                    fail_on_status_code=False,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                status = int(getattr(response, "status", 0) or 0)
                if status >= 400:
                    continue
                try:
                    payload = await response.json()
                except Exception:
                    payload = await response.text()
                raw = (
                    str(payload.get("ip") or payload.get("origin") or "")
                    if isinstance(payload, dict)
                    else str(payload)
                )
                for candidate in raw.replace("\n", ",").split(","):
                    normalized = IMVerificationManager._normalize_ip_value(candidate)
                    if not normalized:
                        continue
                    if ip_address(normalized).is_global:
                        result.add(normalized)
                if {ip_address(item).version for item in result} == {4, 6}:
                    break
            except Exception as exc:
                logger.info("Browser context IP probe failed via %s: %s", probe_url, exc)
            finally:
                dispose = getattr(response, "dispose", None)
                if callable(dispose):
                    with suppress(Exception):
                        await dispose()
        return result

    @staticmethod
    async def _capture_browser_fingerprint_snapshot(
        page: Any,
        identity: ClientIdentity,
        *,
        proxy_enabled: bool = False,
        expected_proxy_ips: set[str] | None = None,
    ) -> BrowserFingerprintSnapshotPayload | None:
        evaluate = getattr(page, "evaluate", None)
        if not callable(evaluate):
            return None
        try:
            result = await evaluate(
                FINGERPRINT_PROBE_SCRIPT,
                {
                    "stunUrl": getattr(
                        settings, "browser_fingerprint_probe_stun_url", ""
                    )
                    or None
                },
            )
        except Exception as exc:
            logger.warning("Unable to collect browser fingerprint snapshot: %s", exc)
            return None
        if not isinstance(result, dict) or not result.get("userAgent"):
            return None

        def optional_text(name: str) -> str | None:
            value = result.get(name)
            normalized = str(value or "").strip()
            return normalized or None

        def optional_number(name: str) -> float | None:
            value = result.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            return None

        def optional_bool(name: str) -> bool | None:
            value = result.get(name)
            return value if isinstance(value, bool) else None

        concurrency = optional_number("hardwareConcurrency")
        fonts = result.get("detectedFonts")
        candidates = result.get("webrtcCandidateTypes")
        candidate_addresses = result.get("webrtcCandidateAddresses")
        markers = result.get("automationWindowMarkers")
        navigator_webdriver = optional_bool("navigatorWebdriver")
        cdp_stack_probe_detected = optional_bool("cdpStackProbeDetected")
        webrtc_api_available = optional_bool("webrtcApiAvailable")
        private_candidate = bool(result.get("webrtcPrivateCandidateDetected"))
        public_candidate = bool(result.get("webrtcPublicCandidateDetected"))
        normalized_expected_ips = {
            normalized
            for item in (expected_proxy_ips or set())
            if (normalized := IMVerificationManager._normalize_ip_value(item))
        }
        normalized_candidate_ips = {
            normalized
            for item in (
                candidate_addresses if isinstance(candidate_addresses, list) else []
            )
            if (normalized := IMVerificationManager._normalize_ip_value(item))
        }
        webrtc_proxy_match, _ = IMVerificationManager._compare_proxy_exit_ips(
            normalized_candidate_ips,
            normalized_expected_ips,
        )
        webrtc_probe_configured = bool(
            getattr(settings, "browser_fingerprint_probe_stun_url", "")
        )
        browser_egress_ips = (
            await IMVerificationManager._browser_context_exit_ips(page)
            if proxy_enabled
            else set()
        )
        (
            browser_egress_match,
            browser_missing_proxy_families,
        ) = IMVerificationManager._compare_proxy_exit_ips(
            browser_egress_ips,
            normalized_expected_ips,
        )
        risk_findings: list[str] = []
        if navigator_webdriver:
            risk_findings.append("navigator.webdriver 暴露自动化状态")
        if isinstance(markers, list) and markers:
            risk_findings.append("页面环境存在自动化工具标记")
        if cdp_stack_probe_detected:
            risk_findings.append("页面检测到 CDP Runtime 调试特征")
        if identity.webrtc_policy == "disabled":
            if webrtc_api_available:
                risk_findings.append("WebRTC 严格阻断未完全生效")
        elif identity.webrtc_policy == "proxy_only":
            if not proxy_enabled:
                risk_findings.append("WebRTC 仅代理策略未配置账户代理")
            if private_candidate:
                risk_findings.append("WebRTC 返回了私网候选地址")
            if public_candidate and webrtc_proxy_match is False:
                risk_findings.append("WebRTC 公网候选地址与账户代理出口不一致")
            elif public_candidate and webrtc_proxy_match is None:
                risk_findings.append("WebRTC 公网候选地址尚无法与账户代理出口比对")
            if browser_egress_match is False:
                risk_findings.append("Chromium HTTP 出口与账户代理出口不一致")
            elif browser_missing_proxy_families:
                missing_labels = "、".join(
                    f"IPv{version}" for version in sorted(browser_missing_proxy_families)
                )
                risk_findings.append(
                    f"Chromium {missing_labels} 出口缺少账户代理基线，需复核"
                )
            elif browser_egress_match is None and webrtc_proxy_match is not True:
                risk_findings.append("Chromium HTTP 出口尚无法与账户代理基线比对")
        else:
            risk_findings.append("WebRTC 使用浏览器内核默认策略")

        hard_risk = bool(
            navigator_webdriver
            or cdp_stack_probe_detected
            or (isinstance(markers, list) and markers)
            or private_candidate
            or webrtc_proxy_match is False
            or browser_egress_match is False
            or (identity.webrtc_policy == "disabled" and webrtc_api_available)
        )
        if hard_risk:
            risk_status = "risk"
        elif risk_findings:
            risk_status = "warning"
        else:
            risk_status = "pass"
        return BrowserFingerprintSnapshotPayload(
            schema_version=3,
            browser_engine=identity.browser_engine,  # type: ignore[arg-type]
            browser_version=identity.normalized_browser_version,
            target_platform=identity.platform,  # type: ignore[arg-type]
            brand=identity.brand,  # type: ignore[arg-type]
            observed_platform=optional_text("observedPlatform"),
            user_agent=str(result["userAgent"]),
            ua_ch_platform=optional_text("uaChPlatform"),
            ua_ch_brands=(
                [str(item) for item in result.get("uaChBrands", []) if str(item).strip()]
                if isinstance(result.get("uaChBrands"), list)
                else []
            ),
            language=optional_text("language"),
            languages=(
                [str(item) for item in result.get("languages", []) if str(item).strip()]
                if isinstance(result.get("languages"), list)
                else []
            ),
            accept_language=identity.accept_language,
            timezone=optional_text("timezone"),
            hardware_concurrency=int(concurrency) if concurrency is not None else None,
            device_memory=optional_number("deviceMemory"),
            canvas_hash=optional_text("canvasHash"),
            webgl_vendor=optional_text("webglVendor"),
            webgl_renderer=optional_text("webglRenderer"),
            webgl_hash=optional_text("webglHash"),
            audio_hash=optional_text("audioHash"),
            fonts_hash=optional_text("fontsHash"),
            detected_fonts=(
                [str(item) for item in fonts if str(item).strip()]
                if isinstance(fonts, list)
                else []
            ),
            client_rects_hash=optional_text("clientRectsHash"),
            spoof_canvas=identity.spoof_canvas,
            spoof_webgl=identity.spoof_webgl,
            spoof_audio=identity.spoof_audio,
            spoof_fonts=identity.spoof_fonts,
            spoof_client_rects=identity.spoof_client_rects,
            webrtc_policy=identity.webrtc_policy,  # type: ignore[arg-type]
            webrtc_candidate_types=(
                [str(item) for item in candidates if str(item).strip()]
                if isinstance(candidates, list)
                else []
            ),
            webrtc_api_available=webrtc_api_available,
            webrtc_blocked=bool(result.get("webrtcBlocked")),
            webrtc_gathering_state=optional_text("webrtcGatheringState"),
            webrtc_private_candidate_detected=private_candidate,
            webrtc_public_candidate_detected=public_candidate,
            webrtc_proxy_match=webrtc_proxy_match,
            webrtc_probe_configured=webrtc_probe_configured,
            browser_egress_ips=sorted(browser_egress_ips),
            proxy_expected_ips=sorted(normalized_expected_ips),
            browser_egress_match=browser_egress_match,
            browser_egress_probe_source=(
                "browser_context_http" if browser_egress_ips else None
            ),
            navigator_webdriver=navigator_webdriver,
            automation_window_markers=(
                [str(item) for item in markers if str(item).strip()]
                if isinstance(markers, list)
                else []
            ),
            has_window_chrome=optional_bool("hasWindowChrome"),
            plugins_count=(
                int(value)
                if (value := optional_number("pluginsCount")) is not None
                else None
            ),
            notification_permission=optional_text("notificationPermission"),
            iframe_webdriver=optional_bool("iframeWebdriver"),
            worker_webdriver=optional_bool("workerWebdriver"),
            cdp_stack_probe_detected=cdp_stack_probe_detected,
            automation_protection_level=(
                "fingerprint_kernel"
                if identity.browser_engine == "fingerprint_chromium"
                else "system_compatibility"
            ),
            risk_status=risk_status,  # type: ignore[arg-type]
            risk_findings=risk_findings,
            config_revision=identity.config_revision,
            observed_at=datetime.now(UTC),
        )

    @staticmethod
    async def _maximize_browser_window(context: Any, page: Any) -> bool:
        create_session = getattr(context, "new_cdp_session", None)
        if not callable(create_session):
            return False
        session: Any | None = None
        try:
            session = await create_session(page)
            window = await session.send("Browser.getWindowForTarget")
            window_id = window.get("windowId") if isinstance(window, dict) else None
            if window_id is None:
                return False
            await session.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {"windowState": "maximized"},
                },
            )
            return True
        except Exception as exc:
            logger.warning("Unable to maximize VNC browser window: %s", exc)
            return False
        finally:
            if session is not None:
                with suppress(Exception):
                    await session.detach()

    async def _ensure_cdp_port_available(self, port: int | None = None) -> None:
        port = port or settings.account_browser_cdp_port
        if not 1 <= port <= 65535:
            raise IMVerificationError("账户浏览器 CDP 端口配置无效")
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=0.5,
            )
        except (OSError, TimeoutError):
            return
        del reader
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        raise IMVerificationBusyError(f"账户浏览器 CDP 端口 {port} 已被占用")

    async def _wait_for_cdp(self, port: int | None = None) -> None:
        effective_port = port or settings.account_browser_cdp_port
        for _ in range(30):
            if await self._cdp_is_healthy(effective_port):
                return
            await asyncio.sleep(0.1)
        raise IMVerificationError("账户浏览器已启动，但本机 CDP 未就绪")

    async def _cdp_is_healthy(self, port: int | None = None) -> bool:
        effective_port = port or settings.account_browser_cdp_port
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    "127.0.0.1", effective_port
                ),
                timeout=0.5,
            )
            writer.write(
                b"GET /json/version HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            await writer.drain()
            status_line = await asyncio.wait_for(reader.readline(), timeout=0.5)
            return b" 200 " in status_line
        except (OSError, TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                with suppress(Exception):
                    await writer.wait_closed()

    async def _inject_account_cookies(self, context: Any, account: AccountRecord) -> None:
        cookie_map = load_upstream_modules().trans_cookies(account.cookie)
        expected_unb = str(cookie_map.get("unb") or "")
        if not expected_unb:
            raise IMVerificationError("账户 Cookie 缺少 unb")
        await context.clear_cookies()
        cookies_to_add = [
            {
                "name": str(name),
                "value": str(value),
                "domain": ".goofish.com",
                "path": "/",
                "secure": True,
            }
            for name, value in cookie_map.items()
            if name and value is not None
        ]
        await context.add_cookies(cookies_to_add)
        applied = await context.cookies(
            [
                "https://www.goofish.com/",
                "https://h5api.m.goofish.com/",
                "https://passport.goofish.com/",
            ]
        )
        applied_map = {
            str(cookie.get("name")): str(cookie.get("value") or "")
            for cookie in applied
            if cookie.get("name")
        }
        if applied_map.get("unb") != expected_unb:
            raise IMVerificationError("账户 Cookie 注入校验失败：unb 不一致")
        missing = sorted(
            name
            for name, value in cookie_map.items()
            if name and value is not None and applied_map.get(str(name)) != str(value)
        )
        if missing:
            raise IMVerificationError(
                f"账户 Cookie 注入校验失败：{', '.join(missing[:5])}"
            )

    async def _start_proxy_bridge(self, account: AccountRecord) -> SocksBridge | None:
        self._validate_account_network(account)
        return await self._start_proxy_bridge_config(
            account.proxy,
            proxy_id=account.proxy_id,
        )

    async def _start_proxy_bridge_config(
        self,
        proxy: ProxyConfigPayload,
        *,
        proxy_id: str | None = None,
    ) -> SocksBridge | None:
        try:
            mode = validate_account_network_route(proxy_id, proxy)
        except AccountNetworkPolicyError as exc:
            raise IMVerificationError(str(exc)) from exc
        if mode == "direct":
            return None
        assert proxy.host and proxy.port
        auth = ""
        if proxy.username:
            auth = quote(proxy.username, safe="")
            if proxy.password:
                auth += f":{quote(proxy.password, safe='')}"
            auth += "@"
        bridge_scheme = "socks5" if proxy.scheme == "socks5h" else proxy.scheme
        bridge = SocksBridge(f"{bridge_scheme}://{auth}{proxy.host}:{proxy.port}")
        await bridge.start()
        return bridge

    def _request_token_once(self, account: AccountRecord) -> _TokenResult:
        mode = self._validate_account_network(account)
        upstream = load_upstream_modules()
        cookie_map = upstream.trans_cookies(account.cookie)
        expected_unb = str(cookie_map.get("unb") or "")
        stable_uuid = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"xianyu-im:{account.account_id}:{expected_unb}",
        )
        api = upstream.XianyuApis(cookie_map, f"{str(stable_uuid).upper()}-{expected_unb}")
        api.session.trust_env = False
        api.session.headers.update(
            {
                "User-Agent": account.client_identity.user_agent,
                "Accept-Language": account.client_identity.accept_language,
            }
        )
        proxy = account.proxy
        if mode == "socks5":
            assert proxy.host and proxy.port
            auth = ""
            if proxy.username:
                auth = quote(proxy.username, safe="")
                if proxy.password:
                    auth += f":{quote(proxy.password, safe='')}"
                auth += "@"
            proxy_url = f"{proxy.scheme}://{auth}{proxy.host}:{proxy.port}"
            api.session.proxies.update({"http": proxy_url, "https": proxy_url})
        try:
            response = api.get_token()
            updated_cookie = upstream.get_session_cookies_str(api.session)
            if updated_cookie:
                updated_map = upstream.trans_cookies(updated_cookie)
                if str(updated_map.get("unb") or "") != expected_unb:
                    updated_cookie = None
            data = response.get("data") if isinstance(response, dict) else None
            token = str(data.get("accessToken") or "") if isinstance(data, dict) else ""
            url = str(data.get("url") or "") if isinstance(data, dict) else ""
            response_text = str(response)
            reason_code = (
                "FAIL_SYS_USER_VALIDATE"
                if "FAIL_SYS_USER_VALIDATE" in response_text
                else "RGV587_ERROR" if "RGV587_ERROR" in response_text else None
            )
            return _TokenResult(
                token=token or None,
                verification_url=url or None,
                reason_code=reason_code,
                session_expired=(
                    "FAIL_SYS_SESSION_EXPIRED" in response_text or "Session过期" in response_text
                ),
                updated_cookie=updated_cookie,
            )
        finally:
            api.session.close()

    @staticmethod
    def _validate_account_network(account: AccountRecord) -> str:
        try:
            return account_network_mode(account)
        except AccountNetworkPolicyError as exc:
            raise IMVerificationError(str(exc)) from exc

    async def _persist_refreshed_cookie(
        self, account: AccountRecord, updated_cookie: str
    ) -> None:
        if updated_cookie == account.cookie:
            return
        persisted = await self._store.compare_and_set_account_cookie(
            account.account_id,
            account.cookie,
            updated_cookie,
            source="im_verification",
        )
        if persisted:
            account.cookie = updated_cookie

    async def _resume_without_browser(
        self, verification_id: str, account_id: str
    ) -> IMVerificationPayload:
        latest = await self._store.get_account(account_id)
        if latest is None:
            raise IMVerificationError("账户不存在")
        result = await self._runtime.start(latest, force_restart=True)
        if result.runtime.state == "risk_blocked":
            current = await self._store.get_latest_im_verification(account_id)
            if current is not None and current.status == "required":
                return self._decorate(current)
        if result.runtime.state != "online":
            raise IMVerificationError(result.runtime.message or "闲鱼 IM 恢复失败")
        completed = await self._store.set_im_verification_state(
            verification_id,
            "completed",
            "平台验证已解除，闲鱼 IM 已恢复在线",
        )
        assert completed is not None
        return self._decorate(completed)

    async def _expire_session(self, verification_id: str, expires_at: float) -> None:
        try:
            await asyncio.sleep(max(0, expires_at - time.time()))
            async with self._lock:
                active = self._active_for_verification(verification_id)
                if active is None:
                    return
                purpose = active.purpose
                if purpose == "account_browser" and active.expires_at > expires_at + 0.01:
                    return
                expired_at_maximum = bool(
                    purpose == "account_browser"
                    and active.max_expires_at is not None
                    and time.time() >= active.max_expires_at - 0.5
                )
                if purpose == "account_browser":
                    reconcile = await self._close_account_active_locked(
                        active,
                        cancel_timeout=False,
                    )
                else:
                    reconcile = None
                    await self._close_active_locked(cancel_timeout=False)
                if purpose == "qr_login":
                    session_id = verification_id.removeprefix("qr:")
                    self._qr_verifications[session_id] = self._qr_payload(
                        session_id,
                        "expired",
                        "远程登录验证会话已超时",
                        None,
                    )
                elif purpose == "account_browser":
                    session_id = verification_id.removeprefix("account-browser:")
                    payload = self._account_browser_sessions.get(session_id)
                    if payload is not None:
                        self._account_browser_sessions[session_id] = payload.model_copy(
                            update={
                                "status": "expired",
                                "message": (
                                    reconcile.message
                                    if reconcile is not None
                                    else (
                                        "平台账户浏览器已达到最长运行时间"
                                        if expired_at_maximum
                                        else "平台账户浏览器因长时间无操作已关闭"
                                    )
                                ),
                                "vnc_available": False,
                                "cdp_available": False,
                                "idle_expires_at": None,
                                "max_expires_at": None,
                                "expires_at": None,
                                **self._cookie_reconcile_payload_updates(reconcile),
                            }
                        )
                else:
                    await self._store.set_im_verification_state(
                        verification_id,
                        "expired",
                        "人工安全验证会话已超时",
                    )
        except asyncio.CancelledError:
            raise

    async def _close_active_locked(
        self,
        *,
        cancel_timeout: bool = True,
    ) -> _CookieReconcileResult | None:
        active = self._active
        self._active = None
        if active is None:
            return None
        return await self._close_session_resources(active, cancel_timeout=cancel_timeout)

    async def _close_account_active_locked(
        self,
        active: _ActiveSession,
        *,
        cancel_timeout: bool = True,
    ) -> _CookieReconcileResult | None:
        current = self._account_actives.get(active.verification_id)
        if current is active:
            self._account_actives.pop(active.verification_id, None)
        if self._active is active:
            self._active = None
        return await self._close_session_resources(active, cancel_timeout=cancel_timeout)

    async def _close_session_resources(
        self,
        active: _ActiveSession,
        *,
        cancel_timeout: bool,
    ) -> _CookieReconcileResult | None:
        if cancel_timeout and active.timeout_task is not None:
            active.timeout_task.cancel()
        self._tickets = {
            ticket: value
            for ticket, value in self._tickets.items()
            if value.verification_id != active.verification_id
        }
        browser_cookie: str | None = None
        capture_error: str | None = None
        if active.purpose == "account_browser" and active.account_id and active.baseline_cookie:
            try:
                browser_cookie = await self._read_account_browser_cookie(active)
            except Exception as exc:
                capture_error = str(exc)
                logger.warning(
                    "Unable to read account browser Cookie before close account=%s: %s",
                    active.account_id,
                    exc,
                )
        with suppress(Exception):
            await active.context.close()
        if active.bridge is not None:
            with suppress(Exception):
                await active.bridge.close()
        if active.desktop is not None:
            with suppress(Exception):
                await self._stop_visual_desktop(active.desktop)
        if active.temporary_profile is not None:
            with suppress(OSError):
                shutil.rmtree(active.temporary_profile)

        if (
            active.purpose != "account_browser"
            or not active.account_id
            or self._cookie_coordinator is None
        ):
            return None
        try:
            return await self._reconcile_account_browser_cookie(
                active,
                browser_cookie,
                capture_error=capture_error,
            )
        except Exception as exc:
            logger.exception(
                "Unable to reconcile account browser Cookie account=%s",
                active.account_id,
            )
            return _CookieReconcileResult(
                sync_status="failed",
                browser_status="unknown",
                local_status="not_checked",
                message=f"浏览器会话已关闭，Cookie 核对失败：{exc}",
            )

    @staticmethod
    def _serialize_cookie_map(cookie_map: dict[str, str]) -> str:
        return "; ".join(f"{key}={value}" for key, value in cookie_map.items())

    @staticmethod
    def _cookie_reconcile_payload_updates(
        reconcile: _CookieReconcileResult | None,
    ) -> dict[str, str]:
        if reconcile is None:
            return {}
        return {
            "cookie_sync_status": reconcile.sync_status,
            "browser_cookie_status": reconcile.browser_status,
            "local_cookie_status": reconcile.local_status,
        }

    @staticmethod
    def _cookie_maps_equal(left: str, right: str) -> bool:
        upstream = load_upstream_modules()
        return upstream.trans_cookies(left) == upstream.trans_cookies(right)

    async def _read_account_browser_cookie(self, active: _ActiveSession) -> str:
        browser_cookies = await active.context.cookies(
            [
                "https://www.goofish.com/",
                "https://h5api.m.goofish.com/",
                "https://passport.goofish.com/",
                "https://log.mmstat.com/",
            ]
        )
        browser_map = {
            str(cookie.get("name")): str(cookie.get("value") or "")
            for cookie in browser_cookies
            if cookie.get("name") and cookie.get("value") is not None
        }
        return self._serialize_cookie_map(browser_map)

    async def _check_web_cookie(
        self,
        account: AccountRecord,
        cookie: str,
    ) -> _CookieCheck:
        upstream = load_upstream_modules()
        cookie_map = upstream.trans_cookies(cookie)
        if not str(cookie_map.get("unb") or "") or not str(
            cookie_map.get("_m_h5_tk") or ""
        ):
            return _CookieCheck(
                state="invalid",
                cookie=cookie,
                message="Cookie 缺少 Web 平台必要字段",
                error_kind="suspected_expired",
            )
        coordinator = self._cookie_coordinator
        validator = getattr(coordinator, "validate_cookie", None)
        if not callable(validator):
            return _CookieCheck(
                state="unknown",
                cookie=cookie,
                message="Web Cookie 验证服务未配置",
                error_kind="validator_unavailable",
            )
        try:
            result = await validator(account, cookie)
            return _CookieCheck(
                state="valid",
                cookie=result.new_cookie,
                result=result,
                message=result.message,
            )
        except CookieRenewalError as exc:
            state = (
                "invalid"
                if exc.kind
                in {"suspected_expired", "auth_expired", "verification_required"}
                else "unknown"
            )
            return _CookieCheck(
                state=state,
                cookie=cookie,
                message=str(exc),
                error_kind=exc.kind,
            )
        except Exception as exc:
            logger.warning(
                "Unable to validate Web Cookie candidate account=%s: %s",
                account.account_id,
                exc,
            )
            return _CookieCheck(
                state="unknown",
                cookie=cookie,
                message=str(exc),
                error_kind="internal_error",
            )

    async def _persist_validated_browser_cookie(
        self,
        account: AccountRecord,
        check: _CookieCheck,
        *,
        message: str,
    ) -> bool:
        coordinator = self._cookie_coordinator
        persist = getattr(coordinator, "persist_validated_cookie", None)
        if not callable(persist) or check.result is None:
            return False
        current = account
        for _ in range(2):
            persisted = await persist(
                current,
                expected_cookie=current.cookie,
                result=check.result,
                source="account_browser",
                message=message,
            )
            if persisted:
                return True
            latest = await self._store.get_account(account.account_id)
            if latest is None:
                return False
            expected_unb = str(
                load_upstream_modules().trans_cookies(account.cookie).get("unb") or ""
            )
            latest_unb = str(
                load_upstream_modules().trans_cookies(latest.cookie).get("unb") or ""
            )
            if expected_unb and latest_unb and latest_unb != expected_unb:
                return False
            current = latest
        return False

    async def _persist_validated_local_cookie(
        self,
        account: AccountRecord,
        check: _CookieCheck,
    ) -> None:
        coordinator = self._cookie_coordinator
        persist = getattr(coordinator, "persist_validated_cookie", None)
        if not callable(persist) or check.result is None:
            return
        await persist(
            account,
            expected_cookie=account.cookie,
            result=check.result,
            source="account_browser_local_validation",
            message="VNC 结束核对：浏览器凭据异常，已保留并验证本地 Web Cookie",
        )

    async def _trigger_account_browser_auth_recovery(
        self,
        account: AccountRecord,
        browser_check: _CookieCheck,
        local_check: _CookieCheck,
    ) -> None:
        coordinator = self._cookie_coordinator
        trigger = getattr(coordinator, "handle_auth_expired", None)
        if callable(trigger):
            await trigger(
                account.account_id,
                source="account_browser",
                message=(
                    "VNC 结束核对发现浏览器与本地 Web Cookie 均异常："
                    f"浏览器={browser_check.message or browser_check.error_kind or '异常'}；"
                    f"本地={local_check.message or local_check.error_kind or '异常'}"
                ),
            )

    async def _reconcile_account_browser_cookie(
        self,
        active: _ActiveSession,
        browser_cookie: str | None,
        *,
        capture_error: str | None = None,
    ) -> _CookieReconcileResult:
        if not active.account_id:
            return _CookieReconcileResult(
                sync_status="failed",
                browser_status="not_checked",
                local_status="not_checked",
                message="浏览器会话已关闭，但账户标识缺失，未更新 Cookie",
            )
        account = await self._store.get_account(active.account_id)
        if account is None:
            return _CookieReconcileResult(
                sync_status="failed",
                browser_status="not_checked",
                local_status="not_checked",
                message="浏览器会话已关闭，但账户已不存在，未更新 Cookie",
            )

        upstream = load_upstream_modules()
        baseline_map = upstream.trans_cookies(active.baseline_cookie or "")
        local_map = upstream.trans_cookies(account.cookie)
        browser_map = upstream.trans_cookies(browser_cookie or "")
        expected_unb = str(baseline_map.get("unb") or local_map.get("unb") or "")
        browser_unb = str(browser_map.get("unb") or "")
        local_unb = str(local_map.get("unb") or "")
        if (
            (expected_unb and browser_unb and browser_unb != expected_unb)
            or (expected_unb and local_unb and local_unb != expected_unb)
        ):
            return _CookieReconcileResult(
                sync_status="account_mismatch",
                browser_status="invalid",
                local_status="unknown",
                message="浏览器会话已关闭，检测到闲鱼账号不一致，已拒绝更新 Cookie",
            )

        if browser_cookie:
            browser_check = await self._check_web_cookie(account, browser_cookie)
        else:
            browser_check = _CookieCheck(
                state="unknown" if capture_error else "invalid",
                cookie="",
                message=capture_error or "浏览器未返回 Cookie",
                error_kind="capture_failed" if capture_error else "suspected_expired",
            )

        if browser_cookie and self._cookie_maps_equal(browser_cookie, account.cookie):
            local_check = browser_check
        else:
            local_check = await self._check_web_cookie(account, account.cookie)

        if browser_check.state == "valid":
            both_valid = local_check.state == "valid"
            if both_valid:
                decision_message = (
                    "VNC 结束核对：浏览器与本地 Cookie 均正常，已采用浏览器最新 Cookie"
                )
            elif local_check.state == "invalid":
                decision_message = (
                    "VNC 结束核对：浏览器 Cookie 正常、本地 Cookie 异常，已采用浏览器 Cookie"
                )
            else:
                decision_message = (
                    "VNC 结束核对：浏览器 Cookie 正常、本地状态暂未确认，"
                    "已采用验证通过的浏览器 Cookie"
                )
            persisted = await self._persist_validated_browser_cookie(
                account,
                browser_check,
                message=decision_message,
            )
            if persisted:
                changed = not self._cookie_maps_equal(
                    browser_check.cookie,
                    account.cookie,
                )
                return _CookieReconcileResult(
                    sync_status=(
                        "updated_from_browser" if changed else "refreshed_from_browser"
                    ),
                    browser_status=browser_check.state,
                    local_status=local_check.state,
                    message=decision_message,
                )
            return _CookieReconcileResult(
                sync_status="unknown",
                browser_status=browser_check.state,
                local_status=local_check.state,
                message="浏览器会话已关闭，Cookie 核对期间本地凭据发生变化，未完成更新",
            )

        if local_check.state == "valid":
            await self._persist_validated_local_cookie(account, local_check)
            return _CookieReconcileResult(
                sync_status="kept_local",
                browser_status=browser_check.state,
                local_status=local_check.state,
                message="VNC 结束核对：浏览器 Cookie 异常，已保留本地正常 Cookie",
            )

        if browser_check.state == "invalid" and local_check.state == "invalid":
            await self._trigger_account_browser_auth_recovery(
                account,
                browser_check,
                local_check,
            )
            return _CookieReconcileResult(
                sync_status="auth_recovery",
                browser_status=browser_check.state,
                local_status=local_check.state,
                message="VNC 结束核对：浏览器与本地 Cookie 均异常，已启动认证恢复链路",
            )

        return _CookieReconcileResult(
            sync_status="unknown",
            browser_status=browser_check.state,
            local_status=local_check.state,
            message="浏览器会话已关闭，Cookie 状态暂时无法确认，未覆盖本地凭据，请稍后复核",
        )

    def _decorate(self, payload: IMVerificationPayload | None) -> IMVerificationPayload | None:
        if payload is None:
            return None
        availability_error = self.availability_error()
        return payload.model_copy(
            update={
                "browser_available": availability_error is None,
                "browser_error": availability_error,
                "vnc_available": bool(
                    self._active is not None
                    and self._active.verification_id == payload.verification_id
                    and payload.status == "ready"
                ),
            }
        )

    def _decorate_qr(
        self, payload: XianyuQRBrowserVerificationPayload
    ) -> XianyuQRBrowserVerificationPayload:
        availability_error = self.availability_error()
        verification_id = self._qr_verification_id(payload.session_id)
        return payload.model_copy(
            update={
                "browser_available": availability_error is None,
                "browser_error": availability_error,
                "vnc_available": bool(
                    self._active is not None
                    and self._active.verification_id == verification_id
                    and payload.status == "ready"
                ),
            }
        )

    def _decorate_account_browser(
        self, payload: AccountBrowserSessionPayload | None
    ) -> AccountBrowserSessionPayload | None:
        if payload is None:
            return None
        availability_error = self.availability_error()
        verification_id = self._account_browser_verification_id(payload.session_id)
        active = self._account_actives.get(verification_id)
        is_ready = bool(
            active is not None
            and active.verification_id == verification_id
            and active.purpose == "account_browser"
            and payload.status == "ready"
        )
        current_url = payload.current_url
        if is_ready and active is not None:
            current_url = str(active.page.url or current_url or "") or None
        return payload.model_copy(
            update={
                "current_url": current_url,
                "browser_available": availability_error is None,
                "browser_error": availability_error,
                "vnc_available": is_ready,
                "cdp_available": bool(
                    is_ready
                    and settings.account_browser_cdp_enabled
                    and payload.cdp_available
                ),
            }
        )

    @staticmethod
    def _qr_verification_id(session_id: str) -> str:
        return f"qr:{session_id}"

    @staticmethod
    def _account_browser_verification_id(session_id: str) -> str:
        return f"account-browser:{session_id}"

    @staticmethod
    def _account_browser_session_id(active: _ActiveSession) -> str | None:
        if not active.verification_id.startswith("account-browser:"):
            return None
        return active.verification_id.removeprefix("account-browser:")

    @staticmethod
    def _active_profile_key(active: _ActiveSession | None) -> str | None:
        if active is None:
            return None
        if active.temporary_profile is not None:
            return browser_profile_storage.qr_profile_key(active.temporary_profile.name)
        if active.account_id:
            return browser_profile_storage.account_profile_key(active.account_id)
        return None

    @staticmethod
    def _active_session_id(active: _ActiveSession | None) -> str | None:
        if active is None:
            return None
        if active.verification_id.startswith("account-browser:"):
            return active.verification_id.removeprefix("account-browser:")
        if active.verification_id.startswith("qr:"):
            return active.verification_id.removeprefix("qr:")
        return active.verification_id

    @staticmethod
    def _account_browser_payload(
        session_id: str,
        account_id: str,
        status: str,
        message: str | None,
        proxy_enabled: bool,
        started_at: float | None,
        expires_at: float | None,
        *,
        current_url: str | None = None,
        cdp_available: bool = False,
        fingerprint_snapshot: BrowserFingerprintSnapshotPayload | None = None,
        fingerprint_detection_status: str = "pending",
        fingerprint_detection_error: str | None = None,
        last_activity_at: float | None = None,
        max_expires_at: float | None = None,
    ) -> AccountBrowserSessionPayload:
        return AccountBrowserSessionPayload(
            session_id=session_id,
            account_id=account_id,
            status=status,  # type: ignore[arg-type]
            message=message,
            current_url=current_url,
            proxy_enabled=proxy_enabled,
            cdp_available=cdp_available,
            fingerprint_snapshot=fingerprint_snapshot,
            fingerprint_detection_status=fingerprint_detection_status,  # type: ignore[arg-type]
            fingerprint_detection_error=fingerprint_detection_error,
            started_at=(
                datetime.fromtimestamp(started_at, UTC) if started_at is not None else None
            ),
            last_activity_at=(
                datetime.fromtimestamp(last_activity_at, UTC)
                if last_activity_at is not None
                else None
            ),
            idle_expires_at=(
                datetime.fromtimestamp(expires_at, UTC) if expires_at is not None else None
            ),
            max_expires_at=(
                datetime.fromtimestamp(max_expires_at, UTC)
                if max_expires_at is not None
                else None
            ),
            expires_at=(
                datetime.fromtimestamp(expires_at, UTC) if expires_at is not None else None
            ),
        )

    @staticmethod
    def _qr_payload(
        session_id: str,
        status: str,
        message: str | None,
        expires_at: float | None,
    ) -> XianyuQRBrowserVerificationPayload:
        return XianyuQRBrowserVerificationPayload(
            session_id=session_id,
            status=status,  # type: ignore[arg-type]
            message=message,
            expires_at=(
                datetime.fromtimestamp(expires_at, UTC) if expires_at is not None else None
            ),
        )

    @staticmethod
    def _remove_stale_profile_locks(profile: Path) -> None:
        profile_text = str(profile.resolve())
        for _process_id, arguments in iter_process_arguments():
            if profile_text in arguments or f"--user-data-dir={profile_text}" in arguments:
                raise IMVerificationBusyError("账户浏览器 Profile 正在被使用")
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = profile / name
            with suppress(FileNotFoundError, OSError):
                path.unlink()
