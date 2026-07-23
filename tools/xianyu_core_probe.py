#!/usr/bin/env python3
"""Manual phase-1 probe for one Xianyu account.

Examples:

    export XIANYU_COOKIE='unb=...; _m_h5_tk=...'
    python tools/xianyu_core_probe.py listen --account-id test --cookie-env XIANYU_COOKIE

    python tools/xianyu_core_probe.py send-text \\
      --account-id test \\
      --cookie-env XIANYU_COOKIE \\
      --proxy-url socks5h://127.0.0.1:1080 \\
      --conversation-id 123456789 \\
      --receiver-id 987654321 \\
      --text 'hello'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integrations.xianyu_core.client import XianyuCoreRuntime
from integrations.xianyu_core.models import AccountConfig, ChatMessageEvent, ConnectionState, ProxyConfig


def _parse_proxy_url(proxy_url: str | None) -> ProxyConfig:
    if not proxy_url:
        return ProxyConfig(enabled=False)

    from urllib.parse import urlparse

    parsed = urlparse(proxy_url)
    if parsed.scheme not in {"socks5", "socks5h"}:
        raise SystemExit("--proxy-url only supports socks5:// or socks5h://")
    if not parsed.hostname or not parsed.port:
        raise SystemExit("--proxy-url must include host and port")

    return ProxyConfig(
        enabled=True,
        scheme=parsed.scheme,
        host=parsed.hostname,
        port=parsed.port,
        username=parsed.username,
        password=parsed.password,
    )


def _get_cookie(args: argparse.Namespace) -> str:
    if args.cookie:
        return args.cookie
    if args.cookie_env:
        value = os.getenv(args.cookie_env)
        if value:
            return value
        raise SystemExit(f"environment variable is empty: {args.cookie_env}")
    raise SystemExit("provide --cookie or --cookie-env")


def _build_account(args: argparse.Namespace) -> AccountConfig:
    return AccountConfig(
        account_id=args.account_id,
        cookie=_get_cookie(args),
        nickname=args.nickname,
        proxy=_parse_proxy_url(args.proxy_url),
    )


async def _print_message(event: ChatMessageEvent) -> None:
    print(
        json.dumps(
            {
                "event": "message",
                "account_id": event.account_id,
                "conversation_id": event.conversation_id,
                "message_id": event.message_id,
                "peer_user_id": event.peer_user_id,
                "peer_name": event.peer_name,
                "direction": event.direction,
                "message_type": event.message_type,
                "content": event.content,
                "item_id": event.item_id,
                "created_at_ms": event.created_at_ms,
            },
            ensure_ascii=False,
        )
    )


async def _print_state(account_id: str, state: ConnectionState, message: str | None) -> None:
    print(
        json.dumps(
            {
                "event": "state",
                "account_id": account_id,
                "state": state,
                "message": message,
            },
            ensure_ascii=False,
        )
    )


async def cmd_listen(args: argparse.Namespace) -> None:
    runtime = XianyuCoreRuntime()
    account = _build_account(args)
    await runtime.start_account(account, on_message=_print_message, on_state=_print_state)

    try:
        if args.duration:
            await asyncio.sleep(args.duration)
        else:
            await runtime.wait_account(account.account_id)
    finally:
        await runtime.stop_account(account.account_id)


async def cmd_send_text(args: argparse.Namespace) -> None:
    runtime = XianyuCoreRuntime()
    account = _build_account(args)
    online = asyncio.Event()

    async def on_state(account_id: str, state: ConnectionState, message: str | None) -> None:
        await _print_state(account_id, state, message)
        if state == ConnectionState.ONLINE:
            online.set()

    await runtime.start_account(account, on_message=_print_message, on_state=on_state)

    try:
        await asyncio.wait_for(online.wait(), timeout=args.online_timeout)
        result = await runtime.send_text(
            account_id=account.account_id,
            conversation_id=args.conversation_id,
            receiver_user_id=args.receiver_id,
            text=args.text,
        )
        print(
            json.dumps(
                {
                    "event": "send_result",
                    "success": result.success,
                    "account_id": result.account_id,
                    "conversation_id": result.conversation_id,
                    "message_id": result.message_id,
                    "error": result.error,
                },
                ensure_ascii=False,
            )
        )
        if args.after_send_wait:
            await asyncio.sleep(args.after_send_wait)
    finally:
        await runtime.stop_account(account.account_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xianyu core phase-1 probe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--account-id", required=True)
        subparser.add_argument("--nickname")
        subparser.add_argument("--cookie", help="raw cookie string; prefer --cookie-env for shell history safety")
        subparser.add_argument("--cookie-env", help="environment variable containing the raw cookie string")
        subparser.add_argument("--proxy-url", help="socks5h://user:pass@host:port")

    listen = subparsers.add_parser("listen", help="connect and print inbound messages")
    add_common(listen)
    listen.add_argument("--duration", type=int, default=0, help="seconds to run; 0 means until disconnected/Ctrl-C")
    listen.set_defaults(func=cmd_listen)

    send_text = subparsers.add_parser("send-text", help="connect, send one text message, then stop")
    add_common(send_text)
    send_text.add_argument("--conversation-id", required=True)
    send_text.add_argument("--receiver-id", required=True)
    send_text.add_argument("--text", required=True)
    send_text.add_argument("--online-timeout", type=int, default=30)
    send_text.add_argument("--after-send-wait", type=int, default=3)
    send_text.set_defaults(func=cmd_send_text)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
