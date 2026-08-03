"""FastAPI entrypoint for the Xianyu web admin backend."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Literal

from apps.runtime_paths import resource_path
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException

from integrations.xianyu_core.images import (
    MAX_IMAGE_INPUT_BYTES,
    ImageValidationError,
)
from integrations.xianyu_core import OrderActionError, ProductPublishError
from .cookie_renewal_manager import CookieRenewalCooldownError, CookieRenewalManager
from .executors import (
    run_browser_blocking,
    run_external_blocking,
    run_media_blocking,
    run_qr_blocking,
    shutdown_executors,
)
from .browser_binaries import (
    BrowserBinaryError,
    browser_binary_manager,
    browser_runtime_payload,
    standard_browser_binary_manager,
)
from .browser_profiles import BrowserProfileStorage
from .account_migrations import (
    AccountMigrationArchiveService,
    AccountMigrationError,
    StagedAccountMigration,
)
from .chatwoot import (
    ChatwootIntegrationError,
    ChatwootRepository,
    _download_xianyu_audio,
    _extract_xianyu_audio_url,
    accept_chatwoot_webhook,
    enqueue_account_metadata_sync,
    enqueue_account_status_sync,
    execute_account_alert_task,
    reconcile_chatwoot_read_states,
    test_chatwoot_config,
    save_chatwoot_config,
)
from .queue import enqueue_background_task
from .process_health import event_loop_monitor
from .product_image_archives import ProductImageArchiveError, import_product_image_archive
from .product_images import product_image_storage
from .qr_login import QRLoginError, QRLoginSession
from .runtime import AccountRuntimeManager
from .settings import settings
from .schemas import (
    AIProviderSettingPayload,
    AIProviderSettingUpdatePayload,
    AccountBrowserSessionPayload,
    AccountBrowserTextPastePayload,
    AccountBrowserIdentityPayload,
    AccountAutoReplyStatusPayload,
    AccountAutoReplyUpdatePayload,
    AccountCreatePayload,
    AccountCookiePayload,
    AccountConnectionHealthPayload,
    AccountMigrationImportPayload,
    AccountMigrationPreviewPayload,
    AccountPayload,
    AccountReorderPayload,
    AccountUpdatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
    AuthBootstrapPayload,
    AuthLoginPayload,
    ClientAccessPayload,
    AuthSetupStatusPayload,
    AuthTokenPayload,
    AuditLogPayload,
    AutoReplyLogPayload,
    AutoReplyPreviewRequestPayload,
    AutoReplyPreviewResultPayload,
    AutoReplyRuleCreatePayload,
    AutoReplyRuleIssuePayload,
    AutoReplyRulePayload,
    AutoReplyRuleReorderPayload,
    AutoReplyRuleUpdatePayload,
    BackgroundTaskCreatePayload,
    BackgroundTaskPayload,
    BrowserProfileActionPayload,
    BrowserProfileCleanupPayload,
    BrowserProfilePayload,
    BrowserRuntimeSettingPayload,
    BrowserBinaryActivatePayload,
    BrowserBinaryPayload,
    StandardBrowserActivatePayload,
    ConversationPayload,
    ConversationPagePayload,
    ChatwootConfigPayload,
    ChatwootConfigUpdatePayload,
    ChatwootTestResultPayload,
    ChatwootWebhookAcceptedPayload,
    WebNotificationConfigPayload,
    WebNotificationConfigUpdatePayload,
    CookieRenewalStatusPayload,
    DeliveryAutomationSettingPayload,
    DeliveryAutomationSettingUpdatePayload,
    DeliveryPreparePayload,
    DeliveryPreflightPayload,
    DeliveryRecordPayload,
    DeliverySendResultPayload,
    DeliveryTemplateCreatePayload,
    DeliveryTemplatePayload,
    DeliveryTemplateUpdatePayload,
    HealthPayload,
    IMVerificationPayload,
    IMVerificationTicketPayload,
    MessageCardPayload,
    MessagePayload,
    MessagePagePayload,
    ManualTakeoverPayload,
    ManualTakeoverStatusPayload,
    OrderDeliveryPreviewPayload,
    OrderDeliveryPreviewRequest,
    OrderDetailPayload,
    OrderPayload,
    OrderOperationExecutePayload,
    OrderOperationExecuteRequest,
    OrderOperationPreviewPayload,
    OrderOperationPreviewRequest,
    OrderAccountSummaryPayload,
    OrderSyncEnqueuePayload,
    OrderSyncRequestPayload,
    OrderSyncRunPayload,
    OrderSyncSettingPayload,
    OrderSyncSettingUpdatePayload,
    ProductDraftCreatePayload,
    ProductDraftPayload,
    ProductDraftUpdatePayload,
    ProductAccountSummaryPayload,
    ProductItemOperationRequestPayload,
    ProductItemPayload,
    ProductLocalCleanupPayload,
    ProductImageArchiveRejectedPayload,
    ProductImageArchiveUploadPayload,
    ProductImageAssetPayload,
    ProductLocationListPayload,
    ProductRegionCatalogPayload,
    ProductPublishJobCreatePayload,
    ProductPublishEnqueuePayload,
    ProductPublishRetryPayload,
    ProductPublishTaskCreatePayload,
    ProductPublishTaskPayload,
    ProductOperationEnqueuePayload,
    ProductOperationRunPayload,
    ProductSyncRequestPayload,
    ProductSyncSettingPayload,
    ProductSyncSettingUpdatePayload,
    ProcessHealthPayload,
    PublishAddressCreatePayload,
    PublishAddressGroupCreatePayload,
    PublishAddressGroupPayload,
    PublishAddressGroupUpdatePayload,
    PublishAddressPayload,
    PublishAddressRegionSelectionPayload,
    PublishAddressRegionSelectionResultPayload,
    PublishAddressUpdatePayload,
    ProxyCreatePayload,
    ProxyConfigPayload,
    ProxyPayload,
    ProxyTestPayload,
    ProxyUpdatePayload,
    PlatformBlacklistPayload,
    PlatformBlacklistUpdatePayload,
    QuickPhraseCreatePayload,
    QuickPhrasePayload,
    QuickPhraseUpdatePayload,
    RecallMessageResultPayload,
    RuntimeEventPayload,
    RuntimeStatusPayload,
    RealtimeTicketPayload,
    SendImageResultPayload,
    SendTextPayload,
    SendTextResultPayload,
    UserCreatePayload,
    UserPayload,
    UserPreferenceUpdatePayload,
    UserUpdatePayload,
    XianyuQRStartPayload,
    XianyuQRBrowserVerificationPayload,
    XianyuQRStatusPayload,
)
from .security import create_access_token, verify_access_token
from .realtime import realtime_broker, relay_cross_process_events
from .product_publish_service import list_platform_product_locations
from .product_management_service import (
    ProductLocalCleanupConflict,
    ProductManagementRepository,
    create_and_enqueue_product_run,
)
from .product_management_scheduler import ProductManagementScheduler
from .order_management_service import (
    OrderManagementRepository,
    create_and_enqueue_order_sync,
)
from .order_management_scheduler import OrderManagementScheduler
from .active_order_refresh_scheduler import ActiveOrderRefreshScheduler
from .order_action_service import (
    OrderActionConflict,
    OrderActionRepository,
    OrderActionService,
)
from .product_regions import product_region_catalog
from .store import AccountStore, ProxyAssignmentConflict
from .web_notifications import (
    MAX_WEB_NOTIFICATION_SOUND_BYTES,
    WebNotificationRepository,
    WebNotificationSoundError,
    web_notification_sound_storage,
)
from .im_verification import (
    IMVerificationBusyError,
    IMVerificationError,
    IMVerificationManager,
)


store = AccountStore()
chatwoot_repository = ChatwootRepository(store.session_factory)
web_notification_repository = WebNotificationRepository(store.session_factory)
runtime_manager = AccountRuntimeManager(store)
cookie_renewal_manager = CookieRenewalManager(store, runtime_manager)
im_verification_manager = IMVerificationManager(
    store,
    runtime_manager,
    cookie_renewal_manager,
)
account_migration_service = AccountMigrationArchiveService(
    BrowserProfileStorage(settings.im_verification_profile_dir)
)
account_migration_lock = asyncio.Lock()
runtime_manager.set_cookie_auth_failure_handler(
    lambda account_id, source, message: cookie_renewal_manager.handle_auth_expired(
        account_id,
        source=source,
        message=message,
    )
)
qr_login_sessions: dict[str, QRLoginSession] = {}
qr_finalize_locks: dict[str, asyncio.Lock] = {}
qr_poll_locks: dict[str, asyncio.Lock] = {}
qr_initialize_tasks: dict[str, asyncio.Task[None]] = {}
qr_session_keys: dict[str, str] = {}
qr_start_lock = asyncio.Lock()
qr_cleanup_task: asyncio.Task[None] | None = None
chatwoot_reconcile_task: asyncio.Task[None] | None = None
chatwoot_read_sync_task: asyncio.Task[None] | None = None
realtime_tickets: dict[str, tuple[str, float]] = {}
realtime_ticket_lock = asyncio.Lock()
publish_enqueue_locks: dict[str, asyncio.Lock] = {}
delivery_enqueue_locks: dict[str, asyncio.Lock] = {}
proxy_test_locks: dict[str, asyncio.Lock] = {}
product_management_repository = ProductManagementRepository(store.session_factory)
product_management_scheduler = ProductManagementScheduler(
    store, product_management_repository
)
order_management_repository = OrderManagementRepository(store.session_factory)
order_management_scheduler = OrderManagementScheduler(
    store, order_management_repository
)
order_action_repository = OrderActionRepository(store.session_factory)
order_action_service = OrderActionService(store, order_action_repository)
active_order_refresh_scheduler = ActiveOrderRefreshScheduler(
    store, order_action_service
)
logger = logging.getLogger(__name__)


def _product_publish_persistence_error(account_id: str) -> HTTPException:
    error_id = secrets.token_hex(6)
    logger.exception(
        "Failed to persist product publish task account=%s error_id=%s",
        account_id,
        error_id,
    )
    return HTTPException(
        status_code=500,
        detail={
            "code": "PRODUCT_TASK_PERSIST_FAILED",
            "message": "发布任务保存失败，请稍后重试",
            "error_id": error_id,
        },
    )


def _qr_status_payload(session: QRLoginSession) -> XianyuQRStatusPayload:
    return XianyuQRStatusPayload(
        session_id=session.session_id,
        status=session.status,  # type: ignore[arg-type]
        code_content=session.code_content if session.status in {"pending", "scanned"} else None,
        face_code_content=(
            session.face_code_content if session.status == "verification_required" else None
        ),
        challenge_type=getattr(session, "challenge_type", "none"),  # type: ignore[arg-type]
        expires_in=session.expires_in,
        account_id=session.account_id,
        runtime_state=session.runtime_state,  # type: ignore[arg-type]
        error=session.error,
    )


def _qr_session_key(
    account_id: str | None,
    client_request_id: str | None,
    owner_user_id: str | None,
    proxy_id: str | None,
) -> str:
    if account_id:
        return f"account:{account_id}"
    request_key = client_request_id or f"owner:{owner_user_id or 'anonymous'}"
    return f"new:{request_key}:{proxy_id or '-'}"


def _discard_qr_session(session_id: str) -> None:
    session = qr_login_sessions.pop(session_id, None)
    if session is not None:
        close = getattr(session, "close", None)
        if callable(close):
            close()
    qr_finalize_locks.pop(session_id, None)
    qr_poll_locks.pop(session_id, None)
    qr_session_keys.pop(session_id, None)


async def _initialize_qr_session(session: QRLoginSession) -> None:
    try:
        await run_qr_blocking(session.start)
        if session.status == "initializing":
            session.status = "pending"
    except QRLoginError as exc:
        session.fail(f"HTTP 扫码登录初始化失败：{exc}")
    except Exception as exc:
        session.fail(f"HTTP 扫码登录初始化失败：{exc.__class__.__name__}")
    finally:
        qr_initialize_tasks.pop(session.session_id, None)
        if session.session_id not in qr_login_sessions:
            session.close()


async def _cleanup_qr_sessions_loop() -> None:
    while True:
        await asyncio.sleep(15)
        for session_id, session in list(qr_login_sessions.items()):
            initializing = session_id in qr_initialize_tasks
            polling = qr_poll_locks.get(session_id)
            if (session.expires_in <= 0 or session.finalized) and not initializing and not (
                polling and polling.locked()
            ):
                _discard_qr_session(session_id)


async def _enqueue_chatwoot_reconciliation(reason: str) -> None:
    config = await chatwoot_repository.get_config()
    if config is None or not config["platform_enabled"]:
        return
    for account in await store.list_accounts():
        if not account.enabled or not account.chat_enabled:
            continue
        await enqueue_account_metadata_sync(
            store,
            account_id=account.account_id,
            reason=reason,
        )
        if account.runtime is not None:
            await enqueue_account_status_sync(
                store,
                account_id=account.account_id,
                state=account.runtime.state,
                message=account.runtime.message,
            )


async def _chatwoot_reconcile_loop() -> None:
    while True:
        await asyncio.sleep(settings.chatwoot_reconcile_interval_seconds)
        try:
            await _enqueue_chatwoot_reconciliation("periodic-reconcile")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic Chatwoot reconciliation failed")


async def _chatwoot_read_sync_loop() -> None:
    while True:
        try:
            result = await reconcile_chatwoot_read_states(store)
            for event in result.get("events", []):
                await realtime_broker.publish(event)
            errors = result.get("errors", [])
            if errors:
                logger.warning(
                    "Chatwoot read reconciliation completed with %s error(s): %s",
                    len(errors),
                    "; ".join(str(error) for error in errors[:3]),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic Chatwoot read reconciliation failed")
        await asyncio.sleep(settings.chatwoot_read_sync_interval_seconds)


async def _run_startup_maintenance() -> None:
    try:
        await runtime_manager.restore_enabled_accounts()
        await store.backfill_unknown_text_cards()
        await store.reconcile_conversation_summaries()
        await store.backfill_peer_names()
        await store.backfill_message_contexts()
        await store.backfill_orders()
        await _enqueue_chatwoot_reconciliation("startup-reconcile")
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Startup maintenance failed")


async def _persist_qr_login_credentials(
    session: QRLoginSession,
    cookie: str,
) -> None:
    from integrations.xianyu_core.upstream import load_upstream_modules

    upstream = load_upstream_modules()
    new_unb = str(upstream.trans_cookies(cookie).get("unb") or "")
    if not new_unb:
        raise QRLoginError("validated login did not contain unb")

    if session.account_id:
        current = await store.get_account(session.account_id)
        if current is None:
            raise QRLoginError("account no longer exists")
        expected_unb = str(upstream.trans_cookies(current.cookie).get("unb") or "")
        if expected_unb and new_unb != expected_unb:
            raise QRLoginError("扫码登录的闲鱼账号与当前账户不一致")
        try:
            persisted = await store.compare_and_set_account_cookie(
                current.account_id,
                current.cookie,
                cookie,
                source="qr_login",
                proxy_id=session.proxy_id,
            )
        except ProxyAssignmentConflict as exc:
            raise QRLoginError(str(exc)) from exc
        if not persisted:
            raise QRLoginError("账户 Cookie 已被其他任务更新，请重新开始登录")
        account = await store.get_account(current.account_id)
    else:
        try:
            account = await store.create_account(
                AccountCreatePayload(
                    remark=session.remark,
                    cookie=cookie,
                    proxy_id=session.proxy_id,
                    browser_identity=session.browser_identity,
                ),
                cookie_source="qr_login",
                automation_owner_user_id=session.automation_owner_user_id,
            )
        except ProxyAssignmentConflict as exc:
            raise QRLoginError(str(exc)) from exc
    if account is None:
        raise QRLoginError("failed to save account credentials")
    session.account_id = account.account_id
    await cookie_renewal_manager.mark_login_success(account.account_id)
    account = await store.get_account(account.account_id)
    if account is None:
        raise QRLoginError("account no longer exists after login")
    runtime_state = account.runtime.state if account.runtime else "stopped"
    account_payload = account.to_payload()
    if account.enabled:
        account_payload = await runtime_manager.start(account, force_restart=True)
        runtime_state = account_payload.runtime.state
    session.mark_completed(runtime_state)
    session.close()
    await realtime_broker.publish(
        {
            "event": "account_upsert",
            "account_id": account_payload.account_id,
            "data": account_payload.model_dump(mode="json"),
        }
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global chatwoot_read_sync_task, chatwoot_reconcile_task, qr_cleanup_task
    await event_loop_monitor.start()
    await cookie_renewal_manager.start()
    await product_management_scheduler.start()
    await order_management_scheduler.start()
    await active_order_refresh_scheduler.start()
    startup_task = asyncio.create_task(
        _run_startup_maintenance(),
        name="xianyu-startup-maintenance",
    )
    qr_cleanup_task = asyncio.create_task(
        _cleanup_qr_sessions_loop(),
        name="xianyu-qr-session-cleanup",
    )
    chatwoot_reconcile_task = asyncio.create_task(
        _chatwoot_reconcile_loop(),
        name="xianyu-chatwoot-reconcile",
    )
    chatwoot_read_sync_task = asyncio.create_task(
        _chatwoot_read_sync_loop(),
        name="xianyu-chatwoot-read-sync",
    )
    realtime_relay_task = asyncio.create_task(
        relay_cross_process_events(),
        name="xianyu-cross-process-realtime-relay",
    )
    try:
        yield
    finally:
        realtime_relay_task.cancel()
        await asyncio.gather(realtime_relay_task, return_exceptions=True)
        startup_task.cancel()
        await asyncio.gather(startup_task, return_exceptions=True)
        if chatwoot_reconcile_task is not None:
            chatwoot_reconcile_task.cancel()
            with suppress(asyncio.CancelledError):
                await chatwoot_reconcile_task
            chatwoot_reconcile_task = None
        if chatwoot_read_sync_task is not None:
            chatwoot_read_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await chatwoot_read_sync_task
            chatwoot_read_sync_task = None
        if qr_cleanup_task is not None:
            qr_cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await qr_cleanup_task
            qr_cleanup_task = None
        initialize_tasks = tuple(qr_initialize_tasks.values())
        for task in initialize_tasks:
            task.cancel()
        if initialize_tasks:
            await asyncio.gather(*initialize_tasks, return_exceptions=True)
        qr_initialize_tasks.clear()
        for session in qr_login_sessions.values():
            session.close()
        qr_login_sessions.clear()
        qr_finalize_locks.clear()
        qr_poll_locks.clear()
        qr_session_keys.clear()
        realtime_tickets.clear()
        await im_verification_manager.shutdown()
        await cookie_renewal_manager.shutdown()
        await active_order_refresh_scheduler.shutdown()
        await order_management_scheduler.shutdown()
        await product_management_scheduler.shutdown()
        await runtime_manager.shutdown()
        await event_loop_monitor.shutdown()
        shutdown_executors()


app = FastAPI(title="Xianyu Admin API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_EXEMPT_PATHS = {
    "/api/health",
    "/api/ready",
    "/api/auth/setup-status",
    "/api/auth/client-info",
    "/api/auth/login",
    "/api/auth/bootstrap",
}
ADMIN_ONLY_PREFIXES = (
    "/api/internal",
    "/api/users",
    "/api/tasks",
    "/api/audit-logs",
    "/api/settings/ai-provider",
    "/api/settings/browser-runtime",
    "/api/settings/message-services",
    "/api/account-migrations",
)


def _normalize_browser_identity_for_save(
    identity: AccountBrowserIdentityPayload,
    *,
    apply_standard_default: bool = False,
) -> AccountBrowserIdentityPayload:
    writable = identity.writable_copy()
    if writable.browser_engine == "system_chromium":
        version = str(writable.browser_version or "").strip()
        if not version and apply_standard_default:
            version = str(standard_browser_binary_manager.active_version() or "").strip()
        if version:
            try:
                standard_browser_binary_manager.resolve_executable(version)
            except BrowserBinaryError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return writable.model_copy(
            update={"browser_version": version or None, "fingerprint_seed": None}
        )
    version = str(
        writable.browser_version or browser_binary_manager.active_version() or ""
    ).strip()
    if not version:
        raise HTTPException(
            status_code=409,
            detail="请先在系统设置中安装并启用 Fingerprint Chromium",
        )
    try:
        browser_binary_manager.resolve_fingerprint_executable(version)
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    major_text = version.split(".", 1)[0]
    major = int(major_text) if major_text.isdigit() else 0
    if major < 144 and not all(
        (
            writable.spoof_canvas,
            writable.spoof_webgl,
            writable.spoof_audio,
            writable.spoof_fonts,
            writable.spoof_client_rects,
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Chrome 144 以下不支持按模块关闭指纹改写",
        )
    return writable.model_copy(update={"browser_version": version})


def _browser_identity_profile_signature(identity: AccountBrowserIdentityPayload) -> tuple[object, ...]:
    writable = identity.writable_copy()
    return (
        writable.browser_engine,
        writable.fingerprint_seed,
        writable.browser_version,
        writable.platform,
        writable.platform_version,
        writable.brand,
        writable.language,
        writable.accept_language,
        writable.timezone,
        writable.hardware_concurrency,
        writable.spoof_canvas,
        writable.spoof_webgl,
        writable.spoof_audio,
        writable.spoof_fonts,
        writable.spoof_client_rects,
        writable.webrtc_policy,
    )


def _migration_browser_available(identity: AccountBrowserIdentityPayload) -> bool:
    try:
        if identity.browser_engine == "fingerprint_chromium":
            browser_binary_manager.resolve_fingerprint_executable(identity.browser_version)
        elif identity.browser_version:
            standard_browser_binary_manager.resolve_executable(identity.browser_version)
        elif not browser_binary_manager.system_browser().available:
            return False
        return True
    except BrowserBinaryError:
        return False


async def _account_migration_preview(
    staged: StagedAccountMigration,
) -> AccountMigrationPreviewPayload:
    migrated = staged.account
    conflicts: list[str] = []
    warnings: list[str] = []
    identity_user_id = migrated.platform_user_id or migrated.cookie_user_id
    for account in await store.list_accounts():
        existing_cookie_user_id = None
        for part in account.cookie.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name == "unb" and value.strip():
                existing_cookie_user_id = value.strip()
                break
        if identity_user_id and identity_user_id in {
            account.platform_user_id,
            existing_cookie_user_id,
        }:
            conflicts.append(f"该闲鱼账户已存在：{account.display_name}")
        if (
            migrated.browser_identity.fingerprint_seed is not None
            and migrated.browser_identity.fingerprint_seed
            == account.browser_identity.fingerprint_seed
        ):
            conflicts.append(f"指纹 Seed 已被账户“{account.display_name}”使用")

    if migrated.proxy is not None:
        for proxy in await store.list_proxies():
            if proxy.name == migrated.proxy.name:
                warnings.append(
                    f"代理名称“{migrated.proxy.name}”已存在；请关闭“导入代理”后再导入"
                )
                break
    browser_available = _migration_browser_available(migrated.browser_identity)
    if not browser_available:
        version = migrated.browser_identity.browser_version or "系统版本"
        warnings.append(f"目标平台缺少对应浏览器内核 {version}，导入后必须保持停用")
    if not migrated.cookie:
        warnings.append("迁移包没有 Cookie，导入后需要重新扫码登录")
    if not staged.profile_path:
        warnings.append("迁移包未包含浏览器 Profile，将只恢复 Cookie 和指纹配置")
    return AccountMigrationPreviewPayload(
        session_id=staged.session_id,
        expires_at=staged.expires_at,
        exported_at=migrated.exported_at,
        source_account_id=migrated.source_account_id,
        platform_user_id=migrated.platform_user_id or migrated.cookie_user_id,
        platform_display_name=migrated.platform_display_name,
        remark=migrated.remark,
        cookie_present=bool(migrated.cookie),
        browser_identity=migrated.browser_identity,
        browser_available=browser_available,
        profile_present=staged.profile_path is not None,
        profile_size_bytes=staged.profile_size_bytes,
        profile_file_count=staged.profile_file_count,
        proxy_included=migrated.proxy is not None,
        proxy_name=migrated.proxy.name if migrated.proxy else None,
        desired_enabled=migrated.desired_enabled,
        desired_chat_enabled=migrated.desired_chat_enabled,
        conflicts=list(dict.fromkeys(conflicts)),
        warnings=list(dict.fromkeys(warnings)),
        can_import=not conflicts,
    )


async def _enqueue_or_fail(task: BackgroundTaskPayload) -> None:
    try:
        result = await enqueue_background_task(store, task)
        if not result.queued:
            raise RuntimeError(result.message)
        await store.mark_background_task_queued(task.task_id)
    except Exception as exc:
        error = f"queue unavailable: {exc.__class__.__name__}: {exc}"
        await store.finish_background_task(task.task_id, status="failed", error=error)
        await store.add_audit_log(
            action="QUEUE",
            target=f"/api/tasks/{task.task_id}",
            success=False,
            status_code=503,
            error=error,
        )
        raise HTTPException(status_code=503, detail=error) from exc


async def _resolve_product_task_location(account_id: str, draft_id: str) -> dict[str, object] | None:
    draft = await store.get_product_draft(account_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="product draft not found")
    if draft.location_mode in {"region", "selected"}:
        if draft.location is None:
            raise HTTPException(status_code=422, detail="selected product location is missing")
        return draft.location.model_dump()
    if draft.location_mode == "group_random":
        return None
    try:
        locations = await list_platform_product_locations(store, account_id)
    except ProductPublishError as exc:
        raise HTTPException(status_code=503 if exc.retryable else 409, detail=str(exc)) from exc
    if not locations.items:
        raise HTTPException(status_code=409, detail="account has no usable product location")
    return locations.items[0].model_dump(exclude={"location_id", "label", "source"})


async def _ensure_publish_background_task(
    account_id: str,
    publish_task: ProductPublishTaskPayload,
) -> BackgroundTaskPayload:
    lock = publish_enqueue_locks.setdefault(publish_task.task_id, asyncio.Lock())
    async with lock:
        created = await store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=account_id,
                task_type="product.publish_task",
                dedupe_key=f"product-publish:{publish_task.task_id}",
                payload={"account_id": account_id, "task_id": publish_task.task_id},
            )
        )
        assert created is not None
        if (
            created.status == "failed"
            and publish_task.status == "pending"
            and (created.error or "").startswith("queue unavailable:")
        ):
            reset = await store.reset_background_task_for_retry(created.task_id)
            if reset is not None:
                created = reset
        if created.status == "pending" and created.queued_at is None:
            await _enqueue_or_fail(created)
            refreshed = await store.get_background_task(created.task_id)
            if refreshed is not None:
                created = refreshed
        return created


def _first_header_ip(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    if not first:
        return None
    try:
        return str(ip_address(first))
    except ValueError:
        return None


def _has_permission(user: UserPayload, request: Request) -> bool:
    if user.role == "admin":
        return True
    if (
        request.method == "POST"
        and request.url.path.startswith("/api/im/conversations/")
        and request.url.path.endswith("/read")
    ):
        return True
    if request.url.path.startswith(ADMIN_ONLY_PREFIXES):
        return False
    if user.role == "viewer":
        return request.method in {"GET", "HEAD", "OPTIONS"}
    return user.role == "operator"


def resolve_client_access(request: Request) -> ClientAccessPayload:
    remote_addr = _first_header_ip(request.client.host if request.client else None)
    trust_forwarded = remote_addr in settings.trusted_proxy_ips
    cf_connecting_ip = _first_header_ip(request.headers.get("cf-connecting-ip")) if trust_forwarded else None
    true_client_ip = _first_header_ip(request.headers.get("true-client-ip")) if trust_forwarded else None
    x_real_ip = _first_header_ip(request.headers.get("x-real-ip")) if trust_forwarded else None
    x_forwarded_for = request.headers.get("x-forwarded-for") if trust_forwarded else None
    x_forwarded_for_ip = _first_header_ip(x_forwarded_for)

    candidates = [
        ("CF-Connecting-IP", cf_connecting_ip),
        ("True-Client-IP", true_client_ip),
        ("X-Real-IP", x_real_ip),
        ("X-Forwarded-For", x_forwarded_for_ip),
        ("remote_addr", remote_addr),
    ]
    for source, ip in candidates:
        if ip:
            return ClientAccessPayload(
                ip=ip,
                source=source,
                remote_addr=remote_addr,
                cf_connecting_ip=cf_connecting_ip,
                true_client_ip=true_client_ip,
                x_real_ip=x_real_ip,
                x_forwarded_for=x_forwarded_for,
            )

    return ClientAccessPayload(
        ip=None,
        source="unknown",
        remote_addr=remote_addr,
        cf_connecting_ip=cf_connecting_ip,
        true_client_ip=true_client_ip,
        x_real_ip=x_real_ip,
        x_forwarded_for=x_forwarded_for,
    )


@app.middleware("http")
async def require_jwt(request: Request, call_next):  # type: ignore[no-untyped-def]
    user: UserPayload | None = None
    is_chatwoot_webhook = (
        request.method == "POST"
        and request.url.path == "/api/integrations/chatwoot/webhook"
    )
    if (
        request.url.path.startswith("/api")
        and request.url.path not in AUTH_EXEMPT_PATHS
        and not is_chatwoot_webhook
    ):
        authorization = request.headers.get("authorization", "")
        bearer_token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else None

        if bearer_token:
            token_payload = verify_access_token(bearer_token)
            if token_payload is not None:
                user = await store.get_user(str(token_payload["sub"]))

        if user is None or not user.enabled:
            return JSONResponse(status_code=401, content={"detail": "invalid or missing access token"})
        request.state.auth_user = user
        if not _has_permission(user, request):
            client = resolve_client_access(request)
            await store.add_audit_log(
                action=request.method,
                target=request.url.path,
                success=False,
                status_code=403,
                error="permission denied",
                actor=user.username,
                client_ip=client.ip,
            )
            return JSONResponse(status_code=403, content={"detail": "permission denied"})
    response = await call_next(request)
    is_vnc_activity_heartbeat = (
        request.method == "POST"
        and request.url.path.startswith("/api/browser-sessions/")
        and request.url.path.endswith("/activity")
    )
    if (
        request.url.path.startswith("/api")
        and request.method in {"POST", "PUT", "DELETE"}
        and not is_vnc_activity_heartbeat
    ):
        client = resolve_client_access(request)
        await store.add_audit_log(
            action=request.method,
            target=request.url.path,
            success=response.status_code < 400,
            status_code=response.status_code,
            error=None if response.status_code < 400 else str(response.status_code),
            actor=getattr(request.state, "audit_actor", None) or (user.username if user else "system"),
            client_ip=client.ip,
        )
    return response


def _account_connection_health(account) -> AccountConnectionHealthPayload:  # type: ignore[no-untyped-def]
    health = runtime_manager.connection_health(account.account_id)
    connected_at_ms = health.get("connected_at_ms")
    heartbeat_at_ms = health.get("last_heartbeat_at_ms")
    server_frame_at_ms = health.get("last_server_frame_at_ms")
    rpc_success_at_ms = health.get("last_rpc_success_at_ms")
    now_ms = int(time.time() * 1000)
    return AccountConnectionHealthPayload(
        account_id=account.account_id,
        account_name=account.display_name,
        enabled=account.enabled,
        network_mode="socks5" if account.proxy_id else "direct",
        proxy_id=account.proxy_id,
        proxy_name=account.proxy_name,
        running=bool(health.get("running")),
        online=bool(health.get("online")),
        connected_at=(
            datetime.fromtimestamp(connected_at_ms / 1000, UTC)
            if isinstance(connected_at_ms, int)
            else None
        ),
        last_heartbeat_at=(
            datetime.fromtimestamp(heartbeat_at_ms / 1000, UTC)
            if isinstance(heartbeat_at_ms, int)
            else None
        ),
        heartbeat_age_seconds=(
            max(0.0, (now_ms - heartbeat_at_ms) / 1000)
            if isinstance(heartbeat_at_ms, int)
            else None
        ),
        last_server_frame_at=(
            datetime.fromtimestamp(server_frame_at_ms / 1000, UTC)
            if isinstance(server_frame_at_ms, int)
            else None
        ),
        server_frame_age_seconds=(
            max(0.0, (now_ms - server_frame_at_ms) / 1000)
            if isinstance(server_frame_at_ms, int)
            else None
        ),
        last_rpc_success_at=(
            datetime.fromtimestamp(rpc_success_at_ms / 1000, UTC)
            if isinstance(rpc_success_at_ms, int)
            else None
        ),
        last_rpc_latency_ms=health.get("last_rpc_latency_ms"),
        last_rpc_error=health.get("last_rpc_error"),
        consecutive_rpc_failures=int(health.get("consecutive_rpc_failures") or 0),
        rpc_healthy=bool(health.get("rpc_healthy")),
        push_queue_depth=int(health.get("push_queue_depth") or 0),
        push_queue_dropped=int(health.get("push_queue_dropped") or 0),
        push_inflight=int(health.get("push_inflight") or 0),
        active_pushes=list(health.get("active_pushes") or []),
        reconnect_count=int(health.get("reconnect_count") or 0),
        last_disconnect_reason=health.get("last_disconnect_reason"),
        sync_queue_depth=int(health.get("sync_queue_depth") or 0),
        side_effect_queue_depth=int(health.get("side_effect_queue_depth") or 0),
        side_effect_queue_capacity=int(health.get("side_effect_queue_capacity") or 200),
        side_effect_queue_dropped=int(health.get("side_effect_queue_dropped") or 0),
        message_retry_pending=int(health.get("message_retry_pending") or 0),
        processing_errors_total=int(health.get("processing_errors_total") or 0),
        last_processing_error=health.get("last_processing_error"),
        last_processing_error_at=health.get("last_processing_error_at"),
    )


@app.get("/api/health", response_model=HealthPayload)
async def health() -> HealthPayload:
    return HealthPayload()


@app.get("/api/ready", response_model=HealthPayload)
async def readiness() -> HealthPayload:
    accounts = [
        account
        for account in await store.list_accounts()
        if account.enabled and account.runtime.state not in {"disabled", "deleting"}
    ]
    enabled = [account for account in accounts if account.enabled]
    connection_health = [_account_connection_health(account) for account in enabled]
    running = sum(item.running for item in connection_health)
    online = sum(item.online for item in connection_health)
    return HealthPayload(
        runtime_ok=online == len(enabled),
        enabled_accounts=len(enabled),
        running_accounts=running,
        online_accounts=online,
    )


@app.get(
    "/api/runtime-health",
    response_model=list[AccountConnectionHealthPayload],
)
async def runtime_health() -> list[AccountConnectionHealthPayload]:
    return [_account_connection_health(account) for account in await store.list_accounts()]


@app.get("/api/process-health", response_model=ProcessHealthPayload)
async def process_health() -> ProcessHealthPayload:
    return ProcessHealthPayload.model_validate(
        await event_loop_monitor.process_snapshot(await realtime_broker.health())
    )


@app.get("/api/auth/setup-status", response_model=AuthSetupStatusPayload)
async def auth_setup_status(request: Request) -> AuthSetupStatusPayload:
    return AuthSetupStatusPayload(
        initialized=await store.count_users() > 0,
        client=resolve_client_access(request),
    )


@app.get("/api/auth/client-info", response_model=ClientAccessPayload)
async def auth_client_info(request: Request) -> ClientAccessPayload:
    return resolve_client_access(request)


@app.post("/api/auth/bootstrap", response_model=AuthTokenPayload, status_code=201)
async def bootstrap_auth(request: Request, payload: AuthBootstrapPayload) -> AuthTokenPayload:
    if await store.count_users() > 0:
        raise HTTPException(status_code=409, detail="admin user already initialized")
    user = await store.create_user(
        UserCreatePayload(
            username=payload.username,
            password=payload.password,
            role="admin",
            enabled=True,
        )
    )
    client = resolve_client_access(request)
    user = await store.record_user_login(
        user.user_id,
        client_ip=client.ip,
        login_source=client.source,
    ) or user
    request.state.audit_actor = user.username
    token, expires_in = create_access_token(user_id=user.user_id, username=user.username, role=user.role)
    return AuthTokenPayload(access_token=token, expires_in=expires_in, user=user)


@app.post("/api/auth/login", response_model=AuthTokenPayload)
async def login(request: Request, payload: AuthLoginPayload) -> AuthTokenPayload:
    client = resolve_client_access(request)
    user = await store.authenticate_user(
        payload.username,
        payload.password,
        client_ip=client.ip,
        login_source=client.source,
    )
    if user is None:
        raise HTTPException(status_code=401, detail="invalid username or password")
    request.state.audit_actor = user.username
    token, expires_in = create_access_token(user_id=user.user_id, username=user.username, role=user.role)
    return AuthTokenPayload(access_token=token, expires_in=expires_in, user=user)


@app.get("/api/auth/me", response_model=UserPayload)
async def current_user(request: Request) -> UserPayload:
    return request.state.auth_user


@app.patch("/api/auth/preferences", response_model=UserPayload)
async def update_current_user_preferences(
    request: Request,
    payload: UserPreferenceUpdatePayload,
) -> UserPayload:
    user: UserPayload = request.state.auth_user
    updated = await store.update_user_preferences(user.user_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")
    request.state.audit_actor = updated.username
    return updated


@app.get("/api/quick-phrases", response_model=list[QuickPhrasePayload])
async def list_quick_phrases(request: Request) -> list[QuickPhrasePayload]:
    user: UserPayload = request.state.auth_user
    return await store.list_quick_phrases(user.user_id)


@app.post("/api/quick-phrases", response_model=QuickPhrasePayload, status_code=201)
async def create_quick_phrase(
    request: Request,
    payload: QuickPhraseCreatePayload,
) -> QuickPhrasePayload:
    user: UserPayload = request.state.auth_user
    return await store.create_quick_phrase(user.user_id, payload)


@app.put("/api/quick-phrases/{phrase_id}", response_model=QuickPhrasePayload)
async def update_quick_phrase(
    phrase_id: str,
    request: Request,
    payload: QuickPhraseUpdatePayload,
) -> QuickPhrasePayload:
    user: UserPayload = request.state.auth_user
    phrase = await store.update_quick_phrase(user.user_id, phrase_id, payload)
    if phrase is None:
        raise HTTPException(status_code=404, detail="quick phrase not found")
    return phrase


@app.delete("/api/quick-phrases/{phrase_id}", status_code=204)
async def delete_quick_phrase(phrase_id: str, request: Request) -> None:
    user: UserPayload = request.state.auth_user
    if not await store.delete_quick_phrase(user.user_id, phrase_id):
        raise HTTPException(status_code=404, detail="quick phrase not found")


@app.post("/api/quick-phrases/{phrase_id}/used", response_model=QuickPhrasePayload)
async def touch_quick_phrase(phrase_id: str, request: Request) -> QuickPhrasePayload:
    user: UserPayload = request.state.auth_user
    phrase = await store.touch_quick_phrase(user.user_id, phrase_id)
    if phrase is None:
        raise HTTPException(status_code=404, detail="quick phrase not found")
    return phrase


@app.post("/api/realtime-ticket", response_model=RealtimeTicketPayload)
async def create_realtime_ticket(request: Request) -> RealtimeTicketPayload:
    ticket = secrets.token_urlsafe(32)
    expires_at = time.monotonic() + 30
    user: UserPayload = request.state.auth_user
    async with realtime_ticket_lock:
        now = time.monotonic()
        for stale_ticket, (_, stale_expires_at) in tuple(realtime_tickets.items()):
            if stale_expires_at <= now:
                realtime_tickets.pop(stale_ticket, None)
        realtime_tickets[ticket] = (user.user_id, expires_at)
    return RealtimeTicketPayload(ticket=ticket)


@app.websocket("/api/realtime")
async def realtime_events(websocket: WebSocket, ticket: str = Query(default="")) -> None:
    await websocket.accept()
    async with realtime_ticket_lock:
        ticket_data = realtime_tickets.pop(ticket, None)
    if ticket_data is None or ticket_data[1] <= time.monotonic():
        await websocket.close(code=4401)
        return
    user = await store.get_user(ticket_data[0])
    if user is None or not user.enabled:
        await websocket.close(code=4401)
        return

    queue = await realtime_broker.subscribe()

    async def send_events() -> None:
        while True:
            event = await queue.get()
            target_user_id = event.get("user_id")
            if target_user_id is not None and target_user_id != user.user_id:
                continue
            payload = dict(event)
            payload.pop("user_id", None)
            await websocket.send_json(payload)

    async def receive_heartbeat() -> None:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"event": "pong"})

    sender = asyncio.create_task(send_events())
    receiver = asyncio.create_task(receive_heartbeat())
    try:
        await websocket.send_json({"event": "connected"})
        done, pending = await asyncio.wait(
            {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done | pending:
            try:
                await task
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        receiver.cancel()
        await realtime_broker.unsubscribe(queue)


@app.get("/api/users", response_model=list[UserPayload])
async def list_users() -> list[UserPayload]:
    return await store.list_users()


@app.post("/api/users", response_model=UserPayload, status_code=201)
async def create_user(payload: UserCreatePayload) -> UserPayload:
    try:
        return await store.create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/users/{user_id}", response_model=UserPayload)
async def update_user(user_id: str, payload: UserUpdatePayload) -> UserPayload:
    updated = await store.update_user(user_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")
    return updated


@app.get("/api/proxies", response_model=list[ProxyPayload])
async def list_proxies() -> list[ProxyPayload]:
    return [record.to_payload() for record in await store.list_proxies()]


@app.post("/api/proxies", response_model=ProxyPayload, status_code=201)
async def create_proxy(payload: ProxyCreatePayload) -> ProxyPayload:
    try:
        return (await store.create_proxy(payload)).to_payload()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/proxies/{proxy_id}", response_model=ProxyPayload)
async def update_proxy(proxy_id: str, payload: ProxyUpdatePayload) -> ProxyPayload:
    previous = await store.get_proxy(proxy_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="proxy not found")
    try:
        record = await store.update_proxy(proxy_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="proxy not found")
    if record.connection_signature() != previous.connection_signature():
        bound_accounts = [
            account
            for account in await store.list_accounts()
            if account.proxy_id == proxy_id
            and account.enabled
            and account.runtime.state not in {"stopped", "disabled"}
        ]
        if bound_accounts:
            await asyncio.gather(
                *(runtime_manager.start(account, force_restart=True) for account in bound_accounts)
            )
    return record.to_payload()


@app.delete("/api/proxies/{proxy_id}", status_code=204)
async def delete_proxy(proxy_id: str) -> None:
    try:
        deleted = await store.delete_proxy(proxy_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="proxy not found")


@app.post("/api/proxies/{proxy_id}/test", response_model=ProxyTestPayload)
async def test_proxy(proxy_id: str) -> ProxyTestPayload:
    lock = proxy_test_locks.setdefault(proxy_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail="该代理正在检测，请等待当前检测完成")
    try:
        async with lock:
            record = await store.get_proxy(proxy_id)
            if record is None:
                raise HTTPException(status_code=404, detail="proxy not found")
            tested_connection = record.connection_signature()
            result = await runtime_manager.test_proxy(record.to_config())
            updated = await store.record_proxy_test(
                proxy_id,
                ok=result.ok,
                message=result.message,
                latency_ms=result.latency_ms,
                exit_ip=result.exit_ip,
                exit_ipv4=result.exit_ipv4,
                exit_ipv6=result.exit_ipv6,
                exit_country=result.exit_country,
                exit_region=result.exit_region,
                exit_city=result.exit_city,
                exit_isp=result.exit_isp,
                exit_ipv6_country=result.exit_ipv6_country,
                exit_ipv6_continent=result.exit_ipv6_continent,
                platform_status=result.platform_status_code,
                expected_connection=tested_connection,
            )
            if updated is None or updated.connection_signature() != tested_connection:
                return ProxyTestPayload(
                    ok=False,
                    proxy_url=result.proxy_url,
                    message="检测期间代理配置已发生变化，本次结果未保存，请重新检测",
                    latency_ms=result.latency_ms,
                )
            return result
    finally:
        if proxy_test_locks.get(proxy_id) is lock and not lock.locked():
            proxy_test_locks.pop(proxy_id, None)


@app.post("/api/xianyu-login/qr", response_model=XianyuQRStatusPayload, status_code=202)
async def start_xianyu_qr_login(
    payload: XianyuQRStartPayload,
    request: Request = None,  # type: ignore[assignment]
) -> XianyuQRStatusPayload:
    user: UserPayload | None = (
        getattr(request.state, "auth_user", None) if request is not None else None
    )
    account = await store.get_account(payload.account_id) if payload.account_id else None
    if payload.account_id and account is None:
        raise HTTPException(status_code=404, detail="account not found")
    remark = account.remark if account else payload.remark
    browser_identity = (
        account.browser_identity
        if account is not None
        else _normalize_browser_identity_for_save(
            payload.browser_identity or AccountBrowserIdentityPayload(),
            apply_standard_default=True,
        )
    )

    proxy_id = payload.proxy_id if payload.proxy_id is not None else (account.proxy_id if account else None)
    if proxy_id:
        try:
            proxy_record = await store.validate_proxy_assignment(
                proxy_id,
                account_id=account.account_id if account else None,
            )
        except ProxyAssignmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            status_code = 404 if str(exc) == "proxy not found" else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc
        proxy_config = proxy_record.to_config()
    elif account:
        proxy_config = account.proxy
    else:
        proxy_config = ProxyConfigPayload()

    identity = _qr_session_key(
        account.account_id if account else None,
        payload.client_request_id,
        user.user_id if user else None,
        proxy_id,
    )
    async with qr_start_lock:
        for session_id, existing in list(qr_login_sessions.items()):
            if existing.expires_in <= 0 or existing.finalized or existing.status in {
                "error",
                "expired",
            }:
                if session_id not in qr_initialize_tasks:
                    _discard_qr_session(session_id)
                continue
            if qr_session_keys.get(session_id) == identity:
                return _qr_status_payload(existing)

        active_sessions = sum(
            1
            for existing in qr_login_sessions.values()
            if existing.expires_in > 0 and not existing.finalized
        )
        if active_sessions >= settings.qr_login_max_active_sessions:
            raise HTTPException(status_code=429, detail="扫码登录任务已满，请稍后再试")

        session = QRLoginSession(
            account_id=account.account_id if account else None,
            remark=remark,
            automation_owner_user_id=(
                account.automation_owner_user_id
                if account
                else user.user_id if user else None
            ) or (user.user_id if user else None),
            proxy_id=proxy_id,
            proxy=proxy_config,
            browser_identity=browser_identity,
        )
        session.status = "initializing"
        qr_login_sessions[session.session_id] = session
        qr_session_keys[session.session_id] = identity
        qr_finalize_locks[session.session_id] = asyncio.Lock()
        qr_poll_locks[session.session_id] = asyncio.Lock()
        qr_initialize_tasks[session.session_id] = asyncio.create_task(
            _initialize_qr_session(session),
            name=f"xianyu-qr-initialize:{session.session_id}",
        )
    return _qr_status_payload(session)


@app.delete("/api/xianyu-login/qr/{session_id}", status_code=204)
async def cancel_xianyu_qr_login(session_id: str) -> None:
    session = qr_login_sessions.get(session_id)
    if session is None:
        return
    if session.status == "browser_verification":
        with suppress(IMVerificationError):
            await im_verification_manager.cancel_qr_login(session_id)
    session.fail("扫码登录已取消")
    if session_id in qr_initialize_tasks:
        qr_login_sessions.pop(session_id, None)
        qr_finalize_locks.pop(session_id, None)
        qr_poll_locks.pop(session_id, None)
        qr_session_keys.pop(session_id, None)
        return
    _discard_qr_session(session_id)


@app.post("/api/xianyu-login/qr/{session_id}/poll", response_model=XianyuQRStatusPayload)
async def poll_xianyu_qr_login(session_id: str) -> XianyuQRStatusPayload:
    session = qr_login_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="QR login session not found or expired")
    initializing = qr_initialize_tasks.get(session_id)
    if initializing is not None and not initializing.done():
        return _qr_status_payload(session)

    poll_lock = qr_poll_locks.setdefault(session_id, asyncio.Lock())
    if poll_lock.locked():
        return _qr_status_payload(session)
    async with poll_lock:
        try:
            status = await run_qr_blocking(session.poll)
        except Exception as exc:
            session.status = "error"
            session.error = str(exc)
            status = "error"

        if status == "finalizing" and not session.finalized:
            lock = qr_finalize_locks[session_id]
            async with lock:
                if not session.finalized:
                    try:
                        cookie = await run_qr_blocking(session.finalize_credentials)
                        await _persist_qr_login_credentials(session, cookie)
                    except QRLoginError as exc:
                        session.fail(str(exc))
                    except Exception as exc:
                        session.fail(f"failed to finalize Xianyu login: {exc.__class__.__name__}")

    status = session.status

    return _qr_status_payload(session)


@app.post(
    "/api/xianyu-login/qr/{session_id}/browser-verification/start",
    response_model=XianyuQRBrowserVerificationPayload,
)
async def start_xianyu_qr_browser_verification(
    session_id: str,
    request: Request,
) -> XianyuQRBrowserVerificationPayload:
    session = qr_login_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="扫码登录会话不存在或已过期")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="扫码登录已经完成")
    account = await store.get_account(session.account_id) if session.account_id else None
    user: UserPayload = request.state.auth_user
    try:
        return await im_verification_manager.start_qr_login(session, account, user.user_id)
    except IMVerificationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IMVerificationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/api/xianyu-login/qr/{session_id}/browser-verification/complete",
    response_model=XianyuQRStatusPayload,
)
async def complete_xianyu_qr_browser_verification(
    session_id: str,
) -> XianyuQRStatusPayload:
    session = qr_login_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="扫码登录会话不存在或已过期")
    account = await store.get_account(session.account_id) if session.account_id else None
    try:
        cookie = await im_verification_manager.prepare_qr_login_completion(session, account)
        await _persist_qr_login_credentials(session, cookie)
        await im_verification_manager.finish_qr_login(session_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QRLoginError as exc:
        with suppress(IMVerificationError):
            await im_verification_manager.restore_qr_login_ready(session_id, str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        detail = f"登录凭据保存失败：{exc}"
        with suppress(IMVerificationError):
            await im_verification_manager.restore_qr_login_ready(session_id, detail)
        raise HTTPException(status_code=409, detail=detail) from exc
    return _qr_status_payload(session)


@app.post(
    "/api/xianyu-login/qr/{session_id}/browser-verification/cancel",
    response_model=XianyuQRBrowserVerificationPayload,
)
async def cancel_xianyu_qr_browser_verification(
    session_id: str,
) -> XianyuQRBrowserVerificationPayload:
    session = qr_login_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="扫码登录会话不存在或已过期")
    session.fail("远程登录验证已取消")
    return await im_verification_manager.cancel_qr_login(session_id)


@app.post(
    "/api/xianyu-login/qr/{session_id}/browser-verification/vnc-ticket",
    response_model=IMVerificationTicketPayload,
)
async def create_xianyu_qr_browser_verification_vnc_ticket(
    session_id: str,
    request: Request,
) -> IMVerificationTicketPayload:
    if session_id not in qr_login_sessions:
        raise HTTPException(status_code=404, detail="扫码登录会话不存在或已过期")
    user: UserPayload = request.state.auth_user
    try:
        ticket, expires_in = await im_verification_manager.issue_vnc_ticket(
            f"qr:{session_id}",
            user.user_id,
        )
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return IMVerificationTicketPayload(ticket=ticket, expires_in=expires_in)


@app.post("/api/account-migrations/export/{account_id}")
async def export_account_migration(
    account_id: str,
    password: str = Form(min_length=8, max_length=256),
) -> FileResponse:
    async with account_migration_lock:
        account = await store.get_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        previous_state = account.runtime.state if account.runtime else "stopped"
        restore_runtime = previous_state in {"connecting", "online", "reconnecting"}
        package = None
        try:
            profile_key = account_migration_service.profile_storage.account_profile_key(
                account_id
            )
            await im_verification_manager.stop_browser_profile(profile_key)
            if restore_runtime:
                await runtime_manager.stop(account_id)
            latest = await store.get_account(account_id)
            if latest is None:
                raise HTTPException(status_code=404, detail="account not found")
            package = await run_external_blocking(
                account_migration_service.create_package,
                latest,
                password,
            )
        except AccountMigrationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            if restore_runtime:
                latest = await store.get_account(account_id)
                if latest is not None:
                    try:
                        await runtime_manager.start(latest, force_restart=True)
                    except Exception:
                        logger.exception(
                            "Failed to restore account runtime after migration export account=%s",
                            account_id,
                        )
        if package is None:
            raise HTTPException(status_code=500, detail="账户迁移包生成失败")
        return FileResponse(
            package.path,
            media_type="application/zip",
            filename=package.filename,
            headers={
                "Cache-Control": "no-store, private",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
            },
            background=BackgroundTask(account_migration_service.remove_export, package),
        )


@app.post(
    "/api/account-migrations/inspect",
    response_model=AccountMigrationPreviewPayload,
)
async def inspect_account_migration(
    archive: UploadFile = File(...),
    password: str = Form(min_length=8, max_length=256),
) -> AccountMigrationPreviewPayload:
    try:
        staged = await run_external_blocking(
            account_migration_service.inspect_package,
            archive.file,
            archive.filename or "account.xianyu.zip",
            password,
        )
    except AccountMigrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await archive.close()
    return await _account_migration_preview(staged)


@app.post(
    "/api/account-migrations/import",
    response_model=AccountPayload,
    status_code=201,
)
async def import_account_migration(
    payload: AccountMigrationImportPayload,
) -> AccountPayload:
    async with account_migration_lock:
        try:
            staged = account_migration_service.get_session(payload.session_id)
        except AccountMigrationError as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc
        preview = await _account_migration_preview(staged)
        if not preview.can_import:
            raise HTTPException(status_code=409, detail="；".join(preview.conflicts))
        migrated = staged.account
        if payload.enable_after_import and not migrated.cookie:
            raise HTTPException(status_code=409, detail="迁移包没有 Cookie，不能直接启用账户")
        if payload.enable_after_import and not preview.browser_available:
            raise HTTPException(
                status_code=409,
                detail="目标平台缺少迁移账户使用的浏览器内核，请导入后安装内核再启用",
            )
        proxy_payload = None
        if payload.import_proxy and migrated.proxy is not None:
            if any(
                proxy.name == migrated.proxy.name for proxy in await store.list_proxies()
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"代理名称“{migrated.proxy.name}”已经存在，请关闭导入代理后重试",
                )
            proxy_payload = ProxyCreatePayload(
                name=migrated.proxy.name,
                enabled=True,
                scheme=migrated.proxy.scheme,
                host=migrated.proxy.host,
                port=migrated.proxy.port,
                username=migrated.proxy.username,
                password=migrated.proxy.password,
            )
        create_payload = AccountCreatePayload(
            remark=migrated.remark,
            cookie=migrated.cookie,
            enabled=payload.enable_after_import,
            conversation_visible=migrated.conversation_visible,
            chat_enabled=(
                payload.enable_after_import and payload.enable_chatwoot_after_import
            ),
            order_management_visible=migrated.order_management_visible,
            product_management_visible=migrated.product_management_visible,
            browser_identity=migrated.browser_identity,
        )
        created = None
        imported_proxy_id = None
        try:
            created = await store.import_migrated_account(
                create_payload,
                platform_user_id=migrated.platform_user_id or migrated.cookie_user_id,
                platform_display_name=migrated.platform_display_name,
                platform_avatar_url=migrated.platform_avatar_url,
                proxy=proxy_payload,
            )
            imported_proxy_id = created.proxy_id
            await run_browser_blocking(
                account_migration_service.install_profile,
                staged,
                created,
            )
        except (AccountMigrationError, ProxyAssignmentConflict, ValueError) as exc:
            if created is not None:
                await store.delete_account(created.account_id)
                if imported_proxy_id:
                    with suppress(ValueError):
                        await store.delete_proxy(imported_proxy_id)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception:
            if created is not None:
                await store.delete_account(created.account_id)
                if imported_proxy_id:
                    with suppress(ValueError):
                        await store.delete_proxy(imported_proxy_id)
            raise

        account_migration_service.complete_session(payload.session_id)
        latest = await store.get_account(created.account_id)
        if latest is None:
            raise HTTPException(status_code=500, detail="导入后账户读取失败")
        result = latest.to_payload()
        if payload.enable_after_import:
            result = await runtime_manager.start(latest, force_restart=True)
        await realtime_broker.publish(
            {
                "event": "account_upsert",
                "account_id": created.account_id,
                "data": result.model_dump(mode="json"),
            }
        )
        if payload.enable_chatwoot_after_import:
            await enqueue_account_metadata_sync(
                store,
                account_id=created.account_id,
                reason="account-imported",
            )
        return result


@app.get("/api/accounts", response_model=list[AccountPayload])
async def list_accounts() -> list[AccountPayload]:
    records = await store.list_accounts()
    return [record.to_payload() for record in records]


@app.put("/api/accounts/order", response_model=list[AccountPayload])
async def reorder_accounts(payload: AccountReorderPayload) -> list[AccountPayload]:
    try:
        records = await store.reorder_accounts(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = [record.to_payload() for record in records]
    await realtime_broker.publish(
        {
            "event": "accounts_reordered",
            "account_ids": [record.account_id for record in records],
        }
    )
    return result


@app.get(
    "/api/settings/browser-runtime",
    response_model=BrowserRuntimeSettingPayload,
)
async def get_browser_runtime_setting() -> BrowserRuntimeSettingPayload:
    return await run_browser_blocking(
        browser_runtime_payload,
        active_vnc_account_id=im_verification_manager.active_visual_account_id,
        active_vnc_account_ids=im_verification_manager.active_visual_account_ids,
        max_vnc_session_count=settings.account_browser_max_sessions,
        vnc_idle_timeout_seconds=settings.account_browser_idle_seconds,
        vnc_max_session_seconds=settings.account_browser_max_session_seconds,
    )


@app.post(
    "/api/settings/browser-runtime/standard/upload",
    response_model=BrowserBinaryPayload,
)
async def upload_standard_browser(
    file: UploadFile = File(...),
) -> BrowserBinaryPayload:
    try:
        installed = await run_browser_blocking(
            standard_browser_binary_manager.install_upload,
            file.file,
            file.filename or "chrome-linux64.zip",
        )
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
    return installed.to_payload()


@app.post(
    "/api/settings/browser-runtime/standard/download",
    response_model=BrowserBinaryPayload,
)
async def download_standard_browser() -> BrowserBinaryPayload:
    try:
        installed = await run_browser_blocking(
            standard_browser_binary_manager.download_latest
        )
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return installed.to_payload()


@app.put(
    "/api/settings/browser-runtime/standard/active",
    response_model=BrowserRuntimeSettingPayload,
)
async def activate_standard_browser(
    payload: StandardBrowserActivatePayload,
) -> BrowserRuntimeSettingPayload:
    if im_verification_manager.has_active_visual_sessions:
        raise HTTPException(status_code=409, detail="请先停止全部 VNC 浏览器环境")
    try:
        if payload.version is None:
            await run_browser_blocking(standard_browser_binary_manager.clear_active)
        else:
            await run_browser_blocking(
                standard_browser_binary_manager.activate,
                payload.version,
            )
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await run_browser_blocking(
        browser_runtime_payload,
        active_vnc_account_id=im_verification_manager.active_visual_account_id,
        active_vnc_account_ids=im_verification_manager.active_visual_account_ids,
        max_vnc_session_count=settings.account_browser_max_sessions,
        vnc_idle_timeout_seconds=settings.account_browser_idle_seconds,
        vnc_max_session_seconds=settings.account_browser_max_session_seconds,
    )


@app.post(
    "/api/settings/browser-runtime/fingerprint/upload",
    response_model=BrowserBinaryPayload,
)
async def upload_fingerprint_browser(
    file: UploadFile = File(...),
) -> BrowserBinaryPayload:
    try:
        installed = await run_browser_blocking(
            browser_binary_manager.install_upload,
            file.file,
            file.filename or "fingerprint-chromium.tar.xz",
        )
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
    return installed.to_payload()


@app.post(
    "/api/settings/browser-runtime/fingerprint/download",
    response_model=BrowserBinaryPayload,
)
async def download_fingerprint_browser() -> BrowserBinaryPayload:
    try:
        installed = await run_browser_blocking(browser_binary_manager.download_latest)
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return installed.to_payload()


@app.put(
    "/api/settings/browser-runtime/fingerprint/active",
    response_model=BrowserBinaryPayload,
)
async def activate_fingerprint_browser(
    payload: BrowserBinaryActivatePayload,
) -> BrowserBinaryPayload:
    if im_verification_manager.has_active_visual_sessions:
        raise HTTPException(status_code=409, detail="请先停止全部 VNC 浏览器环境")
    try:
        installed = await run_browser_blocking(
            browser_binary_manager.activate,
            payload.version,
        )
    except BrowserBinaryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return installed.to_payload()


@app.post("/api/accounts", response_model=AccountPayload, status_code=201)
async def create_account(
    payload: AccountCreatePayload,
    request: Request = None,  # type: ignore[assignment]
) -> AccountPayload:
    user: UserPayload | None = (
        getattr(request.state, "auth_user", None) if request is not None else None
    )
    payload = payload.model_copy(
        update={
            "browser_identity": _normalize_browser_identity_for_save(
                payload.browser_identity,
                apply_standard_default=True,
            )
        }
    )
    try:
        record = await store.create_account(
            payload, automation_owner_user_id=user.user_id if user else None
        )
    except ProxyAssignmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = record.to_payload()
    await realtime_broker.publish(
        {"event": "account_upsert", "account_id": record.account_id, "data": result.model_dump(mode="json")}
    )
    return result


@app.get("/api/accounts/{account_id}", response_model=AccountPayload)
async def get_account(account_id: str) -> AccountPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return record.to_payload()


@app.post(
    "/api/accounts/{account_id}/cookie/reveal",
    response_model=AccountCookiePayload,
)
async def reveal_account_cookie(
    account_id: str,
    response: Response,
) -> AccountCookiePayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return AccountCookiePayload(
        account_id=record.account_id,
        cookie=record.cookie,
        cookie_updated_at=record.cookie_updated_at,
    )


@app.get(
    "/api/accounts/{account_id}/browser-session",
    response_model=AccountBrowserSessionPayload,
)
async def get_account_browser_session(
    account_id: str,
) -> AccountBrowserSessionPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    payload = await im_verification_manager.account_browser_status(account_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="平台账户浏览器会话不存在")
    return payload


@app.get(
    "/api/browser-sessions",
    response_model=list[AccountBrowserSessionPayload],
)
async def list_active_account_browser_sessions() -> list[AccountBrowserSessionPayload]:
    return await im_verification_manager.list_active_account_browsers()


@app.get(
    "/api/browser-profiles",
    response_model=list[BrowserProfilePayload],
)
async def list_browser_profiles() -> list[BrowserProfilePayload]:
    return await im_verification_manager.list_browser_profiles()


@app.post(
    "/api/browser-profiles/{profile_key}/stop",
    response_model=BrowserProfileActionPayload,
)
async def stop_browser_profile(profile_key: str) -> BrowserProfileActionPayload:
    try:
        stopped = await im_verification_manager.stop_browser_profile(profile_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"浏览器目录停止失败：{exc}") from exc
    return BrowserProfileActionPayload(
        profile_key=profile_key,
        stopped=stopped,
        message="浏览器会话已停止" if stopped else "该目录没有运行中的浏览器",
    )


@app.delete(
    "/api/browser-profiles/{profile_key}",
    response_model=BrowserProfileActionPayload,
)
async def clear_browser_profile(profile_key: str) -> BrowserProfileActionPayload:
    try:
        deleted = await im_verification_manager.clear_browser_profile(profile_key)
    except IMVerificationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"浏览器目录清理失败：{exc}") from exc
    return BrowserProfileActionPayload(
        profile_key=profile_key,
        deleted=deleted,
        message="浏览器数据目录已清理" if deleted else "浏览器数据目录不存在",
    )


@app.post(
    "/api/accounts/{account_id}/browser-session",
    response_model=AccountBrowserSessionPayload,
)
async def start_account_browser_session(
    account_id: str,
    request: Request,
) -> AccountBrowserSessionPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    user: UserPayload = request.state.auth_user
    try:
        result = await im_verification_manager.start_account_browser(account, user.user_id)
    except IMVerificationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IMVerificationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result.fingerprint_snapshot is not None:
        latest = await store.get_account(account_id)
        if latest is not None:
            account_payload = latest.to_payload()
            await realtime_broker.publish(
                {
                    "event": "account_upsert",
                    "account_id": account_id,
                    "data": account_payload.model_dump(mode="json"),
                }
            )
    return result


@app.delete(
    "/api/accounts/{account_id}/browser-profile",
    response_model=BrowserProfileCleanupPayload,
)
async def clear_account_browser_profile(
    account_id: str,
) -> BrowserProfileCleanupPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        deleted = await im_verification_manager.clear_account_browser_profile(account_id)
    except IMVerificationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"浏览器数据清理失败：{exc}") from exc
    return BrowserProfileCleanupPayload(
        account_id=account_id,
        deleted=deleted,
        message="浏览器数据已清理" if deleted else "浏览器数据目录不存在，无需清理",
    )


@app.put("/api/accounts/{account_id}", response_model=AccountPayload)
async def update_account(account_id: str, payload: AccountUpdatePayload) -> AccountPayload:
    previous = await store.get_account(account_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="account not found")
    if "browser_identity" in payload.model_fields_set and payload.browser_identity is not None:
        payload = payload.model_copy(
            update={
                "browser_identity": _normalize_browser_identity_for_save(
                    payload.browser_identity
                )
            }
        )
    try:
        record = await store.update_account(account_id, payload)
    except ProxyAssignmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    proxy_changed = previous.proxy_id != record.proxy_id or previous.proxy != record.proxy
    cookie_changed = previous.cookie != record.cookie
    identity_changed = _browser_identity_profile_signature(
        previous.browser_identity
    ) != _browser_identity_profile_signature(record.browser_identity)
    if identity_changed:
        await runtime_manager.stop(account_id)
        await im_verification_manager.prepare_account_identity_change(account_id)
        try:
            await im_verification_manager.clear_account_browser_profile(account_id)
        except (IMVerificationBusyError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=409,
                detail=f"浏览器身份已保存，但旧环境清理失败：{exc}",
            ) from exc
    if not record.enabled:
        await runtime_manager.stop(account_id)
        await store.set_runtime_state(account_id, "disabled", "账户已禁用")
    elif not previous.enabled:
        await runtime_manager.start(record, force_restart=True)
    elif proxy_changed or identity_changed:
        await runtime_manager.start(record, force_restart=True)
    elif cookie_changed:
        if record.cookie:
            replaced = await runtime_manager.replace_cookie(account_id, record.cookie)
            if not replaced:
                await runtime_manager.start(record, force_restart=True)
        else:
            await runtime_manager.start(record, force_restart=True)
    latest = await store.get_account(account_id)
    result = (latest or record).to_payload()
    await realtime_broker.publish(
        {"event": "account_upsert", "account_id": account_id, "data": result.model_dump(mode="json")}
    )
    await enqueue_account_metadata_sync(
        store,
        account_id=account_id,
        reason="account-updated",
    )
    return result


@app.put(
    "/api/accounts/{account_id}/workspace-visibility",
    response_model=AccountPayload,
)
async def update_account_workspace_visibility(
    account_id: str,
    payload: AccountWorkspaceVisibilityUpdatePayload,
) -> AccountPayload:
    record = await store.update_account_workspace_visibility(account_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    result = record.to_payload()
    await realtime_broker.publish(
        {
            "event": "account_upsert",
            "account_id": account_id,
            "data": result.model_dump(mode="json"),
        }
    )
    if payload.chat_enabled is True and record.runtime is not None:
        await enqueue_account_status_sync(
            store,
            account_id=account_id,
            state=record.runtime.state,
            message=record.runtime.message,
        )
    if payload.chat_enabled is True:
        await enqueue_account_metadata_sync(
            store,
            account_id=account_id,
            reason="chat-enabled",
        )
    return result


@app.delete(
    "/api/accounts/{account_id}",
    response_model=BackgroundTaskPayload,
    status_code=202,
)
async def delete_account(account_id: str) -> BackgroundTaskPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    stopped = await runtime_manager.prepare_delete(account_id, timeout=5)
    if not stopped:
        await store.set_runtime_state(
            account_id,
            "stopped",
            "删除前停止连接超时，请重试删除",
        )
        raise HTTPException(status_code=409, detail="账户连接停止超时，请重试删除")

    await im_verification_manager.prepare_account_deletion(account_id)

    await store.set_runtime_state(account_id, "deleting", "账户数据正在后台删除")
    latest = await store.get_account(account_id)
    if latest is not None:
        await realtime_broker.publish(
            {
                "event": "account_upsert",
                "account_id": account_id,
                "data": latest.to_payload().model_dump(mode="json"),
            }
        )

    task = await store.create_background_task(
        BackgroundTaskCreatePayload(
            account_id=account_id,
            task_type="account.delete",
            dedupe_key=f"account-delete:{account_id}",
            payload={"account_id": account_id},
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="account not found")
    if task.status == "failed":
        reset = await store.reset_background_task_for_retry(task.task_id)
        if reset is not None:
            task = reset
    if task.status == "pending" and task.queued_at is None:
        try:
            await _enqueue_or_fail(task)
        except HTTPException:
            await store.set_runtime_state(account_id, "stopped", "删除任务入队失败")
            raise
    return await store.get_background_task(task.task_id) or task


@app.post("/api/internal/accounts/{account_id}/deletion-complete")
async def complete_account_deletion(account_id: str, task_id: str = Query(...)) -> dict[str, object]:
    if await store.get_account(account_id) is not None:
        raise HTTPException(status_code=409, detail="account deletion is not complete")
    await runtime_manager.forget_account(account_id)
    await im_verification_manager.forget_account_browser(account_id)
    await realtime_broker.publish(
        {"event": "account_delete", "account_id": account_id, "task_id": task_id}
    )
    return {"ok": True, "account_id": account_id, "task_id": task_id}


@app.post("/api/accounts/start-all", response_model=list[AccountPayload])
async def start_all_accounts() -> list[AccountPayload]:
    records = await store.list_accounts()
    return await asyncio.gather(*(runtime_manager.start(record) for record in records if record.enabled))


@app.post("/api/accounts/stop-all", response_model=list[RuntimeStatusPayload])
async def stop_all_accounts() -> list[RuntimeStatusPayload]:
    records = await store.list_accounts()
    await asyncio.gather(*(runtime_manager.stop(record.account_id) for record in records))
    updated = await store.list_accounts()
    return [record.runtime.to_payload() for record in updated if record.runtime is not None]


@app.post("/api/accounts/{account_id}/start", response_model=AccountPayload)
async def start_account(account_id: str) -> AccountPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not record.enabled:
        raise HTTPException(status_code=409, detail="账户已禁用，请在编辑账户中启用")
    if record.runtime.state == "risk_blocked":
        raise HTTPException(status_code=409, detail="账户需要完成安全验证，不能直接恢复连接")
    if record.runtime.state == "auth_expired":
        raise HTTPException(status_code=409, detail="闲鱼登录已过期，请重新扫码登录")
    if record.runtime.state == "proxy_failed":
        raise HTTPException(status_code=409, detail="账户代理异常，请先处理代理配置")
    return await runtime_manager.start(record)


@app.post("/api/accounts/{account_id}/stop", response_model=RuntimeStatusPayload)
async def stop_account(account_id: str) -> RuntimeStatusPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    await runtime_manager.stop(account_id)
    updated = await store.get_account(account_id)
    assert updated is not None and updated.runtime is not None
    return updated.runtime.to_payload()


@app.get(
    "/api/accounts/{account_id}/cookie-renewal",
    response_model=CookieRenewalStatusPayload,
)
async def get_cookie_renewal(account_id: str) -> CookieRenewalStatusPayload:
    status = await store.get_cookie_renewal_status(account_id)
    if status is None:
        raise HTTPException(status_code=404, detail="account not found")
    return status


@app.post(
    "/api/accounts/{account_id}/cookie-renewal",
    response_model=CookieRenewalStatusPayload,
    status_code=202,
)
async def renew_account_cookie(account_id: str) -> CookieRenewalStatusPayload:
    try:
        status = await cookie_renewal_manager.trigger(account_id, trigger="manual")
    except CookieRenewalCooldownError as exc:
        minutes, seconds = divmod(exc.remaining_seconds, 60)
        wait_text = f"{minutes} 分 {seconds} 秒" if minutes else f"{seconds} 秒"
        raise HTTPException(
            status_code=429,
            detail=f"近期已续期成功，无需重复执行；请在 {wait_text} 后再试",
            headers={"Retry-After": str(exc.remaining_seconds)},
        ) from exc
    if status is None:
        raise HTTPException(status_code=404, detail="account not found")
    return status


@app.post("/api/accounts/{account_id}/test-proxy", response_model=ProxyTestPayload)
async def test_account_proxy(account_id: str) -> ProxyTestPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await runtime_manager.test_proxy(record.proxy)


@app.get("/api/accounts/{account_id}/runtime", response_model=RuntimeStatusPayload)
async def get_account_runtime(account_id: str) -> RuntimeStatusPayload:
    record = await store.get_account(account_id)
    if record is None or record.runtime is None:
        raise HTTPException(status_code=404, detail="account not found")
    return record.runtime.to_payload()


@app.get(
    "/api/accounts/{account_id}/im-verification",
    response_model=IMVerificationPayload,
)
async def get_account_im_verification(account_id: str) -> IMVerificationPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    verification = await im_verification_manager.status_for_account(account_id)
    if verification is None and account.runtime.state == "risk_blocked":
        await store.record_im_verification(
            account_id,
            "INTERACTIVE_VERIFICATION_REQUIRED",
            None,
        )
        verification = await im_verification_manager.status_for_account(account_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="该账户当前没有安全验证任务")
    return verification


@app.post(
    "/api/accounts/{account_id}/im-verification/start",
    response_model=IMVerificationPayload,
)
async def start_account_im_verification(
    account_id: str,
    request: Request,
) -> IMVerificationPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if not account.enabled:
        raise HTTPException(status_code=409, detail="账户已禁用，请先在编辑账户中启用")
    if account.runtime.state == "auth_expired":
        raise HTTPException(status_code=409, detail="闲鱼登录已过期，请先重新扫码登录")
    if account.runtime.state != "risk_blocked":
        raise HTTPException(status_code=409, detail="账户当前没有需要处理的 IM 安全验证")
    verification = await store.get_latest_im_verification(account_id)
    if verification is None or verification.status in {
        "completed",
        "failed",
        "expired",
        "cancelled",
    }:
        verification = await store.record_im_verification(
            account_id,
            verification.reason_code
            if verification is not None
            else "INTERACTIVE_VERIFICATION_REQUIRED",
            None,
        )
    if verification is None:
        raise HTTPException(status_code=409, detail="无法创建安全验证任务")
    user: UserPayload = request.state.auth_user
    try:
        return await im_verification_manager.start(account, verification, user.user_id)
    except IMVerificationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IMVerificationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/api/im-verifications/{verification_id}/complete",
    response_model=IMVerificationPayload,
)
async def complete_im_verification(verification_id: str) -> IMVerificationPayload:
    try:
        return await im_verification_manager.complete(verification_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/im-verifications/{verification_id}/cancel",
    response_model=IMVerificationPayload,
)
async def cancel_im_verification(verification_id: str) -> IMVerificationPayload:
    try:
        return await im_verification_manager.cancel(verification_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/im-verifications/{verification_id}/vnc-ticket",
    response_model=IMVerificationTicketPayload,
)
async def create_im_verification_vnc_ticket(
    verification_id: str,
    request: Request,
) -> IMVerificationTicketPayload:
    user: UserPayload = request.state.auth_user
    try:
        ticket, expires_in = await im_verification_manager.issue_vnc_ticket(
            verification_id,
            user.user_id,
        )
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return IMVerificationTicketPayload(ticket=ticket, expires_in=expires_in)


@app.post(
    "/api/browser-sessions/{session_id}/vnc-ticket",
    response_model=IMVerificationTicketPayload,
)
async def create_account_browser_vnc_ticket(
    session_id: str,
    request: Request,
) -> IMVerificationTicketPayload:
    user: UserPayload = request.state.auth_user
    try:
        ticket, expires_in = await im_verification_manager.issue_account_browser_vnc_ticket(
            session_id,
            user.user_id,
        )
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return IMVerificationTicketPayload(ticket=ticket, expires_in=expires_in)


@app.post(
    "/api/browser-sessions/{session_id}/fingerprint-detect",
    response_model=AccountBrowserSessionPayload,
)
async def detect_account_browser_fingerprint(
    session_id: str,
) -> AccountBrowserSessionPayload:
    try:
        result = await im_verification_manager.detect_account_browser_fingerprint(session_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result.fingerprint_snapshot is not None:
        latest = await store.get_account(result.account_id)
        if latest is not None:
            account_payload = latest.to_payload()
            await realtime_broker.publish(
                {
                    "event": "account_upsert",
                    "account_id": result.account_id,
                    "data": account_payload.model_dump(mode="json"),
                }
            )
    return result


@app.post(
    "/api/browser-sessions/{session_id}/activity",
    response_model=AccountBrowserSessionPayload,
)
async def touch_account_browser_session(
    session_id: str,
) -> AccountBrowserSessionPayload:
    try:
        return await im_verification_manager.touch_account_browser_session(session_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/browser-sessions/{session_id}/paste-text",
    response_model=AccountBrowserSessionPayload,
)
async def paste_account_browser_text(
    session_id: str,
    payload: AccountBrowserTextPastePayload,
) -> AccountBrowserSessionPayload:
    try:
        return await im_verification_manager.paste_account_browser_text(
            session_id,
            payload.text,
        )
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/browser-sessions/{session_id}/close",
    response_model=AccountBrowserSessionPayload,
)
async def close_account_browser_session(
    session_id: str,
) -> AccountBrowserSessionPayload:
    try:
        return await im_verification_manager.close_account_browser(session_id)
    except IMVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.websocket("/api/im-verifications/vnc/{ticket}")
async def im_verification_vnc(websocket: WebSocket, ticket: str) -> None:
    requested_protocols = {
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    }
    await websocket.accept(subprotocol="binary" if "binary" in requested_protocols else None)
    vnc_port = await im_verification_manager.consume_vnc_ticket(ticket)
    if vnc_port is None:
        await websocket.close(code=4401)
        return
    try:
        reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            vnc_port,
        )
    except OSError:
        await websocket.close(code=1011)
        return

    async def websocket_to_vnc() -> None:
        while True:
            event = await websocket.receive()
            if event["type"] == "websocket.disconnect":
                return
            payload = event.get("bytes")
            if payload is None and event.get("text") is not None:
                payload = event["text"].encode("latin-1")
            if payload:
                writer.write(payload)
                await writer.drain()

    async def vnc_to_websocket() -> None:
        while payload := await reader.read(64 * 1024):
            await websocket.send_bytes(payload)

    tasks = {
        asyncio.create_task(websocket_to_vnc()),
        asyncio.create_task(vnc_to_websocket()),
    }
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*done, *pending, return_exceptions=True)
    writer.close()
    with suppress(Exception):
        await writer.wait_closed()
    with suppress(Exception):
        await websocket.close()


@app.get("/api/accounts/{account_id}/runtime-events", response_model=list[RuntimeEventPayload])
async def list_account_runtime_events(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[RuntimeEventPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_runtime_events(account_id=account_id, limit=limit)


@app.get("/api/runtime-events", response_model=list[RuntimeEventPayload])
async def list_runtime_events(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[RuntimeEventPayload]:
    return await store.list_runtime_events(limit=limit)


@app.get("/api/tasks", response_model=list[BackgroundTaskPayload])
async def list_background_tasks(
    account_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BackgroundTaskPayload]:
    if account_id and await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_background_tasks(account_id=account_id, limit=limit)


@app.post("/api/tasks", response_model=BackgroundTaskPayload, status_code=201)
async def create_background_task(payload: BackgroundTaskCreatePayload) -> BackgroundTaskPayload:
    created = await store.create_background_task(payload)
    if created is None:
        raise HTTPException(status_code=404, detail="account not found")
    await _enqueue_or_fail(created)
    return created


@app.get("/api/audit-logs", response_model=list[AuditLogPayload])
async def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AuditLogPayload]:
    return await store.list_audit_logs(limit=limit)


@app.put(
    "/api/accounts/{account_id}/auto-reply-enabled",
    response_model=AccountAutoReplyStatusPayload,
)
async def update_account_auto_reply_enabled(
    account_id: str,
    payload: AccountAutoReplyUpdatePayload,
) -> AccountAutoReplyStatusPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    updated = await store.update_account_auto_reply(account_id, payload)
    assert updated is not None
    record = await store.get_account(account_id)
    if record is not None:
        await realtime_broker.publish(
            {
                "event": "account_upsert",
                "account_id": account_id,
                "data": record.to_payload().model_dump(mode="json"),
            }
        )
    return updated


@app.get("/api/settings/ai-provider", response_model=AIProviderSettingPayload)
async def get_ai_provider_setting() -> AIProviderSettingPayload:
    return await store.get_ai_provider_setting()


@app.put("/api/settings/ai-provider", response_model=AIProviderSettingPayload)
async def update_ai_provider_setting(
    payload: AIProviderSettingUpdatePayload,
) -> AIProviderSettingPayload:
    return await store.update_ai_provider_setting(payload)


@app.get(
    "/api/web-notification",
    response_model=WebNotificationConfigPayload,
)
async def get_web_notification_config() -> WebNotificationConfigPayload:
    """Expose safe playback settings to every authenticated web client."""

    return await web_notification_repository.get_config()


@app.get("/api/web-notification/sound")
async def get_web_notification_sound() -> FileResponse:
    record = await web_notification_repository.get_sound_record()
    if record is None:
        raise HTTPException(status_code=404, detail="custom notification sound not found")
    sound_key, mime_type, filename = record
    try:
        path = web_notification_sound_storage.path(sound_key)
    except WebNotificationSoundError as exc:
        raise HTTPException(status_code=404, detail="custom notification sound not found") from exc
    if not path.is_file():
        raise HTTPException(status_code=410, detail="custom notification sound file is missing")
    return FileResponse(
        path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400, immutable"},
    )


@app.put(
    "/api/settings/message-services/web-notification",
    response_model=WebNotificationConfigPayload,
)
async def update_web_notification_config(
    payload: WebNotificationConfigUpdatePayload,
) -> WebNotificationConfigPayload:
    return await web_notification_repository.update_config(payload)


@app.post(
    "/api/settings/message-services/web-notification/sound",
    response_model=WebNotificationConfigPayload,
)
async def upload_web_notification_sound(
    sound: UploadFile = File(...),
) -> WebNotificationConfigPayload:
    try:
        raw = await sound.read(MAX_WEB_NOTIFICATION_SOUND_BYTES + 1)
    finally:
        await sound.close()
    if len(raw) > MAX_WEB_NOTIFICATION_SOUND_BYTES:
        raise HTTPException(status_code=413, detail="铃声文件不能超过 5 MB")
    try:
        prepared = await run_media_blocking(
            web_notification_sound_storage.save,
            raw,
            sound.filename,
        )
    except WebNotificationSoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved, previous_key = await web_notification_repository.set_sound(prepared)
    if previous_key and previous_key != prepared.key:
        await run_media_blocking(web_notification_sound_storage.delete, previous_key)
    return saved


@app.delete(
    "/api/settings/message-services/web-notification/sound",
    response_model=WebNotificationConfigPayload,
)
async def clear_web_notification_sound() -> WebNotificationConfigPayload:
    saved, previous_key = await web_notification_repository.clear_sound()
    if previous_key:
        await run_media_blocking(web_notification_sound_storage.delete, previous_key)
    return saved


@app.get(
    "/api/settings/message-services/chatwoot",
    response_model=ChatwootConfigPayload,
)
async def get_chatwoot_config(response: Response) -> ChatwootConfigPayload:
    # The payload includes the administrator-only Chatwoot Access Token.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    config = await chatwoot_repository.get_config_payload()
    if config is None:
        raise HTTPException(status_code=404, detail="Chatwoot config not found")
    return config


@app.put(
    "/api/settings/message-services/chatwoot",
    response_model=ChatwootConfigPayload,
)
async def update_chatwoot_config(
    payload: ChatwootConfigUpdatePayload,
) -> ChatwootConfigPayload:
    try:
        saved = await save_chatwoot_config(chatwoot_repository, payload)
    except (ValueError, ChatwootIntegrationError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if saved.enabled:
        for account in await store.list_accounts():
            if not account.chat_enabled:
                continue
            await enqueue_account_metadata_sync(
                store,
                account_id=account.account_id,
                reason="platform-config-saved",
            )
            if account.runtime is not None:
                await enqueue_account_status_sync(
                    store,
                    account_id=account.account_id,
                    state=account.runtime.state,
                    message=account.runtime.message,
                )
    return saved


@app.post(
    "/api/settings/message-services/chatwoot/test",
    response_model=ChatwootTestResultPayload,
)
async def test_saved_chatwoot_config() -> ChatwootTestResultPayload:
    result = await test_chatwoot_config(chatwoot_repository)
    if not result.success:
        raise HTTPException(status_code=503, detail=result.message)
    return result


@app.post(
    "/api/settings/message-services/chatwoot/resync",
    response_model=ChatwootTestResultPayload,
)
async def resync_chatwoot_account_structure() -> ChatwootTestResultPayload:
    queued = 0
    for account in await store.list_accounts():
        if not account.chat_enabled:
            continue
        await enqueue_account_metadata_sync(
            store,
            account_id=account.account_id,
            reason="manual-platform-resync",
        )
        queued += 1
    if queued == 0:
        raise HTTPException(
            status_code=409,
            detail="没有开启 Chatwoot 的平台账户，无法重新同步账户结构",
        )
    return ChatwootTestResultPayload(
        success=True,
        message=f"已提交 {queued} 个账户的 Inbox、标签和属性同步任务",
    )


@app.post(
    "/api/settings/message-services/chatwoot/account-alert-test",
    response_model=ChatwootTestResultPayload,
)
async def test_chatwoot_account_alerts() -> ChatwootTestResultPayload:
    candidates = [
        account
        for account in await store.list_accounts()
        if account.enabled and account.chat_enabled
    ]
    if not candidates:
        raise HTTPException(
            status_code=409,
            detail="没有已启用 Chat 的平台账户，无法发送账户状态测试提醒",
        )
    delivered = 0
    failures: list[str] = []
    for account in candidates:
        try:
            result = await execute_account_alert_task(
                store,
                account_id=account.account_id,
                state="test",
                message="这是平台发出的账户状态提醒测试消息",
                force=True,
            )
        except Exception as exc:
            failures.append(f"{account.display_name}: {exc}")
            continue
        if result.get("ok") and not result.get("skipped"):
            delivered += 1
    if failures:
        raise HTTPException(
            status_code=503,
            detail=(
                f"已发送 {delivered} 个账户提醒，"
                f"{len(failures)} 个失败：{'；'.join(failures)}"
            ),
        )
    return ChatwootTestResultPayload(
        success=True,
        message=f"已向 Chatwoot 发送 {delivered} 个账户状态测试提醒",
    )


@app.post(
    "/api/integrations/chatwoot/webhook",
    response_model=ChatwootWebhookAcceptedPayload,
    status_code=202,
)
async def receive_chatwoot_webhook(
    request: Request,
) -> ChatwootWebhookAcceptedPayload:
    raw_body = await request.body()
    try:
        return await accept_chatwoot_webhook(
            store,
            chatwoot_repository,
            raw_body=raw_body,
            signature=(
                request.headers.get("x-chatwoot-signature")
                or request.headers.get("x-chatwoot-signature-256")
            ),
            timestamp=request.headers.get("x-chatwoot-timestamp"),
            delivery_header=request.headers.get("x-chatwoot-delivery"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ChatwootIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/me/auto-reply/rules", response_model=list[AutoReplyRulePayload])
async def list_my_auto_reply_rules(request: Request) -> list[AutoReplyRulePayload]:
    user: UserPayload = request.state.auth_user
    return await store.list_user_auto_reply_rules(user.user_id)


@app.post(
    "/api/me/auto-reply/rules",
    response_model=AutoReplyRulePayload,
    status_code=201,
)
async def create_my_auto_reply_rule(
    request: Request,
    payload: AutoReplyRuleCreatePayload,
) -> AutoReplyRulePayload:
    user: UserPayload = request.state.auth_user
    created = await store.create_user_auto_reply_rule(user.user_id, payload)
    assert created is not None
    return created


@app.put(
    "/api/me/auto-reply/rules/order",
    response_model=list[AutoReplyRulePayload],
)
async def reorder_my_auto_reply_rules(
    request: Request,
    payload: AutoReplyRuleReorderPayload,
) -> list[AutoReplyRulePayload]:
    user: UserPayload = request.state.auth_user
    try:
        reordered = await store.reorder_user_auto_reply_rules(user.user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if reordered is None:
        raise HTTPException(status_code=404, detail="user not found")
    return reordered


@app.get(
    "/api/me/auto-reply/rules/issues",
    response_model=list[AutoReplyRuleIssuePayload],
)
async def list_my_auto_reply_rule_issues(
    request: Request,
) -> list[AutoReplyRuleIssuePayload]:
    user: UserPayload = request.state.auth_user
    return await store.list_user_auto_reply_rule_issues(user.user_id)


@app.post(
    "/api/me/auto-reply/preview",
    response_model=AutoReplyPreviewResultPayload,
)
async def preview_my_auto_reply(
    request: Request,
    payload: AutoReplyPreviewRequestPayload,
) -> AutoReplyPreviewResultPayload:
    user: UserPayload = request.state.auth_user
    preview = await store.preview_user_auto_reply(user.user_id, payload)
    if preview is None:
        raise HTTPException(status_code=404, detail="account not found or not assigned to current user")
    return preview


@app.put(
    "/api/me/auto-reply/rules/{rule_id}", response_model=AutoReplyRulePayload
)
async def update_my_auto_reply_rule(
    rule_id: str,
    request: Request,
    payload: AutoReplyRuleUpdatePayload,
) -> AutoReplyRulePayload:
    user: UserPayload = request.state.auth_user
    updated = await store.update_user_auto_reply_rule(user.user_id, rule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="auto reply rule not found")
    return updated


@app.delete("/api/me/auto-reply/rules/{rule_id}", status_code=204)
async def delete_my_auto_reply_rule(rule_id: str, request: Request) -> None:
    user: UserPayload = request.state.auth_user
    if not await store.delete_user_auto_reply_rule(user.user_id, rule_id):
        raise HTTPException(status_code=404, detail="auto reply rule not found")


@app.get("/api/me/auto-reply/logs", response_model=list[AutoReplyLogPayload])
async def list_my_auto_reply_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AutoReplyLogPayload]:
    user: UserPayload = request.state.auth_user
    return await store.list_user_auto_reply_logs(user.user_id, limit=limit)


@app.get("/api/accounts/{account_id}/delivery/templates", response_model=list[DeliveryTemplatePayload])
async def list_delivery_templates(account_id: str) -> list[DeliveryTemplatePayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_delivery_templates(account_id)


@app.post(
    "/api/accounts/{account_id}/delivery/templates",
    response_model=DeliveryTemplatePayload,
    status_code=201,
)
async def create_delivery_template(
    account_id: str,
    payload: DeliveryTemplateCreatePayload,
) -> DeliveryTemplatePayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    created = await store.create_delivery_template(account_id, payload)
    assert created is not None
    return created


@app.put(
    "/api/accounts/{account_id}/delivery/templates/{template_id}",
    response_model=DeliveryTemplatePayload,
)
async def update_delivery_template(
    account_id: str,
    template_id: str,
    payload: DeliveryTemplateUpdatePayload,
) -> DeliveryTemplatePayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    updated = await store.update_delivery_template(account_id, template_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="delivery template not found")
    return updated


@app.delete("/api/accounts/{account_id}/delivery/templates/{template_id}", status_code=204)
async def delete_delivery_template(account_id: str, template_id: str) -> None:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    deleted = await store.delete_delivery_template(account_id, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="delivery template not found")


@app.get("/api/accounts/{account_id}/delivery/records", response_model=list[DeliveryRecordPayload])
async def list_delivery_records(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DeliveryRecordPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_delivery_records(account_id, limit=limit)


@app.get(
    "/api/accounts/{account_id}/delivery/automation",
    response_model=DeliveryAutomationSettingPayload,
)
async def get_delivery_automation_setting(account_id: str) -> DeliveryAutomationSettingPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    setting = await store.get_delivery_automation_setting(account_id)
    assert setting is not None
    return setting


@app.put(
    "/api/accounts/{account_id}/delivery/automation",
    response_model=DeliveryAutomationSettingPayload,
)
async def update_delivery_automation_setting(
    account_id: str,
    payload: DeliveryAutomationSettingUpdatePayload,
) -> DeliveryAutomationSettingPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    updated = await store.update_delivery_automation_setting(account_id, payload)
    assert updated is not None
    return updated


@app.post(
    "/api/accounts/{account_id}/delivery/records/{record_id}/preflight",
    response_model=DeliveryPreflightPayload,
)
async def check_delivery_preflight(account_id: str, record_id: str) -> DeliveryPreflightPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    result = await store.check_delivery_preflight(account_id, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="delivery record not found")
    return result


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/delivery/prepare",
    response_model=DeliveryRecordPayload,
    status_code=201,
)
async def prepare_delivery_record(
    account_id: str,
    conversation_id: str,
    payload: DeliveryPreparePayload,
) -> DeliveryRecordPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    prepared = await store.prepare_delivery_record(account_id, conversation_id, payload)
    if prepared is None:
        raise HTTPException(status_code=400, detail="failed to prepare delivery record")
    return prepared


@app.post(
    "/api/accounts/{account_id}/delivery/records/{record_id}/send",
    response_model=DeliverySendResultPayload,
)
async def send_delivery_record(account_id: str, record_id: str) -> DeliverySendResultPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    result = await runtime_manager.send_delivery_record(record, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="delivery record not found")
    return result


@app.post(
    "/api/accounts/{account_id}/delivery/records/{record_id}/enqueue",
    response_model=BackgroundTaskPayload,
    status_code=201,
)
async def enqueue_delivery_record(account_id: str, record_id: str) -> BackgroundTaskPayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    lock = delivery_enqueue_locks.setdefault(record_id, asyncio.Lock())
    async with lock:
        record = await store.get_delivery_record(account_id, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="delivery record not found")
        if record.status not in {"pending", "failed"}:
            state_errors = {
                "sending": "delivery record is already being sent",
                "sent": "delivery record was already sent",
                "uncertain": "delivery result is uncertain and must be verified before retrying",
                "cancelled": "delivery record was cancelled",
            }
            raise HTTPException(
                status_code=409,
                detail=state_errors.get(record.status, "delivery record cannot be queued"),
            )
        created = await store.create_background_task(
            BackgroundTaskCreatePayload(
                account_id=account_id,
                task_type="delivery.send_record",
                dedupe_key=f"delivery-send:{record_id}",
                payload={"account_id": account_id, "record_id": record_id},
            )
        )
        assert created is not None
        if created.status == "failed":
            reset = await store.reset_background_task_for_retry(created.task_id)
            if reset is not None:
                created = reset
        if created.status == "success":
            raise HTTPException(
                status_code=409,
                detail="delivery task already completed but record is not marked sent",
            )
        if created.status == "pending" and created.queued_at is None:
            await _enqueue_or_fail(created)
            refreshed = await store.get_background_task(created.task_id)
            if refreshed is not None:
                created = refreshed
        return created


@app.get(
    "/api/accounts/{account_id}/im/conversations",
    response_model=ConversationPagePayload,
)
async def sync_account_conversations(
    account_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> ConversationPagePayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    cached = await store.list_conversations(account_id=account_id, limit=limit)
    online = runtime_manager.is_online(account_id)
    status = await runtime_manager.conversation_sync_status(account_id)
    return ConversationPagePayload(
        items=cached,
        source="cache",
        connection_state=account.runtime.state,
        stale=not online,
        error=None if online else "闲鱼 IM 当前未在线",
        account_statuses=[status],
    )


@app.post(
    "/api/accounts/{account_id}/im/conversations/sync",
    response_model=ConversationPagePayload,
)
async def refresh_account_conversations(
    account_id: str,
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ConversationPagePayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        items, has_more, next_cursor = await runtime_manager.sync_conversations(
            account_id, cursor=cursor, limit=limit
        )
        return ConversationPagePayload(
            items=items,
            has_more=has_more,
            next_cursor=next_cursor,
            source="live",
            connection_state="online",
            stale=False,
            account_statuses=[await runtime_manager.conversation_sync_status(account_id)],
        )
    except Exception as exc:
        cached = await store.list_conversations(account_id=account_id, limit=limit)
        latest = await store.get_account(account_id)
        return ConversationPagePayload(
            items=cached,
            source="cache",
            connection_state=latest.runtime.state if latest else account.runtime.state,
            stale=True,
            error=str(exc)[:300],
            account_statuses=[await runtime_manager.conversation_sync_status(account_id)],
        )


@app.get("/api/im/conversations", response_model=ConversationPagePayload)
async def list_aggregate_conversations(
    request: Request,
    account_id: str | None = Query(default=None, max_length=64),
    status: Literal["all", "unread"] = Query(default="all"),
    cursor: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=100, ge=1, le=200),
) -> ConversationPagePayload:
    if account_id is not None and await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    user: UserPayload = request.state.auth_user
    items, has_more, next_cursor = await store.list_conversations_for_user(
        user.user_id,
        account_id=account_id,
        status=status,
        limit=limit,
        cursor=cursor,
    )
    accounts = [
        account
        for account in await store.list_accounts()
        if account.enabled
        and account.conversation_visible
        and account.runtime.state not in {"disabled", "deleting"}
    ]
    if account_id is not None:
        accounts = [account for account in accounts if account.account_id == account_id]
    account_statuses = await runtime_manager.list_conversation_sync_statuses(accounts)
    any_online = any(runtime_manager.is_online(account.account_id) for account in accounts)
    degraded = [
        status
        for status in account_statuses
        if status.state in {"error", "offline"}
    ]
    return ConversationPagePayload(
        items=items,
        has_more=has_more,
        next_cursor=next_cursor,
        source="cache",
        connection_state="online" if any_online else "stopped",
        stale=not any_online or bool(degraded),
        error=(
            "当前没有在线账户，显示本地缓存"
            if not any_online
            else "部分账户会话同步异常，正在显示已有缓存"
            if degraded
            else None
        ),
        account_statuses=account_statuses,
    )


@app.post(
    "/api/im/conversations/{account_id}/{conversation_id}/read",
    response_model=ConversationPayload,
)
async def mark_aggregate_conversation_read(
    request: Request,
    account_id: str,
    conversation_id: str,
) -> ConversationPayload:
    user: UserPayload = request.state.auth_user
    conversation = await store.mark_conversation_read(
        user.user_id,
        account_id,
        conversation_id,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    await realtime_broker.publish(
        {
            "event": "conversation_read",
            "user_id": user.user_id,
            "data": conversation.model_dump(mode="json"),
        }
    )
    return conversation


@app.get(
    "/api/accounts/{account_id}/im/conversations/{conversation_id}/messages",
    response_model=MessagePagePayload,
)
async def sync_conversation_messages(
    account_id: str,
    conversation_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> MessagePagePayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    cached = await store.list_messages(
        account_id=account_id,
        conversation_id=conversation_id,
        limit=limit,
    )
    online = runtime_manager.is_online(account_id)
    return MessagePagePayload(
        items=cached,
        source="cache",
        connection_state=account.runtime.state,
        stale=not online,
        error=None if online else "闲鱼 IM 当前未在线",
    )


@app.post(
    "/api/accounts/{account_id}/im/conversations/{conversation_id}/messages/sync",
    response_model=MessagePagePayload,
)
async def refresh_conversation_messages(
    account_id: str,
    conversation_id: str,
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> MessagePagePayload:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        items, has_more, next_cursor = await runtime_manager.sync_messages(
            account_id,
            conversation_id,
            cursor=cursor,
            limit=limit,
        )
        return MessagePagePayload(
            items=items,
            has_more=has_more,
            next_cursor=next_cursor,
            source="live",
            connection_state="online",
            stale=False,
        )
    except Exception as exc:
        cached = await store.list_messages(
            account_id=account_id,
            conversation_id=conversation_id,
            limit=limit,
        )
        latest = await store.get_account(account_id)
        return MessagePagePayload(
            items=cached,
            source="cache",
            connection_state=latest.runtime.state if latest else account.runtime.state,
            stale=True,
            error=str(exc)[:300],
        )


@app.get("/api/accounts/{account_id}/conversations", response_model=list[ConversationPayload])
async def list_account_conversations(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ConversationPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_conversations(account_id=account_id, limit=limit)


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/manual-takeover",
    response_model=ManualTakeoverStatusPayload,
)
async def set_conversation_manual_takeover(
    account_id: str,
    conversation_id: str,
    payload: ManualTakeoverPayload,
) -> ManualTakeoverStatusPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    conversations = await store.list_conversations(account_id=account_id, limit=500)
    if not any(item.conversation_id == conversation_id for item in conversations):
        raise HTTPException(status_code=404, detail="conversation not found")
    until = await store.set_manual_takeover(
        account_id,
        conversation_id,
        active=payload.active,
        minutes=payload.minutes,
        mode=payload.resolved_mode,
    )
    mode = payload.resolved_mode
    return ManualTakeoverStatusPayload(
        account_id=account_id,
        conversation_id=conversation_id,
        active=mode != "auto",
        mode=mode,
        until=until,
    )


@app.get(
    "/api/accounts/{account_id}/conversations/{conversation_id}/messages",
    response_model=list[MessagePayload],
)
async def list_conversation_messages(
    account_id: str,
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MessagePayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_messages(
        account_id=account_id,
        conversation_id=conversation_id,
        limit=limit,
    )


@app.get(
    "/api/accounts/{account_id}/conversations/{conversation_id}"
    "/messages/{message_pk}/audio"
)
async def get_message_audio(
    account_id: str,
    conversation_id: str,
    message_pk: str,
) -> Response:
    message = await store.get_message(account_id, conversation_id, message_pk)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    audio_url = next(
        (
            attachment.remote_url
            for attachment in message.attachments
            if attachment.attachment_type == "audio" and attachment.remote_url
        ),
        None,
    )
    if not audio_url:
        audio_url = _extract_xianyu_audio_url(message.raw_payload)
    if not audio_url:
        raise HTTPException(status_code=404, detail="audio attachment not found")
    try:
        data, mime_type, filename = await run_external_blocking(
            _download_xianyu_audio,
            audio_url,
        )
    except ChatwootIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/item/sync",
    response_model=ConversationPayload,
)
async def sync_conversation_item(
    account_id: str,
    conversation_id: str,
) -> ConversationPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        return await runtime_manager.sync_conversation_item(account_id, conversation_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/accounts/{account_id}/message-cards", response_model=list[MessageCardPayload])
async def list_account_message_cards(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MessageCardPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_message_cards(account_id=account_id, limit=limit)


@app.get(
    "/api/accounts/{account_id}/conversations/{conversation_id}/cards",
    response_model=list[MessageCardPayload],
)
async def list_conversation_cards(
    account_id: str,
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MessageCardPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_message_cards(
        account_id=account_id,
        conversation_id=conversation_id,
        limit=limit,
    )


@app.get("/api/orders", response_model=list[OrderPayload])
async def list_orders(
    account_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    trade_role: Literal["seller", "buyer", "unknown", "all"] = Query(default="seller"),
    confirmed_only: bool = Query(default=True),
    management_visible_only: bool = Query(default=False),
    keyword: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[OrderPayload]:
    return await store.list_orders(
        account_id=account_id,
        conversation_id=conversation_id,
        status=status,
        trade_role=trade_role,
        confirmed_only=confirmed_only,
        keyword=keyword,
        management_visible_only=management_visible_only,
        limit=limit,
    )


@app.get(
    "/api/accounts/{account_id}/conversations/{conversation_id}/orders",
    response_model=list[OrderPayload],
)
async def list_conversation_orders(
    account_id: str,
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[OrderPayload]:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_orders(
        account_id=account_id,
        conversation_id=conversation_id,
        limit=limit,
    )


@app.get(
    "/api/order-management/accounts",
    response_model=list[OrderAccountSummaryPayload],
)
async def list_order_management_accounts(
    scope: Literal["bought", "sold"] = Query(default="sold"),
) -> list[OrderAccountSummaryPayload]:
    return await order_management_repository.list_account_summaries(scope)


@app.get(
    "/api/accounts/{account_id}/order-management/settings",
    response_model=OrderSyncSettingPayload,
)
async def get_order_management_setting(
    account_id: str,
    scope: Literal["bought", "sold"] = Query(default="sold"),
) -> OrderSyncSettingPayload:
    setting = await order_management_repository.get_setting(account_id, scope)
    if setting is None:
        raise HTTPException(status_code=404, detail="account not found")
    return setting


@app.put(
    "/api/accounts/{account_id}/order-management/settings",
    response_model=OrderSyncSettingPayload,
)
async def update_order_management_setting(
    account_id: str,
    payload: OrderSyncSettingUpdatePayload,
    scope: Literal["bought", "sold"] = Query(default="sold"),
) -> OrderSyncSettingPayload:
    setting = await order_management_repository.update_setting(account_id, payload, scope)
    if setting is None:
        raise HTTPException(status_code=404, detail="account not found")
    return setting


@app.get(
    "/api/accounts/{account_id}/order-management/sync-runs",
    response_model=list[OrderSyncRunPayload],
)
async def list_order_sync_runs(
    account_id: str,
    limit: int = Query(default=30, ge=1, le=200),
    scope: Literal["bought", "sold"] = Query(default="sold"),
) -> list[OrderSyncRunPayload]:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await order_management_repository.list_runs(account_id, limit=limit, scope=scope)


@app.post(
    "/api/accounts/{account_id}/order-management/sync",
    response_model=OrderSyncEnqueuePayload,
    status_code=202,
)
async def enqueue_order_sync(
    account_id: str,
    payload: OrderSyncRequestPayload,
) -> OrderSyncEnqueuePayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        run, task = await create_and_enqueue_order_sync(
            store,
            order_management_repository,
            account_id=account_id,
            scope=payload.scope,
            mode=payload.mode,
            trigger="manual",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"订单同步任务入队失败: {exc.__class__.__name__}: {exc}",
        ) from exc
    return OrderSyncEnqueuePayload(run=run, background_task=task)


@app.get("/api/orders/{order_pk}", response_model=OrderDetailPayload)
async def get_order(order_pk: str) -> OrderDetailPayload:
    order = await store.get_order(order_pk)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@app.post("/api/orders/{order_pk}/sync", response_model=OrderDetailPayload)
async def sync_order(order_pk: str) -> OrderDetailPayload:
    order = await store.get_order(order_pk)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    try:
        if order.trade_role == "seller" and order.platform_confirmed:
            return await order_action_service.refresh(order_pk)
        return await runtime_manager.sync_order_headinfo(order)
    except OrderActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OrderActionError as exc:
        raise HTTPException(status_code=409 if exc.kind == "auth" else 502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/orders/{order_pk}/operations/preview",
    response_model=OrderOperationPreviewPayload,
)
async def preview_order_operation(
    order_pk: str,
    payload: OrderOperationPreviewRequest,
) -> OrderOperationPreviewPayload:
    try:
        return await order_action_service.preview(order_pk, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/orders/{order_pk}/operations",
    response_model=OrderOperationExecutePayload,
)
async def execute_order_operation(
    request: Request,
    order_pk: str,
    payload: OrderOperationExecuteRequest,
) -> OrderOperationExecutePayload:
    user: UserPayload = request.state.auth_user
    try:
        return await order_action_service.execute(
            order_pk,
            payload,
            requested_by=user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrderActionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OrderActionError as exc:
        raise HTTPException(status_code=409 if exc.kind == "auth" else 502, detail=str(exc)) from exc


@app.post(
    "/api/orders/{order_pk}/delivery/preview",
    response_model=OrderDeliveryPreviewPayload,
)
async def preview_order_delivery(
    order_pk: str,
    payload: OrderDeliveryPreviewRequest,
) -> OrderDeliveryPreviewPayload:
    preview = await store.preview_order_delivery(order_pk, payload)
    if preview is None:
        raise HTTPException(status_code=404, detail="order or delivery template not found")
    return preview


@app.post(
    "/api/orders/{order_pk}/delivery/send",
    response_model=DeliverySendResultPayload,
)
async def send_order_delivery(
    order_pk: str,
    payload: OrderDeliveryPreviewRequest,
) -> DeliverySendResultPayload:
    preview = await store.preview_order_delivery(order_pk, payload)
    if preview is None:
        raise HTTPException(status_code=404, detail="order or delivery template not found")
    if not preview.eligible:
        raise HTTPException(status_code=409, detail={"reasons": preview.reasons})
    prepared = await store.prepare_order_delivery(order_pk, payload)
    if prepared is None:
        raise HTTPException(status_code=409, detail="order delivery was already prepared")
    account = await store.get_account(prepared.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    result = await runtime_manager.send_delivery_record(account, prepared.record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="delivery record not found")
    return result


async def _enqueue_product_management_operation(
    account_id: str,
    operation: Literal["sync", "polish", "offline", "delete"],
    *,
    item_ids: list[str] | None = None,
    full_sync: bool = False,
) -> ProductOperationEnqueuePayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    if item_ids:
        candidates = await product_management_repository.operation_candidates(
            account_id, item_ids
        )
        found_ids = {item.item_id for item in candidates}
        missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "部分商品不属于当前账户或尚未同步",
                    "item_ids": missing_ids,
                },
            )
    try:
        run, task = await create_and_enqueue_product_run(
            store,
            product_management_repository,
            account_id=account_id,
            operation=operation,
            trigger="manual",
            item_ids=item_ids,
            full_sync=full_sync,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"商品任务入队失败: {exc.__class__.__name__}: {exc}",
        ) from exc
    return ProductOperationEnqueuePayload(run=run, background_task=task)


@app.get(
    "/api/product-management/accounts",
    response_model=list[ProductAccountSummaryPayload],
)
async def list_product_management_accounts() -> list[ProductAccountSummaryPayload]:
    return await product_management_repository.list_account_summaries()


@app.get(
    "/api/accounts/{account_id}/product-management/items",
    response_model=list[ProductItemPayload],
)
async def list_managed_products(
    account_id: str,
    status: Literal["all", "selling", "offline", "deleted", "not_selling", "unknown"] = Query(
        default="all"
    ),
    keyword: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[ProductItemPayload]:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await product_management_repository.list_items(
        account_id,
        status=status,
        keyword=keyword,
        limit=limit,
    )


@app.delete(
    "/api/accounts/{account_id}/product-management/items/{item_id}/local",
    response_model=ProductLocalCleanupPayload,
)
async def delete_local_managed_product(
    account_id: str,
    item_id: str,
) -> ProductLocalCleanupPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        result = await product_management_repository.delete_local_item(account_id, item_id)
    except ProductLocalCleanupConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="managed product not found")
    return result


@app.get(
    "/api/accounts/{account_id}/product-management/settings",
    response_model=ProductSyncSettingPayload,
)
async def get_product_management_setting(account_id: str) -> ProductSyncSettingPayload:
    setting = await product_management_repository.get_setting(account_id)
    if setting is None:
        raise HTTPException(status_code=404, detail="account not found")
    return setting


@app.put(
    "/api/accounts/{account_id}/product-management/settings",
    response_model=ProductSyncSettingPayload,
)
async def update_product_management_setting(
    account_id: str,
    payload: ProductSyncSettingUpdatePayload,
) -> ProductSyncSettingPayload:
    setting = await product_management_repository.update_setting(account_id, payload)
    if setting is None:
        raise HTTPException(status_code=404, detail="account not found")
    return setting


@app.get(
    "/api/accounts/{account_id}/product-management/operations",
    response_model=list[ProductOperationRunPayload],
)
async def list_product_management_operations(
    account_id: str,
    limit: int = Query(default=30, ge=1, le=200),
) -> list[ProductOperationRunPayload]:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await product_management_repository.list_runs(account_id, limit=limit)


@app.post(
    "/api/accounts/{account_id}/product-management/sync",
    response_model=ProductOperationEnqueuePayload,
    status_code=202,
)
async def enqueue_product_sync(
    account_id: str,
    payload: ProductSyncRequestPayload,
) -> ProductOperationEnqueuePayload:
    return await _enqueue_product_management_operation(
        account_id, "sync", full_sync=payload.full
    )


@app.post(
    "/api/accounts/{account_id}/product-management/polish",
    response_model=ProductOperationEnqueuePayload,
    status_code=202,
)
async def enqueue_product_polish(
    account_id: str,
    payload: ProductItemOperationRequestPayload,
) -> ProductOperationEnqueuePayload:
    return await _enqueue_product_management_operation(
        account_id, "polish", item_ids=payload.item_ids
    )


@app.post(
    "/api/accounts/{account_id}/product-management/offline",
    response_model=ProductOperationEnqueuePayload,
    status_code=202,
)
async def enqueue_product_offline(
    account_id: str,
    payload: ProductItemOperationRequestPayload,
) -> ProductOperationEnqueuePayload:
    return await _enqueue_product_management_operation(
        account_id, "offline", item_ids=payload.item_ids
    )


@app.post(
    "/api/accounts/{account_id}/product-management/delete",
    response_model=ProductOperationEnqueuePayload,
    status_code=202,
)
async def enqueue_product_delete(
    account_id: str,
    payload: ProductItemOperationRequestPayload,
) -> ProductOperationEnqueuePayload:
    return await _enqueue_product_management_operation(
        account_id, "delete", item_ids=payload.item_ids
    )


@app.get("/api/accounts/{account_id}/products/drafts", response_model=list[ProductDraftPayload])
async def list_product_drafts(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProductDraftPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_product_drafts(account_id, limit=limit)


@app.get(
    "/api/accounts/{account_id}/products/locations",
    response_model=ProductLocationListPayload,
)
async def list_product_locations(
    account_id: str,
    longitude: float = Query(default=118.78248347393424, ge=-180, le=180),
    latitude: float = Query(default=31.91629189813543, ge=-90, le=90),
    refresh: bool = Query(default=False),
) -> ProductLocationListPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        return await list_platform_product_locations(
            store,
            account_id,
            longitude=longitude,
            latitude=latitude,
            force_refresh=refresh,
        )
    except ProductPublishError as exc:
        raise HTTPException(status_code=503 if exc.retryable else 409, detail=str(exc)) from exc


@app.get("/api/product-regions", response_model=ProductRegionCatalogPayload)
async def list_product_regions() -> ProductRegionCatalogPayload:
    return product_region_catalog.catalog_payload()


@app.get("/api/product-address-groups", response_model=list[PublishAddressGroupPayload])
async def list_publish_address_groups(
    account_id: str | None = Query(default=None),
) -> list[PublishAddressGroupPayload]:
    return await store.list_publish_address_groups(account_id)


@app.post(
    "/api/product-address-groups",
    response_model=PublishAddressGroupPayload,
    status_code=201,
)
async def create_publish_address_group(
    payload: PublishAddressGroupCreatePayload,
) -> PublishAddressGroupPayload:
    try:
        return await store.create_publish_address_group(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put(
    "/api/product-address-groups/{group_id}",
    response_model=PublishAddressGroupPayload,
)
async def update_publish_address_group(
    group_id: str,
    payload: PublishAddressGroupUpdatePayload,
) -> PublishAddressGroupPayload:
    try:
        updated = await store.update_publish_address_group(group_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="publish address group not found")
    return updated


@app.delete("/api/product-address-groups/{group_id}", status_code=204)
async def delete_publish_address_group(group_id: str) -> None:
    if not await store.delete_publish_address_group(group_id):
        raise HTTPException(status_code=404, detail="publish address group not found")


@app.get(
    "/api/product-address-groups/{group_id}/addresses",
    response_model=list[PublishAddressPayload],
)
async def list_publish_addresses(
    group_id: str,
    include_regions: bool = Query(default=False),
) -> list[PublishAddressPayload]:
    return await store.list_publish_addresses(group_id, include_regions=include_regions)


@app.get(
    "/api/product-address-groups/{group_id}/regions",
    response_model=PublishAddressRegionSelectionResultPayload,
)
async def get_publish_address_regions(
    group_id: str,
) -> PublishAddressRegionSelectionResultPayload:
    result = await store.get_publish_address_regions(group_id)
    if result is None:
        raise HTTPException(status_code=404, detail="publish address group not found")
    return result


@app.put(
    "/api/product-address-groups/{group_id}/regions",
    response_model=PublishAddressRegionSelectionResultPayload,
)
async def replace_publish_address_regions(
    group_id: str,
    payload: PublishAddressRegionSelectionPayload,
) -> PublishAddressRegionSelectionResultPayload:
    try:
        result = await store.replace_publish_address_regions(group_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="publish address group not found")
    return result


@app.post(
    "/api/product-address-groups/{group_id}/addresses",
    response_model=PublishAddressPayload,
    status_code=201,
)
async def create_publish_address(
    group_id: str,
    payload: PublishAddressCreatePayload,
) -> PublishAddressPayload:
    try:
        created = await store.create_publish_address(group_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if created is None:
        raise HTTPException(status_code=404, detail="publish address group not found")
    return created


@app.put(
    "/api/product-address-groups/{group_id}/addresses/{address_id}",
    response_model=PublishAddressPayload,
)
async def update_publish_address(
    group_id: str,
    address_id: str,
    payload: PublishAddressUpdatePayload,
) -> PublishAddressPayload:
    updated = await store.update_publish_address(group_id, address_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="publish address not found")
    return updated


@app.delete(
    "/api/product-address-groups/{group_id}/addresses/{address_id}",
    status_code=204,
)
async def delete_publish_address(group_id: str, address_id: str) -> None:
    if not await store.delete_publish_address(group_id, address_id):
        raise HTTPException(status_code=404, detail="publish address not found")


@app.get(
    "/api/accounts/{account_id}/products/images",
    response_model=list[ProductImageAssetPayload],
)
async def list_product_images(
    account_id: str,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[ProductImageAssetPayload]:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_product_image_assets(account_id, limit=limit)


@app.post(
    "/api/accounts/{account_id}/products/images",
    response_model=ProductImageAssetPayload,
    status_code=201,
)
async def upload_product_image(
    account_id: str,
    image: UploadFile = File(...),
    upload_session_id: str | None = Form(default=None, max_length=64),
) -> ProductImageAssetPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        raw = await image.read(MAX_IMAGE_INPUT_BYTES + 1)
    finally:
        await image.close()
    if not raw:
        raise HTTPException(status_code=422, detail="image file is empty")
    if len(raw) > MAX_IMAGE_INPUT_BYTES:
        raise HTTPException(status_code=413, detail="image file exceeds the 10 MB limit")
    try:
        stored = await run_media_blocking(product_image_storage.save, account_id, raw)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    prepared = stored.prepared
    try:
        created = await store.create_product_image_asset(
            account_id=account_id,
            asset_id=stored.asset_id,
            original_filename=(image.filename or prepared.filename),
            mime_type=prepared.mime_type,
            width=prepared.width,
            height=prepared.height,
            size_bytes=prepared.size_bytes,
            sha256=prepared.sha256,
            upload_session_id=upload_session_id,
        )
    except Exception:
        await run_media_blocking(product_image_storage.delete, account_id, stored.asset_id)
        raise
    if created is None:
        await run_media_blocking(product_image_storage.delete, account_id, stored.asset_id)
        raise HTTPException(status_code=404, detail="account not found")
    return created


@app.post(
    "/api/accounts/{account_id}/products/images/archive",
    response_model=ProductImageArchiveUploadPayload,
    status_code=201,
)
async def upload_product_image_archive(
    account_id: str,
    archive: UploadFile = File(...),
    upload_session_id: str | None = Form(default=None, max_length=64),
    limit: int = Form(default=9, ge=1, le=9),
) -> ProductImageArchiveUploadPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        imported = await run_media_blocking(
            import_product_image_archive,
            archive.file,
            account_id=account_id,
            limit=limit,
            storage=product_image_storage,
        )
    except ProductImageArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await archive.close()

    if not imported.images:
        if imported.rejected_images:
            first = imported.rejected_images[0]
            detail = f"压缩包中没有可导入的有效图片：{first.filename}（{first.reason}）"
        else:
            detail = "压缩包中没有 JPEG、PNG 或 WebP 图片"
        raise HTTPException(status_code=422, detail=detail)

    created_assets: list[ProductImageAssetPayload] = []
    try:
        for image in imported.images:
            prepared = image.stored.prepared
            created = await store.create_product_image_asset(
                account_id=account_id,
                asset_id=image.stored.asset_id,
                original_filename=image.original_filename,
                mime_type=prepared.mime_type,
                width=prepared.width,
                height=prepared.height,
                size_bytes=prepared.size_bytes,
                sha256=prepared.sha256,
                upload_session_id=upload_session_id,
            )
            if created is None:
                raise HTTPException(status_code=404, detail="account not found")
            created_assets.append(created)
    except Exception:
        for created in created_assets:
            await store.delete_product_image_asset(account_id, created.asset_id)
        for image in imported.images:
            await run_media_blocking(
                product_image_storage.delete,
                account_id,
                image.stored.asset_id,
            )
        raise

    return ProductImageArchiveUploadPayload(
        assets=created_assets,
        ignored_non_image_count=imported.ignored_non_image_count,
        rejected_images=[
            ProductImageArchiveRejectedPayload(filename=item.filename, reason=item.reason)
            for item in imported.rejected_images
        ],
        skipped_limit_count=imported.skipped_limit_count,
    )


@app.get("/api/accounts/{account_id}/products/images/{asset_id}/content")
async def get_product_image_content(account_id: str, asset_id: str) -> FileResponse:
    asset = await store.get_product_image_asset(account_id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="product image not found")
    try:
        path = product_image_storage.path(account_id, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="product image not found") from exc
    if not path.is_file():
        raise HTTPException(status_code=410, detail="product image file is missing")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.delete(
    "/api/accounts/{account_id}/products/images/{asset_id}",
    status_code=204,
)
async def delete_product_image(account_id: str, asset_id: str) -> None:
    result = await store.delete_product_image_asset(account_id, asset_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="product image not found")
    if result == "in_use":
        raise HTTPException(status_code=409, detail="product image is still referenced")
    await run_media_blocking(product_image_storage.delete, account_id, asset_id)


@app.delete(
    "/api/accounts/{account_id}/products/upload-sessions/{upload_session_id}",
    status_code=204,
)
async def cleanup_product_upload_session(account_id: str, upload_session_id: str) -> None:
    deleted = await store.cleanup_product_upload_session(account_id, upload_session_id)
    for asset_id in deleted:
        await run_media_blocking(product_image_storage.delete, account_id, asset_id)


@app.post(
    "/api/accounts/{account_id}/products/drafts",
    response_model=ProductDraftPayload,
    status_code=201,
)
async def create_product_draft(
    account_id: str,
    payload: ProductDraftCreatePayload,
) -> ProductDraftPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    created = await store.create_product_draft(account_id, payload)
    assert created is not None
    return created


@app.put(
    "/api/accounts/{account_id}/products/drafts/{draft_id}",
    response_model=ProductDraftPayload,
)
async def update_product_draft(
    account_id: str,
    draft_id: str,
    payload: ProductDraftUpdatePayload,
) -> ProductDraftPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    updated = await store.update_product_draft(account_id, draft_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="product draft not found")
    return updated


@app.delete("/api/accounts/{account_id}/products/drafts/{draft_id}", status_code=204)
async def delete_product_draft(account_id: str, draft_id: str) -> None:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    deleted = await store.delete_product_draft(account_id, draft_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="product draft not found")


@app.get("/api/accounts/{account_id}/products/publish-tasks", response_model=list[ProductPublishTaskPayload])
async def list_product_publish_tasks(
    account_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProductPublishTaskPayload]:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await store.list_product_publish_tasks(account_id, limit=limit)


@app.post(
    "/api/accounts/{account_id}/products/publish-tasks",
    response_model=ProductPublishTaskPayload,
    status_code=201,
)
async def create_product_publish_task(
    account_id: str,
    payload: ProductPublishTaskCreatePayload,
) -> ProductPublishTaskPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    existing = (
        await store.get_product_publish_task_by_idempotency(account_id, payload.idempotency_key)
        if payload.idempotency_key
        else None
    )
    if existing is not None:
        return existing
    resolved_location = (
        await _resolve_product_task_location(account_id, payload.draft_id)
        if payload.mode == "platform_api"
        else None
    )
    try:
        created = await store.create_product_publish_task(
            account_id,
            payload,
            resolved_location=resolved_location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise _product_publish_persistence_error(account_id) from exc
    if created is None:
        raise HTTPException(status_code=404, detail="product draft not found")
    return created


@app.post(
    "/api/accounts/{account_id}/products/publish-tasks:enqueue",
    response_model=ProductPublishEnqueuePayload,
    status_code=201,
)
async def create_and_enqueue_product_publish_task(
    account_id: str,
    payload: ProductPublishTaskCreatePayload,
) -> ProductPublishEnqueuePayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    publish_task = (
        await store.get_product_publish_task_by_idempotency(account_id, payload.idempotency_key)
        if payload.idempotency_key
        else None
    )
    if publish_task is None:
        resolved_location = (
            await _resolve_product_task_location(account_id, payload.draft_id)
            if payload.mode == "platform_api"
            else None
        )
        try:
            publish_task = await store.create_product_publish_task(
                account_id,
                payload,
                resolved_location=resolved_location,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IntegrityError as exc:
            raise _product_publish_persistence_error(account_id) from exc
    if publish_task is None:
        raise HTTPException(status_code=404, detail="product draft not found")
    background_task = await _ensure_publish_background_task(account_id, publish_task)
    return ProductPublishEnqueuePayload(
        publish_task=publish_task,
        background_task=background_task,
    )


@app.post(
    "/api/accounts/{account_id}/product-management/publish-jobs",
    response_model=ProductPublishEnqueuePayload,
    status_code=202,
)
async def create_product_publish_job(
    account_id: str,
    payload: ProductPublishJobCreatePayload,
) -> ProductPublishEnqueuePayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        publish_task = await store.create_direct_product_publish_task(account_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise _product_publish_persistence_error(account_id) from exc
    if publish_task is None:
        raise HTTPException(status_code=404, detail="account not found")
    background_task = await _ensure_publish_background_task(account_id, publish_task)
    await realtime_broker.publish(
        {
            "event": "product_publish_task_upsert",
            "account_id": account_id,
            "data": publish_task.model_dump(mode="json"),
        }
    )
    return ProductPublishEnqueuePayload(
        publish_task=publish_task,
        background_task=background_task,
    )


@app.post(
    "/api/accounts/{account_id}/products/publish-tasks/{task_id}/retry",
    response_model=ProductPublishEnqueuePayload,
    status_code=202,
)
async def retry_product_publish_job(
    account_id: str,
    task_id: str,
    payload: ProductPublishRetryPayload,
) -> ProductPublishEnqueuePayload:
    try:
        publish_task = await store.retry_product_publish_task(account_id, task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise _product_publish_persistence_error(account_id) from exc
    if publish_task is None:
        raise HTTPException(status_code=404, detail="product publish task not found")
    background_task = await _ensure_publish_background_task(account_id, publish_task)
    await realtime_broker.publish(
        {
            "event": "product_publish_task_upsert",
            "account_id": account_id,
            "data": publish_task.model_dump(mode="json"),
        }
    )
    return ProductPublishEnqueuePayload(
        publish_task=publish_task,
        background_task=background_task,
    )


@app.post(
    "/api/accounts/{account_id}/products/publish-tasks/{task_id}/enqueue",
    response_model=BackgroundTaskPayload,
    status_code=201,
)
async def enqueue_product_publish_task(account_id: str, task_id: str) -> BackgroundTaskPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    publish_task = await store.get_product_publish_task(account_id, task_id)
    if publish_task is None:
        raise HTTPException(status_code=404, detail="product publish task not found")
    if publish_task.status != "pending":
        raise HTTPException(status_code=409, detail="only pending publish tasks can be enqueued")
    return await _ensure_publish_background_task(account_id, publish_task)


@app.post("/api/internal/accounts/{account_id}/runtime/reload-cookie")
async def reload_account_runtime_cookie(account_id: str) -> dict[str, bool]:
    account = await store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    applied = await runtime_manager.replace_cookie(account_id, account.cookie)
    return {"applied": applied}


@app.post("/api/internal/accounts/{account_id}/cookie-auth-failure")
async def report_account_cookie_auth_failure(
    account_id: str,
    payload: dict[str, str],
) -> CookieRenewalStatusPayload:
    if await store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    status = await cookie_renewal_manager.handle_auth_expired(
        account_id,
        source=str(payload.get("source") or "background_task")[:64],
        message=str(payload.get("message") or "平台会话已过期")[:500],
    )
    if status is None:
        raise HTTPException(status_code=404, detail="account not found")
    return status


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/send-text",
    response_model=SendTextResultPayload,
)
async def send_conversation_text(
    account_id: str,
    conversation_id: str,
    payload: SendTextPayload,
) -> SendTextResultPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await runtime_manager.send_text(record, conversation_id, payload)


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/send-image",
    response_model=SendImageResultPayload,
)
async def send_conversation_image(
    account_id: str,
    conversation_id: str,
    client_request_id: str = Form(...),
    image: UploadFile = File(...),
) -> SendImageResultPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    request_id = client_request_id.strip()
    if not 8 <= len(request_id) <= 64 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        for character in request_id
    ):
        raise HTTPException(status_code=422, detail="invalid client request ID")
    try:
        image_data = await image.read(MAX_IMAGE_INPUT_BYTES + 1)
    finally:
        await image.close()
    if not image_data:
        raise HTTPException(status_code=422, detail="image file is empty")
    if len(image_data) > MAX_IMAGE_INPUT_BYTES:
        raise HTTPException(status_code=413, detail="image file exceeds the 10 MB limit")
    return await runtime_manager.send_image(
        record,
        conversation_id,
        request_id,
        image_data,
    )


@app.post(
    "/api/accounts/{account_id}/conversations/{conversation_id}/messages/{message_pk}/recall",
    response_model=RecallMessageResultPayload,
)
async def recall_conversation_message(
    account_id: str,
    conversation_id: str,
    message_pk: str,
) -> RecallMessageResultPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await runtime_manager.recall_message(record, conversation_id, message_pk)


@app.get(
    "/api/accounts/{account_id}/conversations/{conversation_id}/platform-blacklist",
    response_model=PlatformBlacklistPayload,
)
async def get_conversation_platform_blacklist(
    account_id: str,
    conversation_id: str,
) -> PlatformBlacklistPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await runtime_manager.get_platform_blacklist(record, conversation_id)


@app.put(
    "/api/accounts/{account_id}/conversations/{conversation_id}/platform-blacklist",
    response_model=PlatformBlacklistPayload,
)
async def set_conversation_platform_blacklist(
    account_id: str,
    conversation_id: str,
    payload: PlatformBlacklistUpdatePayload,
) -> PlatformBlacklistPayload:
    record = await store.get_account(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    return await runtime_manager.set_platform_blacklist(record, conversation_id, payload.blocked)


class _AdminStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


_configured_admin_dist = os.getenv("XIANYU_ADMIN_DIST_DIR", "").strip()
_admin_dist = (
    Path(_configured_admin_dist).expanduser().resolve()
    if _configured_admin_dist
    else resource_path("apps", "admin", "dist")
)
if (_admin_dist / "index.html").is_file():
    app.mount(
        "/",
        _AdminStaticFiles(directory=str(_admin_dist), html=True),
        name="admin",
    )
