"""Normalization helpers for peer display names from Xianyu message metadata."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Any


_NOTICE_TITLES = {
    "你有一条新消息",
    "你有新的消息",
    "您有一条新消息",
    "发来一条新消息",
    "闲鱼新消息",
    "闲鱼消息",
    "交易消息",
    "系统消息",
    "快给ta一个评价吧~",
    "我完成了评价",
    "卖家人不错?送ta闲鱼小红花",
    "可以送ta闲鱼小红花吗~",
    "买家已拍下,待付款",
    "等待您发货",
    "等待你发货",
    "我发起了退款申请",
    "我将「退货退款」修改为「退款」",
    "闲鱼游戏交易安全提醒",
}


def normalize_peer_name(
    value: object,
    *,
    peer_user_id: str | None = None,
) -> str | None:
    """Return a usable nickname, rejecting protocol and transaction notices."""

    if value is None:
        return None
    name = str(value).strip()
    if not name:
        return None
    comparable = unicodedata.normalize("NFKC", name).strip().casefold()
    if comparable in _NOTICE_TITLES:
        return None
    if peer_user_id and comparable == str(peer_user_id).strip().casefold():
        return None
    return name


def extract_peer_name(
    metadata: Mapping[str, Any],
    *,
    peer_user_id: str | None = None,
) -> str | None:
    """Choose the first valid nickname from Xianyu message metadata."""

    for key in ("senderNick", "reminderTitle"):
        candidate = normalize_peer_name(metadata.get(key), peer_user_id=peer_user_id)
        if candidate:
            return candidate
    return None


def merge_peer_name(
    current: object,
    candidate: object,
    *,
    peer_user_id: str | None = None,
) -> str | None:
    """Prefer a valid candidate without degrading an existing valid nickname."""

    normalized_candidate = normalize_peer_name(candidate, peer_user_id=peer_user_id)
    if normalized_candidate:
        return normalized_candidate
    return normalize_peer_name(current, peer_user_id=peer_user_id)
