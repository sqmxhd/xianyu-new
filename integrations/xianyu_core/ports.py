"""Ports implemented by the Xianyu protocol adapter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from .models import (
    AccountConfig,
    ChatMessageEvent,
    ConnectionState,
    ConversationPage,
    MessagePage,
    PlatformBlacklistResult,
    SendMessageResult,
    InteractiveVerification,
)

MessageHandler = Callable[[ChatMessageEvent], Awaitable[None]]
StateHandler = Callable[[str, ConnectionState, str | None], Awaitable[None]]
CookieHandler = Callable[[str, str, str], Awaitable[None]]
TokenHandler = Callable[[str, str, int], Awaitable[None]]
VerificationHandler = Callable[[InteractiveVerification], Awaitable[None]]


class XianyuCoreClient(Protocol):
    """Protocol boundary between business services and XianyuApis.

    Business modules should depend on this interface, not on upstream files in
    ``third_party/XianYuApis``. The concrete implementation will be responsible
    for loading upstream helpers, injecting per-account SOCKS5h proxy settings,
    and normalizing raw messages into ``ChatMessageEvent``.
    """

    async def start_account(
        self,
        account: AccountConfig,
        on_message: MessageHandler,
        on_state: StateHandler | None = None,
        on_cookie: CookieHandler | None = None,
        on_im_token: TokenHandler | None = None,
        on_verification: VerificationHandler | None = None,
    ) -> None:
        """Start one managed account session."""

    async def stop_account(self, account_id: str) -> None:
        """Stop one managed account session."""

    async def send_text(
        self,
        account_id: str,
        conversation_id: str,
        receiver_user_id: str,
        text: str,
    ) -> SendMessageResult:
        """Send one text message through the account's active WS session."""

    async def send_image(
        self,
        account_id: str,
        conversation_id: str,
        receiver_user_id: str,
        image_data: bytes,
    ) -> SendMessageResult:
        """Upload and send one image through the account's active session."""

    async def recall_message(
        self,
        account_id: str,
        conversation_id: str,
        message_id: str,
    ) -> SendMessageResult:
        """Recall one acknowledged outbound message through the active session."""

    async def get_platform_blacklist(
        self,
        account_id: str,
        conversation_id: str,
    ) -> PlatformBlacklistResult:
        """Read the official Xianyu blacklist state for one conversation."""

    async def set_platform_blacklist(
        self,
        account_id: str,
        conversation_id: str,
        blocked: bool,
    ) -> PlatformBlacklistResult:
        """Change the official Xianyu blacklist state for one conversation."""

    async def refresh_token(self, account_id: str) -> None:
        """Refresh token/cookie state for one account using its configured proxy."""

    async def list_conversations(
        self, account_id: str, cursor: int | None = None, limit: int = 20
    ) -> ConversationPage:
        """Load a cursor page of conversations from the active IM session."""

    async def list_messages(
        self,
        account_id: str,
        conversation_id: str,
        cursor: int | None = None,
        limit: int = 20,
    ) -> MessagePage:
        """Load a cursor page of messages from the active IM session."""

    async def replace_cookie(self, account_id: str, cookie: str) -> bool:
        """Replace credentials for a running account without reconnecting its WebSocket."""

    def is_account_online(self, account_id: str) -> bool:
        """Return whether the account currently has an initialized WebSocket."""
