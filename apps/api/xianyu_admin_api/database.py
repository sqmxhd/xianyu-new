"""SQLAlchemy database bootstrap."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import DateTime as SQLAlchemyDateTime
from sqlalchemy import event, inspect, text
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime
from sqlalchemy.schema import CreateColumn
from sqlalchemy import create_engine
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from .settings import settings


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[datetime]):
    """Store UTC in timezone-less databases and restore UTC on every read."""

    impl = SQLAlchemyDateTime
    cache_ok = True

    def __init__(self, *, precision: int | None = None) -> None:
        if precision is not None and precision not in range(7):
            raise ValueError("datetime precision must be between 0 and 6")
        self.precision = precision
        super().__init__()

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "mysql" and self.precision is not None:
            return dialect.type_descriptor(MySQLDateTime(fsp=self.precision))
        return dialect.type_descriptor(
            SQLAlchemyDateTime(timezone=dialect.name == "postgresql")
        )

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        normalized = (
            value.replace(tzinfo=UTC)
            if value.tzinfo is None
            else value.astimezone(UTC)
        )
        if dialect.name == "postgresql":
            return normalized
        return normalized.replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _set_mysql_session_timezone(dbapi_connection: Any, _: Any) -> None:
    """Keep MySQL date functions and future TIMESTAMP columns on UTC."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET SESSION time_zone = '+00:00'")
    finally:
        cursor.close()


def _sqlite_path_from_url(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw_path = database_url[len(prefix) :]
    if raw_path == ":memory:":
        return None
    return Path(raw_path)


def build_engine(database_url: str) -> Engine:
    connect_args = {}
    engine_options: dict[str, object] = {}
    sqlite_path = _sqlite_path_from_url(database_url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False
    elif database_url.startswith("mysql"):
        connect_args.update(
            {
                "connect_timeout": 5,
                "read_timeout": 10,
                "write_timeout": 10,
            }
        )
        engine_options.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 5,
                "pool_recycle": 900,
            }
        )

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=True,
        **engine_options,
    )
    if engine.dialect.name == "mysql":
        event.listen(engine, "connect", _set_mysql_session_timezone)
    return engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_database() -> None:
    from . import orm  # noqa: F401

    if engine.dialect.name == "mysql":
        with engine.connect() as lock_connection:
            acquired = lock_connection.execute(
                text("SELECT GET_LOCK('xianyu_admin_schema_init', 30)")
            ).scalar()
            if acquired != 1:
                raise RuntimeError("timed out waiting for database schema initialization lock")
            try:
                _initialize_schema()
            finally:
                lock_connection.execute(
                    text("SELECT RELEASE_LOCK('xianyu_admin_schema_init')")
                )
        return
    _initialize_schema()


def _initialize_schema() -> None:
    Base.metadata.create_all(bind=engine)
    added_columns = _apply_lightweight_migrations(engine)
    _migrate_chatwoot_platform_config(engine)
    _ensure_chatwoot_platform_indexes(engine)
    _normalize_account_sort_order(engine)
    _migrate_auto_reply_ownership(engine)
    _migrate_auto_reply_v2(engine)
    _ensure_message_time_precision(engine)
    _ensure_message_identity_indexes(engine)
    _ensure_message_time_indexes(engine)
    _ensure_conversation_indexes(engine)
    _ensure_product_publish_indexes(engine)
    _ensure_product_management_indexes(engine)
    _backfill_product_publish_task_assets(engine)
    _backfill_product_published_at(engine)
    _backfill_product_want_metrics(
        engine,
        columns_added=bool(
            {
                ("xianyu_product_items", "want_count"),
                ("xianyu_product_items", "want_text"),
            }
            & added_columns
        ),
    )
    _ensure_background_task_indexes(engine)
    _ensure_order_indexes(engine)
    _ensure_auto_reply_indexes(engine)
    _migrate_legacy_account_proxies(engine)
    _ensure_proxy_assignment_index(engine)
    _drop_legacy_account_name(engine)
    _drop_legacy_notification_tables(engine)
    _normalize_migrated_defaults(engine)
    _normalize_cookie_renewal_metadata(engine)
    _normalize_order_trade_roles(engine)
    _normalize_order_sync_metadata(engine)
    _backfill_headinfo_order_metadata(engine)


def _migrate_chatwoot_platform_config(target_engine: Engine) -> None:
    """Collapse the former account bindings into one platform configuration."""

    tables = set(inspect(target_engine).get_table_names())
    required = {
        "xianyu_accounts",
        "xianyu_chatwoot_config",
        "xianyu_chatwoot_bindings",
    }
    if not required.issubset(tables):
        return

    old_columns = {
        column["name"]
        for column in inspect(target_engine).get_columns("xianyu_chatwoot_bindings")
    }
    client_hmac_expression = (
        "client_hmac_token_encrypted"
        if "client_hmac_token_encrypted" in old_columns
        else "NULL"
    )
    with target_engine.begin() as connection:
        selected = connection.execute(
            text(
                "SELECT binding_id FROM xianyu_chatwoot_bindings "
                "ORDER BY enabled DESC, updated_at DESC, created_at DESC LIMIT 1"
            )
        ).scalar()
        binding_count = int(
            connection.execute(
                text("SELECT COUNT(*) FROM xianyu_chatwoot_bindings")
            ).scalar()
            or 0
        )
        config_exists = connection.execute(
            text(
                "SELECT config_id FROM xianyu_chatwoot_config "
                "WHERE config_id = 'default'"
            )
        ).scalar()
        if selected and not config_exists:
            connection.execute(
                text(
                    "INSERT INTO xianyu_chatwoot_config "
                    "(config_id, enabled, base_url, inbox_identifier, "
                    "chatwoot_account_id, webhook_secret_encrypted, "
                    "client_hmac_token_encrypted, api_access_token_encrypted, "
                    "status, last_error, last_webhook_at, last_push_at, "
                    "created_at, updated_at) "
                    "SELECT 'default', enabled, base_url, inbox_identifier, "
                    "chatwoot_account_id, webhook_secret_encrypted, "
                    f"{client_hmac_expression}, api_access_token_encrypted, "
                    "status, last_error, last_webhook_at, last_push_at, "
                    "created_at, updated_at FROM xianyu_chatwoot_bindings "
                    "WHERE binding_id = :binding_id"
                ),
                {"binding_id": selected},
            )
        connection.execute(
            text(
                "UPDATE xianyu_accounts SET chat_enabled = :enabled "
                "WHERE account_id IN ("
                "SELECT account_id FROM xianyu_chatwoot_bindings WHERE enabled = :enabled"
                ")"
            ),
            {"enabled": True},
        )
        if binding_count > 1:
            for table_name in (
                "xianyu_chatwoot_messages",
                "xianyu_chatwoot_conversations",
                "xianyu_chatwoot_contacts",
            ):
                if table_name in tables:
                    connection.execute(text(f"DELETE FROM {table_name}"))
        if "xianyu_chatwoot_webhook_deliveries" in tables:
            connection.execute(text("DROP TABLE xianyu_chatwoot_webhook_deliveries"))
        connection.execute(text("DROP TABLE xianyu_chatwoot_bindings"))


def _ensure_chatwoot_platform_indexes(target_engine: Engine) -> None:
    table_name = "xianyu_chatwoot_conversations"
    if (
        target_engine.dialect.name != "mysql"
        or table_name not in inspect(target_engine).get_table_names()
    ):
        return
    constraint_name = "uq_xianyu_chatwoot_conversation_remote"
    constraints = {
        item["name"]: item
        for item in inspect(target_engine).get_unique_constraints(table_name)
        if item.get("name")
    }
    existing = constraints.get(constraint_name)
    if existing and existing.get("column_names") == ["chatwoot_conversation_id"]:
        return
    with target_engine.begin() as connection:
        duplicate = connection.execute(
            text(
                "SELECT chatwoot_conversation_id FROM xianyu_chatwoot_conversations "
                "GROUP BY chatwoot_conversation_id HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).scalar()
        if duplicate:
            connection.execute(text("DELETE FROM xianyu_chatwoot_messages"))
            connection.execute(text("DELETE FROM xianyu_chatwoot_conversations"))
            connection.execute(text("DELETE FROM xianyu_chatwoot_contacts"))
        if existing:
            connection.execute(
                text(
                    "ALTER TABLE xianyu_chatwoot_conversations "
                    "DROP INDEX uq_xianyu_chatwoot_conversation_remote"
                )
            )
        connection.execute(
            text(
                "ALTER TABLE xianyu_chatwoot_conversations "
                "ADD UNIQUE INDEX uq_xianyu_chatwoot_conversation_remote "
                "(chatwoot_conversation_id)"
            )
        )


def _apply_lightweight_migrations(target_engine: Engine) -> set[tuple[str, str]]:
    """Add nullable columns introduced after the first local schema.

    This is intentionally small and conservative. It does not replace a real
    Alembic migration chain, but it keeps existing dev SQLite/MySQL databases
    usable while this admin backend is still being built in phases.
    """

    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    added_columns: set[tuple[str, str]] = set()
    with target_engine.begin() as connection:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                if table_name == "xianyu_messages" and column.name == "created_at_ms":
                    ddl = "created_at_ms BIGINT NULL"
                else:
                    ddl = str(CreateColumn(column).compile(dialect=target_engine.dialect))
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
                added_columns.add((table_name, column.name))
    return added_columns


def _normalize_account_sort_order(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_accounts" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("xianyu_accounts")}
    if not {"account_id", "sort_order", "created_at"}.issubset(columns):
        return
    with target_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT account_id, sort_order, created_at FROM xianyu_accounts "
                "ORDER BY CASE WHEN sort_order > 0 THEN 0 ELSE 1 END, "
                "sort_order, created_at, account_id"
            )
        ).mappings().all()
        sort_orders = [int(row["sort_order"] or 0) for row in rows]
        if all(value > 0 for value in sort_orders) and len(sort_orders) == len(set(sort_orders)):
            return
        for position, row in enumerate(rows, start=1):
            connection.execute(
                text(
                    "UPDATE xianyu_accounts SET sort_order = :sort_order "
                    "WHERE account_id = :account_id"
                ),
                {"sort_order": position * 100, "account_id": row["account_id"]},
            )


def _migrate_auto_reply_ownership(target_engine: Engine) -> None:
    """Backfill account automation owners and copy legacy account reply data."""

    tables = set(inspect(target_engine).get_table_names())
    required = {
        "xianyu_users",
        "xianyu_accounts",
        "xianyu_auto_reply_settings",
        "xianyu_auto_reply_rules",
        "xianyu_user_auto_reply_settings",
        "xianyu_user_auto_reply_rules",
    }
    if not required.issubset(tables):
        return

    with target_engine.begin() as connection:
        fallback_user_id = connection.execute(
            text(
                "SELECT user_id FROM xianyu_users WHERE enabled = :enabled "
                "ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, created_at LIMIT 1"
            ),
            {"enabled": True},
        ).scalar()
        if not fallback_user_id:
            return

        connection.execute(
            text(
                "UPDATE xianyu_accounts SET automation_owner_user_id = :user_id "
                "WHERE automation_owner_user_id IS NULL"
            ),
            {"user_id": fallback_user_id},
        )
        accounts = connection.execute(
            text(
                "SELECT account_id, automation_owner_user_id FROM xianyu_accounts "
                "WHERE automation_owner_user_id IS NOT NULL ORDER BY created_at"
            )
        ).mappings().all()

    _copy_legacy_auto_reply_data(target_engine, accounts)


def _migrate_auto_reply_v2(target_engine: Engine) -> None:
    """Move effective switches, provider credentials, and defaults to v2 scopes."""

    from sqlalchemy.orm import Session

    from .orm import (
        AIProviderSettingORM,
        AccountORM,
        AutoReplySettingORM,
        UserAutoReplyRuleORM,
        UserAutoReplySettingORM,
    )
    from .sensitive import encrypt_sensitive

    def load_ids(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return [str(item) for item in value if item] if isinstance(value, list) else []

    with Session(target_engine) as session:
        if session.get(AIProviderSettingORM, "default") is not None:
            return

        now = datetime.now(UTC)
        user_settings = session.query(UserAutoReplySettingORM).all()
        provider_candidates: list[tuple[str, str, str]] = []
        for setting in user_settings:
            if setting.ai_base_url and setting.ai_model and setting.ai_api_key:
                candidate = (setting.ai_base_url, setting.ai_model, setting.ai_api_key)
                if candidate not in provider_candidates:
                    provider_candidates.append(candidate)
        selected_provider = provider_candidates[0] if len(provider_candidates) == 1 else None
        session.add(
            AIProviderSettingORM(
                setting_id="default",
                base_url=selected_provider[0] if selected_provider else None,
                model=selected_provider[1] if selected_provider else None,
                api_key_encrypted=(
                    encrypt_sensitive(selected_provider[2]) if selected_provider else None
                ),
                created_at=now,
                updated_at=now,
            )
        )

        settings_by_user = {row.user_id: row for row in user_settings}
        for account in session.query(AccountORM).all():
            account_setting = session.get(AutoReplySettingORM, account.account_id)
            if account_setting is None:
                account_setting = AutoReplySettingORM(
                    account_id=account.account_id,
                    enabled=False,
                    default_reply_enabled=False,
                    default_reply_text="",
                    ai_enabled=False,
                    ai_context_messages=10,
                    created_at=now,
                    updated_at=now,
                )
                session.add(account_setting)
            owner_setting = settings_by_user.get(account.automation_owner_user_id or "")
            if owner_setting is not None:
                account_setting.enabled = bool(
                    owner_setting.enabled
                    and account.account_id not in load_ids(owner_setting.excluded_account_ids)
                )
                account_setting.updated_at = now

        for setting in user_settings:
            rules = (
                session.query(UserAutoReplyRuleORM)
                .filter(UserAutoReplyRuleORM.user_id == setting.user_id)
                .order_by(UserAutoReplyRuleORM.created_at)
                .all()
            )
            if setting.match_strategy == "first_created":
                for index, rule in enumerate(rules, start=1):
                    rule.priority = index * 10
            for rule in rules:
                rule.trigger_type = rule.trigger_type or "keyword"
                rule.continue_matching = setting.match_strategy == "all_join"
                rule.cooldown_seconds = max(
                    int(rule.cooldown_seconds or 0), int(setting.cooldown_seconds or 0)
                )
                rule.context_message_count = max(
                    1, min(int(setting.ai_context_messages or 10), 50)
                )
                if not rule.context_fields:
                    rule.context_fields = json.dumps(
                        [
                            "account.name", "sender.id", "sender.name", "message.text",
                            "message.time", "item.id", "item.title", "item.price",
                            "order.id", "order.status", "order.price", "conversation.id",
                        ],
                        ensure_ascii=False,
                    )
                rule.ai_system_prompt = rule.ai_system_prompt or setting.ai_system_prompt or ""
                rule.ai_temperature = setting.ai_temperature or 0.4

            fallback_priority = max([rule.priority for rule in rules] + [100]) + 100
            can_migrate_ai = bool(
                setting.ai_enabled
                and selected_provider
                and (setting.ai_base_url, setting.ai_model, setting.ai_api_key)
                == selected_provider
            )
            if can_migrate_ai:
                session.add(
                    UserAutoReplyRuleORM(
                        rule_id=uuid.uuid4().hex,
                        user_id=setting.user_id,
                        account_ids=None,
                        platform=None,
                        enabled=True,
                        group_name="迁移配置",
                        keyword="",
                        trigger_type="fallback",
                        match_mode="contains",
                        case_sensitive=False,
                        message_type=None,
                        sender_user_id=None,
                        conversation_id=None,
                        item_id=None,
                        cooldown_seconds=int(setting.cooldown_seconds or 0),
                        action_type="ai",
                        reply_text="",
                        priority=fallback_priority,
                        continue_matching=False,
                        context_message_count=max(1, min(setting.ai_context_messages or 10, 50)),
                        context_fields=json.dumps(
                            [
                                "account.name", "sender.id", "sender.name", "message.text",
                                "message.time", "item.id", "item.title", "item.price",
                                "order.id", "order.status", "order.price", "conversation.id",
                            ],
                            ensure_ascii=False,
                        ),
                        ai_system_prompt=setting.ai_system_prompt or "",
                        ai_temperature=setting.ai_temperature or 0.4,
                        created_at=now,
                        updated_at=now,
                    )
                )
                fallback_priority += 100
            if setting.default_reply_enabled and setting.default_reply_text.strip():
                session.add(
                    UserAutoReplyRuleORM(
                        rule_id=uuid.uuid4().hex,
                        user_id=setting.user_id,
                        account_ids=None,
                        platform=None,
                        enabled=True,
                        group_name="迁移配置",
                        keyword="",
                        trigger_type="fallback",
                        match_mode="contains",
                        case_sensitive=False,
                        message_type=None,
                        sender_user_id=None,
                        conversation_id=None,
                        item_id=None,
                        cooldown_seconds=int(setting.cooldown_seconds or 0),
                        action_type="template",
                        reply_text=setting.default_reply_text,
                        priority=fallback_priority,
                        continue_matching=False,
                        context_message_count=10,
                        context_fields=None,
                        ai_system_prompt="",
                        ai_temperature=0.4,
                        created_at=now,
                        updated_at=now,
                    )
                )
            if selected_provider and setting.ai_api_key == selected_provider[2]:
                setting.ai_api_key = None
            setting.enabled = False
            setting.excluded_account_ids = None
            setting.updated_at = now

        session.commit()


def _copy_legacy_auto_reply_data(
    target_engine: Engine,
    accounts: list[dict[str, Any]],
) -> None:
    tables = set(inspect(target_engine).get_table_names())
    with target_engine.begin() as connection:
        initialized_users: set[str] = set()
        for account in accounts:
            user_id = str(account["automation_owner_user_id"])
            account_id = str(account["account_id"])
            if user_id not in initialized_users:
                exists = connection.execute(
                    text(
                        "SELECT user_id FROM xianyu_user_auto_reply_settings "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": user_id},
                ).scalar()
                if not exists:
                    legacy = connection.execute(
                        text(
                            "SELECT * FROM xianyu_auto_reply_settings "
                            "WHERE account_id = :account_id"
                        ),
                        {"account_id": account_id},
                    ).mappings().first()
                    now = datetime.now(UTC)
                    values = {
                        "user_id": user_id,
                        "enabled": bool(legacy["enabled"]) if legacy else False,
                        "default_reply_enabled": bool(legacy["default_reply_enabled"]) if legacy else False,
                        "default_reply_text": str(legacy["default_reply_text"] or "") if legacy else "",
                        "cooldown_seconds": int(legacy["cooldown_seconds"] or 0) if legacy else 0,
                        "match_strategy": str(legacy["match_strategy"] or "priority_first") if legacy else "priority_first",
                        "allowlist": legacy["allowlist_conversation_ids"] if legacy else None,
                        "blocklist": legacy["blocklist_conversation_ids"] if legacy else None,
                        "ai_enabled": bool(legacy["ai_enabled"]) if legacy else False,
                        "ai_base_url": legacy["ai_base_url"] if legacy else None,
                        "ai_api_key": legacy["ai_api_key"] if legacy else None,
                        "ai_model": legacy["ai_model"] if legacy else None,
                        "ai_system_prompt": legacy["ai_system_prompt"] if legacy else None,
                        "ai_context_messages": int(legacy["ai_context_messages"] or 10) if legacy else 10,
                        "created_at": legacy["created_at"] if legacy else now,
                        "updated_at": legacy["updated_at"] if legacy else now,
                    }
                    connection.execute(
                        text(
                            "INSERT INTO xianyu_user_auto_reply_settings "
                            "(user_id, enabled, excluded_account_ids, default_reply_enabled, "
                            "default_reply_text, cooldown_seconds, match_strategy, "
                            "allowlist_conversation_ids, blocklist_conversation_ids, ai_enabled, "
                            "ai_base_url, ai_api_key, ai_model, ai_system_prompt, ai_context_messages, "
                            "ai_include_images, ai_temperature, created_at, updated_at) VALUES "
                            "(:user_id, :enabled, NULL, :default_reply_enabled, :default_reply_text, "
                            ":cooldown_seconds, :match_strategy, :allowlist, :blocklist, :ai_enabled, "
                            ":ai_base_url, :ai_api_key, :ai_model, :ai_system_prompt, "
                            ":ai_context_messages, 0, 0.4, :created_at, :updated_at)"
                        ),
                        values,
                    )
                initialized_users.add(user_id)

            legacy_rules = connection.execute(
                text(
                    "SELECT * FROM xianyu_auto_reply_rules WHERE account_id = :account_id"
                ),
                {"account_id": account_id},
            ).mappings().all()
            for legacy_rule in legacy_rules:
                if connection.execute(
                    text(
                        "SELECT rule_id FROM xianyu_user_auto_reply_rules "
                        "WHERE rule_id = :rule_id"
                    ),
                    {"rule_id": legacy_rule["rule_id"]},
                ).scalar():
                    continue
                connection.execute(
                    text(
                        "INSERT INTO xianyu_user_auto_reply_rules "
                        "(rule_id, user_id, account_ids, platform, enabled, group_name, keyword, "
                        "match_mode, case_sensitive, message_type, sender_user_id, conversation_id, "
                        "item_id, cooldown_seconds, action_type, reply_text, priority, created_at, updated_at) "
                        "VALUES (:rule_id, :user_id, :account_ids, 'xianyu', :enabled, :group_name, "
                        ":keyword, :match_mode, :case_sensitive, 'text', NULL, :conversation_id, "
                        ":item_id, :cooldown_seconds, 'template', :reply_text, :priority, :created_at, :updated_at)"
                    ),
                    {
                        **dict(legacy_rule),
                        "user_id": user_id,
                        "account_ids": json.dumps([account_id], ensure_ascii=False),
                    },
                )

        if "xianyu_auto_reply_logs" in tables:
            connection.execute(
                text(
                    "UPDATE xianyu_auto_reply_logs SET user_id = "
                    "(SELECT automation_owner_user_id FROM xianyu_accounts "
                    "WHERE xianyu_accounts.account_id = xianyu_auto_reply_logs.account_id) "
                    "WHERE user_id IS NULL"
                )
            )


def _ensure_auto_reply_indexes(target_engine: Engine) -> None:
    table = Base.metadata.tables.get("xianyu_auto_reply_logs")
    if table is None or "xianyu_auto_reply_logs" not in inspect(target_engine).get_table_names():
        return
    for index in table.indexes:
        if index.name == "uq_xianyu_auto_reply_logs_inbound":
            index.create(bind=target_engine, checkfirst=True)


def _ensure_message_identity_indexes(target_engine: Engine) -> None:
    """Install message idempotency indexes on databases created before they existed."""

    table = Base.metadata.tables.get("xianyu_messages")
    if table is None or "xianyu_messages" not in inspect(target_engine).get_table_names():
        return
    for index in table.indexes:
        if index.name in {
            "uq_xianyu_messages_platform_id",
            "uq_xianyu_messages_dedupe_key",
            "uq_xianyu_messages_client_request",
        }:
            index.create(bind=target_engine, checkfirst=True)


def _coerce_utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _datetime_epoch_milliseconds(value: object) -> int | None:
    parsed = _coerce_utc_datetime(value)
    return int(parsed.timestamp() * 1000) if parsed is not None else None


def _ensure_message_time_precision(target_engine: Engine) -> None:
    """Backfill canonical millisecond timestamps and retain fractional datetimes."""

    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    if "xianyu_messages" not in existing_tables:
        return
    message_columns = {
        column["name"]: column for column in inspector.get_columns("xianyu_messages")
    }
    required_columns = {
        "message_pk",
        "created_at_ms",
        "received_at_ms",
        "created_at",
        "received_at",
    }
    if not required_columns.issubset(message_columns):
        return

    with target_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT message_pk, created_at_ms, received_at_ms, created_at, received_at "
                "FROM xianyu_messages WHERE created_at_ms IS NULL "
                "OR (received_at IS NOT NULL AND received_at_ms IS NULL)"
            )
        ).mappings().all()
        for row in rows:
            created_at_ms = row["created_at_ms"] or _datetime_epoch_milliseconds(
                row["created_at"]
            )
            received_at_ms = row["received_at_ms"] or _datetime_epoch_milliseconds(
                row["received_at"]
            )
            if created_at_ms is None:
                created_at_ms = int(datetime.now(UTC).timestamp() * 1000)
            connection.execute(
                text(
                    "UPDATE xianyu_messages SET created_at_ms = :created_at_ms, "
                    "received_at_ms = :received_at_ms WHERE message_pk = :message_pk"
                ),
                {
                    "message_pk": row["message_pk"],
                    "created_at_ms": created_at_ms,
                    "received_at_ms": received_at_ms,
                },
            )

    if target_engine.dialect.name != "mysql":
        return

    message_columns = {
        column["name"]: column
        for column in inspect(target_engine).get_columns("xianyu_messages")
    }
    message_alterations: list[str] = []
    created_at_needs_backfill = False
    for column_name, nullable in (
        ("created_at", False),
        ("received_at", True),
        ("recalled_at", True),
    ):
        column = message_columns.get(column_name)
        if column is None:
            continue
        precision = getattr(column["type"], "fsp", None)
        if precision != 3:
            if column_name == "created_at":
                created_at_needs_backfill = True
            nullability = "NULL" if nullable else "NOT NULL"
            message_alterations.append(
                f"MODIFY COLUMN {column_name} DATETIME(3) {nullability}"
            )
    created_at_ms_column = message_columns.get("created_at_ms")
    if created_at_ms_column is not None and created_at_ms_column.get("nullable", True):
        message_alterations.append("MODIFY COLUMN created_at_ms BIGINT NOT NULL")

    conversation_columns: dict[str, dict[str, Any]] = {}
    conversation_alterations: list[str] = []
    last_message_at_needs_backfill = False
    if "xianyu_conversations" in existing_tables:
        conversation_columns = {
            column["name"]: column
            for column in inspect(target_engine).get_columns("xianyu_conversations")
        }
        for column_name in (
            "item_context_at",
            "last_message_at",
            "last_activity_at",
            "last_inbound_at",
            "last_outbound_at",
        ):
            column = conversation_columns.get(column_name)
            if column is not None and getattr(column["type"], "fsp", None) != 3:
                if column_name == "last_message_at":
                    last_message_at_needs_backfill = True
                conversation_alterations.append(
                    f"MODIFY COLUMN {column_name} DATETIME(3) NULL"
                )

    with target_engine.begin() as connection:
        if message_alterations:
            connection.execute(
                text("ALTER TABLE xianyu_messages " + ", ".join(message_alterations))
            )
        if conversation_alterations:
            connection.execute(
                text(
                    "ALTER TABLE xianyu_conversations "
                    + ", ".join(conversation_alterations)
                )
            )
        if created_at_needs_backfill:
            connection.execute(
                text(
                    "UPDATE xianyu_messages SET created_at = "
                    "FROM_UNIXTIME(created_at_ms / 1000.0)"
                )
            )
        if last_message_at_needs_backfill:
            connection.execute(
                text(
                    "UPDATE xianyu_conversations AS conversation "
                    "JOIN ("
                    "SELECT account_id, conversation_id, MAX(created_at_ms) AS created_at_ms "
                    "FROM xianyu_messages "
                    "WHERE direction <> 'outbound' OR send_success IS NOT FALSE "
                    "GROUP BY account_id, conversation_id"
                    ") AS latest ON latest.account_id = conversation.account_id "
                    "AND latest.conversation_id = conversation.conversation_id "
                    "SET conversation.last_message_at = FROM_UNIXTIME(latest.created_at_ms / 1000.0) "
                    "WHERE conversation.last_message_at IS NULL "
                    "OR conversation.last_message_at <= FROM_UNIXTIME(latest.created_at_ms / 1000.0)"
                )
            )


def _ensure_message_time_indexes(target_engine: Engine) -> None:
    table_name = "xianyu_messages"
    table = Base.metadata.tables.get(table_name)
    if table is None or table_name not in inspect(target_engine).get_table_names():
        return
    expected_names = {
        "ix_xianyu_messages_conversation_created",
        "ix_xianyu_messages_account_created",
    }
    existing_indexes = {
        item["name"]: item for item in inspect(target_engine).get_indexes(table_name)
    }
    for index in table.indexes:
        if index.name not in expected_names:
            continue
        expected_columns = [column.name for column in index.columns]
        existing = existing_indexes.get(index.name)
        if existing is not None and existing.get("column_names") != expected_columns:
            index.drop(bind=target_engine, checkfirst=True)
        index.create(bind=target_engine, checkfirst=True)


def _ensure_conversation_indexes(target_engine: Engine) -> None:
    for table_name in ("xianyu_accounts", "xianyu_conversations"):
        table = Base.metadata.tables.get(table_name)
        if table is None or table_name not in inspect(target_engine).get_table_names():
            continue
        for index in table.indexes:
            if index.name == "uq_xianyu_accounts_proxy_id":
                continue
            index.create(bind=target_engine, checkfirst=True)


def _ensure_product_publish_indexes(target_engine: Engine) -> None:
    table_name = "xianyu_product_publish_tasks"
    table = Base.metadata.tables.get(table_name)
    if table is None or table_name not in inspect(target_engine).get_table_names():
        return
    existing_indexes = {item["name"]: item for item in inspect(target_engine).get_indexes(table_name)}
    idempotency = next(
        (index for index in table.indexes if index.name == "uq_xianyu_product_publish_tasks_idempotency"),
        None,
    )
    existing_idempotency = existing_indexes.get("uq_xianyu_product_publish_tasks_idempotency")
    if (
        idempotency is not None
        and existing_idempotency is not None
        and existing_idempotency.get("column_names") != ["account_id", "idempotency_key"]
    ):
        idempotency.drop(bind=target_engine, checkfirst=True)
    for index in table.indexes:
        index.create(bind=target_engine, checkfirst=True)
    for related_table_name in (
        "xianyu_product_image_assets",
        "xianyu_product_publish_task_assets",
    ):
        related = Base.metadata.tables.get(related_table_name)
        if related is None or related_table_name not in inspect(target_engine).get_table_names():
            continue
        for index in related.indexes:
            index.create(bind=target_engine, checkfirst=True)


def _ensure_product_management_indexes(target_engine: Engine) -> None:
    table_name = "xianyu_product_items"
    table = Base.metadata.tables.get(table_name)
    if table is None or table_name not in inspect(target_engine).get_table_names():
        return
    for index in table.indexes:
        index.create(bind=target_engine, checkfirst=True)


def _backfill_product_published_at(target_engine: Engine) -> None:
    from .orm import ProductItemORM, ProductPublishTaskORM

    tables = set(inspect(target_engine).get_table_names())
    if not {"xianyu_product_items", "xianyu_product_publish_tasks"}.issubset(tables):
        return
    factory = sessionmaker(bind=target_engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        tasks = (
            session.query(
                ProductPublishTaskORM.account_id,
                ProductPublishTaskORM.item_id,
                ProductPublishTaskORM.finished_at,
            )
            .filter(
                ProductPublishTaskORM.item_id.is_not(None),
                ProductPublishTaskORM.finished_at.is_not(None),
            )
            .order_by(ProductPublishTaskORM.finished_at.asc())
            .all()
        )
        changed = False
        for account_id, item_id, finished_at in tasks:
            row = session.get(
                ProductItemORM,
                {"account_id": account_id, "item_id": item_id},
            )
            if row is None or row.published_at is not None:
                continue
            row.published_at = finished_at
            row.published_at_source = "publish_task"
            changed = True
        if changed:
            session.commit()


def _backfill_product_want_metrics(target_engine: Engine, *, columns_added: bool) -> None:
    if not columns_added:
        return

    from integrations.xianyu_core.product_operations import extract_product_want_metric

    from .orm import ProductItemORM

    if "xianyu_product_items" not in inspect(target_engine).get_table_names():
        return
    factory = sessionmaker(bind=target_engine, autoflush=False, expire_on_commit=False, future=True)
    with factory() as session:
        rows = session.query(ProductItemORM).filter(ProductItemORM.raw_data.is_not(None)).all()
        changed = False
        for row in rows:
            try:
                raw_data = json.loads(row.raw_data or "{}")
            except (TypeError, ValueError):
                continue
            if not isinstance(raw_data, dict):
                continue
            want_count, want_text = extract_product_want_metric(raw_data)
            if want_text is None:
                continue
            row.want_count = want_count
            row.want_text = want_text
            changed = True
        if changed:
            session.commit()


def _backfill_product_publish_task_assets(target_engine: Engine) -> None:
    from .orm import ProductImageAssetORM, ProductPublishTaskAssetORM, ProductPublishTaskORM

    tables = set(inspect(target_engine).get_table_names())
    if not {
        "xianyu_product_image_assets",
        "xianyu_product_publish_tasks",
        "xianyu_product_publish_task_assets",
    }.issubset(tables):
        return
    factory = sessionmaker(bind=target_engine, autoflush=False, expire_on_commit=False, future=True)
    now = datetime.now(UTC)
    with factory() as session:
        tasks = session.query(ProductPublishTaskORM).all()
        for task in tasks:
            try:
                snapshot = json.loads(task.snapshot or "{}")
            except (TypeError, ValueError):
                continue
            images = snapshot.get("images") if isinstance(snapshot, dict) else None
            if not isinstance(images, list):
                continue
            retention_days = 30 if task.status in {"pending", "running", "failed", "verification_required"} else 7
            retain_until = now + timedelta(days=retention_days)
            for ordinal, image_ref in enumerate(images):
                value = str(image_ref)
                if not value.startswith("asset:"):
                    continue
                asset_id = value.removeprefix("asset:")
                asset = session.get(ProductImageAssetORM, asset_id)
                if asset is None or asset.account_id != task.account_id:
                    continue
                key = {"task_id": task.task_id, "asset_id": asset_id}
                if session.get(ProductPublishTaskAssetORM, key) is None:
                    session.add(
                        ProductPublishTaskAssetORM(
                            task_id=task.task_id,
                            asset_id=asset_id,
                            ordinal=ordinal,
                            retain_until=retain_until,
                            created_at=task.created_at or now,
                        )
                    )
                asset.state = "retained"
                asset.last_referenced_at = asset.last_referenced_at or task.created_at or now
                asset.expires_at = max(asset.expires_at or retain_until, retain_until)
        session.commit()


def _ensure_background_task_indexes(target_engine: Engine) -> None:
    table_name = "xianyu_background_tasks"
    table = Base.metadata.tables.get(table_name)
    if table is None or table_name not in inspect(target_engine).get_table_names():
        return
    for index in table.indexes:
        index.create(bind=target_engine, checkfirst=True)


def _ensure_order_indexes(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    for table_name in (
        "xianyu_orders",
        "xianyu_order_sync_settings",
        "xianyu_order_sync_runs",
        "xianyu_order_operations",
    ):
        table = Base.metadata.tables.get(table_name)
        if table is None or table_name not in existing_tables:
            continue
        existing_indexes = {
            item["name"]: item for item in inspect(target_engine).get_indexes(table_name)
        }
        for index in table.indexes:
            existing = existing_indexes.get(index.name)
            expected_columns = [column.name for column in index.columns]
            if existing is not None and existing.get("column_names") != expected_columns:
                index.drop(bind=target_engine, checkfirst=True)
            index.create(bind=target_engine, checkfirst=True)


def _normalize_order_trade_roles(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_orders" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("xianyu_orders")}
    if not {"trade_role", "data_source", "raw_summary"}.issubset(columns):
        return
    with target_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT order_pk, trade_role, data_source, raw_summary FROM xianyu_orders "
                "WHERE trade_role IS NULL OR trade_role = '' OR data_source IS NULL OR data_source = ''"
            )
        ).mappings().all()
        for row in rows:
            summary: dict[str, object] = {}
            try:
                loaded = json.loads(row["raw_summary"] or "{}")
                if isinstance(loaded, dict):
                    summary = loaded
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            target_url = str(summary.get("target_url") or "").lower()
            task_name = str(summary.get("task_name") or "").lower()
            explicit_role = str(summary.get("trade_role") or "").lower()
            if explicit_role in {"seller", "buyer"}:
                role = explicit_role
            elif "role=seller" in target_url or task_name.endswith("_卖家") or "_seller" in task_name:
                role = "seller"
            elif "role=buyer" in target_url or task_name.endswith("_买家") or "_buyer" in task_name:
                role = "buyer"
            else:
                role = "unknown"
            source = str(summary.get("source") or "message")
            data_source = "seller_sold" if source == "seller_sold" else source
            connection.execute(
                text(
                    "UPDATE xianyu_orders SET trade_role = :role, data_source = :data_source "
                    "WHERE order_pk = :order_pk"
                ),
                {"role": role, "data_source": data_source, "order_pk": row["order_pk"]},
            )


def _normalize_order_sync_metadata(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_orders" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("xianyu_orders")}
    required = {
        "data_source",
        "first_seen_source",
        "platform_confirmed",
        "sync_state",
    }
    if not required.issubset(columns):
        return
    with target_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE xianyu_orders SET first_seen_source = "
                "COALESCE(NULLIF(first_seen_source, ''), NULLIF(data_source, ''), 'message') "
                "WHERE first_seen_source IS NULL OR first_seen_source = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE xianyu_orders SET platform_confirmed = 1, sync_state = 'confirmed' "
                "WHERE data_source IN ('seller_sold', 'buyer_bought')"
            )
        )
        connection.execute(
            text(
                "UPDATE xianyu_orders SET sync_state = 'provisional' "
                "WHERE (sync_state IS NULL OR sync_state = '') "
                "AND data_source NOT IN ('seller_sold', 'buyer_bought')"
            )
        )


def _backfill_headinfo_order_metadata(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_orders" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("xianyu_orders")}
    required = {
        "order_pk",
        "platform_order_id",
        "trade_role",
        "data_source",
        "raw_summary",
        "platform_confirmed",
        "sync_state",
        "headinfo_confirmed_at",
        "platform_capabilities",
        "platform_action_links",
        "status",
        "status_text",
        "platform_status",
        "refund_status",
        "last_synced_at",
        "updated_at",
    }
    if not required.issubset(columns):
        return
    with target_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT order_pk, platform_order_id, trade_role, raw_summary, "
                "last_synced_at, updated_at FROM xianyu_orders "
                "WHERE data_source = 'headinfo' AND platform_order_id IS NOT NULL"
            )
        ).mappings().all()
        for row in rows:
            try:
                summary = json.loads(row["raw_summary"] or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(summary, dict):
                continue
            common = summary.get("commonData")
            right = summary.get("right")
            common = common if isinstance(common, dict) else {}
            right = right if isinstance(right, dict) else {}
            response_order_id = str(common.get("orderId") or "").strip()
            if not response_order_id or response_order_id != str(row["platform_order_id"]):
                continue
            buttons = right.get("btnList") if isinstance(right.get("btnList"), list) else []
            capabilities: set[str] = set()
            links: dict[str, str] = {}
            for button in buttons:
                if not isinstance(button, dict):
                    continue
                action = str(button.get("tradeAction") or "").strip().upper()
                if not action:
                    continue
                capabilities.add(action)
                click_event = button.get("clickEvent")
                data = click_event.get("data") if isinstance(click_event, dict) else None
                if not isinstance(data, dict):
                    continue
                target = str(
                    data.get("url") or data.get("targetUrl") or data.get("jumpUrl") or ""
                ).strip()
                parsed = urlsplit(target) if target else None
                if (
                    parsed is not None
                    and parsed.scheme == "https"
                    and parsed.hostname
                    in {"h5.m.goofish.com", "www.goofish.com", "seller.goofish.com"}
                ):
                    links[action] = target[:2000]
            if row["trade_role"] != "seller":
                continue
            confirmed_at = row["last_synced_at"] or row["updated_at"] or datetime.now(UTC)
            values: dict[str, Any] = {
                "order_pk": row["order_pk"],
                "confirmed_at": confirmed_at,
                "capabilities": json.dumps(sorted(capabilities), ensure_ascii=False),
                "links": json.dumps(links, ensure_ascii=False),
            }
            refund_sql = ""
            if "DEAL_REFUND" in capabilities:
                refund_sql = ", refund_status = 'pending'"
            connection.execute(
                text(
                    "UPDATE xianyu_orders SET platform_confirmed = 1, "
                    "sync_state = 'confirmed', headinfo_confirmed_at = :confirmed_at, "
                    "platform_capabilities = :capabilities, platform_action_links = :links"
                    f"{refund_sql} WHERE order_pk = :order_pk"
                ),
                values,
            )

        confirmed_rows = connection.execute(
            text(
                "SELECT order_pk, trade_role, data_source, status, "
                "platform_capabilities FROM xianyu_orders "
                "WHERE headinfo_confirmed_at IS NOT NULL "
                "AND platform_order_id IS NOT NULL"
            )
        ).mappings().all()
        for row in confirmed_rows:
            if row["trade_role"] != "seller":
                continue
            try:
                loaded_capabilities = json.loads(row["platform_capabilities"] or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                loaded_capabilities = []
            capabilities = {
                str(item or "").strip().upper()
                for item in loaded_capabilities
                if str(item or "").strip()
            } if isinstance(loaded_capabilities, list) else set()
            refund_sql = ""
            if row["status"] == "refunded":
                refund_sql = ", status = 'closed', refund_status = 'refunded'"
            elif row["status"] == "refunding":
                repaired_status = (
                    "paid_waiting_delivery"
                    if "LOGISTICS_SEND" in capabilities
                    else "unknown"
                )
                refund_sql = (
                    f", status = '{repaired_status}', refund_status = 'pending'"
                )
            elif "DEAL_REFUND" in capabilities:
                refund_sql = ", refund_status = 'pending'"
            connection.execute(
                text(
                    "UPDATE xianyu_orders SET platform_confirmed = 1, "
                    "sync_state = 'confirmed', "
                    "data_source = CASE WHEN data_source IN "
                    "('seller_sold', 'buyer_bought') THEN data_source ELSE 'headinfo' END"
                    f"{refund_sql} WHERE order_pk = :order_pk"
                ),
                {"order_pk": row["order_pk"]},
            )


def _migrate_legacy_account_proxies(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_proxies" not in inspector.get_table_names():
        return
    account_columns = {column["name"] for column in inspector.get_columns("xianyu_accounts")}
    if "proxy_id" not in account_columns:
        return

    display_name_column = (
        "platform_display_name"
        if "platform_display_name" in account_columns
        else "NULL AS platform_display_name"
    )
    with target_engine.begin() as connection:
        rows = connection.execute(
            text(
                f"SELECT account_id, {display_name_column}, proxy_enabled, proxy_scheme, proxy_host, "
                "proxy_port, proxy_username, proxy_password FROM xianyu_accounts "
                "WHERE proxy_id IS NULL AND proxy_host IS NOT NULL AND proxy_port IS NOT NULL"
            )
        ).mappings().all()
        for row in rows:
            proxy_id = uuid.uuid4().hex
            label = str(row["platform_display_name"] or "").strip() or str(row["account_id"])[:8]
            name = f"legacy-{label}-{str(row['account_id'])[:8]}"[:80]
            now = datetime.now(UTC)
            connection.execute(
                text(
                    "INSERT INTO xianyu_proxies "
                    "(proxy_id, name, enabled, scheme, host, port, username, password, created_at, updated_at) "
                    "VALUES (:proxy_id, :name, :enabled, :scheme, :host, :port, :username, :password, :now, :now)"
                ),
                {
                    "proxy_id": proxy_id,
                    "name": name,
                    "enabled": bool(row["proxy_enabled"]),
                    "scheme": row["proxy_scheme"] or "socks5h",
                    "host": row["proxy_host"],
                    "port": row["proxy_port"],
                    "username": row["proxy_username"],
                    "password": row["proxy_password"],
                    "now": now,
                },
            )
            connection.execute(
                text(
                    "UPDATE xianyu_accounts SET proxy_id = :proxy_id, proxy_enabled = 0, "
                    "proxy_host = NULL, proxy_port = NULL, proxy_username = NULL, "
                    "proxy_password = NULL WHERE account_id = :account_id"
                ),
                {"proxy_id": proxy_id, "account_id": row["account_id"]},
            )
        connection.execute(
            text(
                "UPDATE xianyu_accounts SET proxy_enabled = 0, proxy_host = NULL, "
                "proxy_port = NULL, proxy_username = NULL, proxy_password = NULL "
                "WHERE proxy_id IS NOT NULL"
            )
        )


def _ensure_proxy_assignment_index(target_engine: Engine) -> None:
    """Enforce exclusive shared-proxy ownership without silently changing data."""

    table_name = "xianyu_accounts"
    inspector = inspect(target_engine)
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "proxy_id" not in columns:
        return

    with target_engine.begin() as connection:
        duplicate_rows = connection.execute(
            text(
                "SELECT proxy_id, COUNT(*) AS account_count FROM xianyu_accounts "
                "WHERE proxy_id IS NOT NULL GROUP BY proxy_id HAVING COUNT(*) > 1"
            )
        ).mappings().all()
        if duplicate_rows:
            conflicts: list[str] = []
            display_name_column = (
                "platform_display_name"
                if "platform_display_name" in columns
                else "NULL AS platform_display_name"
            )
            for duplicate in duplicate_rows:
                accounts = connection.execute(
                    text(
                        f"SELECT account_id, {display_name_column} FROM xianyu_accounts "
                        "WHERE proxy_id = :proxy_id ORDER BY created_at, account_id"
                    ),
                    {"proxy_id": duplicate["proxy_id"]},
                ).mappings().all()
                account_labels = ", ".join(
                    f"{str(row['platform_display_name'] or '').strip() or str(row['account_id'])[:8]}"
                    f"({row['account_id']})"
                    for row in accounts
                )
                conflicts.append(f"{duplicate['proxy_id']}: {account_labels}")
            raise RuntimeError(
                "duplicate proxy assignments must be resolved before startup: "
                + "; ".join(conflicts)
            )

    table = Base.metadata.tables.get(table_name)
    if table is None:
        return
    unique_index = next(
        (index for index in table.indexes if index.name == "uq_xianyu_accounts_proxy_id"),
        None,
    )
    if unique_index is None:
        return
    existing = {
        item["name"]: item for item in inspect(target_engine).get_indexes(table_name)
    }.get(unique_index.name)
    if existing is not None and (
        existing.get("column_names") != ["proxy_id"] or not existing.get("unique")
    ):
        unique_index.drop(bind=target_engine, checkfirst=True)
    unique_index.create(bind=target_engine, checkfirst=True)


def _drop_legacy_account_name(target_engine: Engine) -> None:
    """Remove the retired editable account alias after dependent migrations."""

    table_name = "xianyu_accounts"
    inspector = inspect(target_engine)
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "account_name" not in columns:
        return
    with target_engine.begin() as connection:
        connection.execute(text("ALTER TABLE xianyu_accounts DROP COLUMN account_name"))


def _drop_legacy_notification_tables(target_engine: Engine) -> None:
    """Remove the retired Bark channel and its per-account switches."""

    tables = set(inspect(target_engine).get_table_names())
    with target_engine.begin() as connection:
        if "xianyu_account_notifications" in tables:
            connection.execute(text("DROP TABLE xianyu_account_notifications"))
        if "xianyu_bark_config" in tables:
            connection.execute(text("DROP TABLE xianyu_bark_config"))


def _normalize_migrated_defaults(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "xianyu_accounts" in inspector.get_table_names():
        account_columns = {
            column["name"] for column in inspector.get_columns("xianyu_accounts")
        }
        if "cookie_updated_at" in account_columns:
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE xianyu_accounts SET cookie_updated_at = updated_at "
                        "WHERE cookie_updated_at IS NULL"
                    )
                )
        if "platform" in account_columns:
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE xianyu_accounts SET platform = 'xianyu' "
                        "WHERE platform IS NULL OR platform = ''"
                    )
                )
    if "xianyu_conversations" in inspector.get_table_names():
        conversation_columns = {
            column["name"] for column in inspector.get_columns("xianyu_conversations")
        }
        if {"needs_reply", "last_inbound_at", "last_outbound_at"}.issubset(
            conversation_columns
        ):
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE xianyu_conversations SET "
                        "last_inbound_at = CASE WHEN last_message_direction = 'inbound' "
                        "THEN last_message_at ELSE last_inbound_at END, "
                        "last_outbound_at = CASE WHEN last_message_direction = 'outbound' "
                        "THEN last_message_at ELSE last_outbound_at END, "
                        "needs_reply = CASE WHEN last_message_direction = 'inbound' "
                        "AND last_message_type IN ('text', 'image', 'audio', 'unknown') THEN 1 ELSE 0 END "
                        "WHERE last_inbound_at IS NULL AND last_outbound_at IS NULL"
                    )
                )
        if {
            "last_activity_at",
            "last_activity_content",
            "last_activity_type",
            "last_activity_direction",
        }.issubset(conversation_columns):
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE xianyu_conversations SET "
                        "last_activity_at = COALESCE(last_activity_at, last_message_at, updated_at, created_at), "
                        "last_activity_content = COALESCE(last_activity_content, last_message_content), "
                        "last_activity_type = COALESCE(last_activity_type, last_message_type), "
                        "last_activity_direction = COALESCE(last_activity_direction, last_message_direction) "
                        "WHERE last_activity_at IS NULL OR last_activity_type IS NULL "
                        "OR last_activity_direction IS NULL"
                    )
                )
    if "xianyu_auto_reply_settings" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("xianyu_auto_reply_settings")}
    if "ai_context_messages" in columns:
        with target_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE xianyu_auto_reply_settings SET ai_context_messages = 10 "
                    "WHERE ai_context_messages IS NULL OR ai_context_messages <= 0"
                )
            )


def _normalize_cookie_renewal_metadata(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    tables = set(inspector.get_table_names())
    if "xianyu_accounts" not in tables or "xianyu_cookie_renewals" not in tables:
        return

    account_columns = {column["name"] for column in inspector.get_columns("xianyu_accounts")}
    renewal_columns = {
        column["name"] for column in inspector.get_columns("xianyu_cookie_renewals")
    }
    with target_engine.begin() as connection:
        if "phase" in renewal_columns:
            connection.execute(
                text(
                    "UPDATE xianyu_cookie_renewals SET phase = CASE "
                    "WHEN state = 'running' THEN 'renewing' "
                    "WHEN state IN ('succeeded', 'failed', 'conflict') THEN 'completed' "
                    "ELSE 'idle' END WHERE phase IS NULL OR phase = ''"
                )
            )
        if "last_finished_at" in renewal_columns:
            connection.execute(
                text(
                    "UPDATE xianyu_cookie_renewals SET last_finished_at = CASE "
                    "WHEN state = 'succeeded' THEN last_succeeded_at "
                    "WHEN state = 'failed' THEN last_failed_at "
                    "WHEN state = 'conflict' THEN updated_at "
                    "ELSE last_finished_at END WHERE last_finished_at IS NULL"
                )
            )
        if "last_verified_at" in renewal_columns:
            connection.execute(
                text(
                    "UPDATE xianyu_cookie_renewals SET last_verified_at = last_succeeded_at "
                    "WHERE last_verified_at IS NULL AND last_succeeded_at IS NOT NULL"
                )
            )
        if "last_verified_source" in renewal_columns:
            connection.execute(
                text(
                    "UPDATE xianyu_cookie_renewals SET last_verified_source = "
                    "COALESCE(`trigger`, 'legacy_renewal') "
                    "WHERE last_verified_source IS NULL AND last_verified_at IS NOT NULL"
                )
            )
            connection.execute(
                text(
                    "UPDATE xianyu_cookie_renewals SET last_verified_source = CASE "
                    "WHEN last_verified_source = 'manual' THEN 'manual_renewal' "
                    "WHEN last_verified_source = 'scheduled' THEN 'scheduled_renewal' "
                    "ELSE last_verified_source END"
                )
            )

        if "cookie_update_source" in account_columns:
            rows = connection.execute(
                text(
                    "SELECT a.account_id, a.cookie_updated_at, r.last_succeeded_at, r.trigger "
                    "FROM xianyu_accounts a LEFT JOIN xianyu_cookie_renewals r "
                    "ON r.account_id = a.account_id "
                    "WHERE a.cookie_updated_at IS NOT NULL "
                    "AND (a.cookie_update_source IS NULL OR a.cookie_update_source = '')"
                )
            ).mappings().all()
            for row in rows:
                cookie_updated_at = row["cookie_updated_at"]
                succeeded_at = row["last_succeeded_at"]
                matches_renewal = bool(
                    cookie_updated_at
                    and succeeded_at
                    and abs((cookie_updated_at - succeeded_at).total_seconds()) <= 2
                )
                source = "legacy"
                if matches_renewal:
                    source = {
                        "manual": "manual_renewal",
                        "scheduled": "scheduled_renewal",
                        "auth_recovery": "auth_recovery",
                    }.get(row["trigger"], "legacy")
                connection.execute(
                    text(
                        "UPDATE xianyu_accounts SET cookie_update_source = :source "
                        "WHERE account_id = :account_id"
                    ),
                    {"source": source, "account_id": row["account_id"]},
                )

        if "xianyu_cookie_renewal_attempts" not in tables:
            return
        legacy_rows = connection.execute(
            text(
                "SELECT r.account_id, r.state, r.phase, r.trigger, r.message, "
                "r.updated_cookie_names, r.last_started_at, r.last_finished_at, "
                "r.next_attempt_at, r.updated_at FROM xianyu_cookie_renewals r "
                "WHERE r.state <> 'idle' AND r.trigger IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM xianyu_cookie_renewal_attempts a "
                "WHERE a.account_id = r.account_id)"
            )
        ).mappings().all()
        for row in legacy_rows:
            started_at = row["last_started_at"] or row["updated_at"]
            finished_at = row["last_finished_at"]
            connection.execute(
                text(
                    "INSERT INTO xianyu_cookie_renewal_attempts "
                    "(attempt_id, account_id, `trigger`, state, phase, message, error_kind, "
                    "updated_cookie_names, runtime_applied, started_at, finished_at, "
                    "next_attempt_at, created_at, updated_at) VALUES "
                    "(:attempt_id, :account_id, :trigger, :state, :phase, :message, "
                    ":error_kind, :updated_cookie_names, NULL, :started_at, :finished_at, "
                    ":next_attempt_at, :created_at, :updated_at)"
                ),
                {
                    "attempt_id": uuid.uuid4().hex,
                    "account_id": row["account_id"],
                    "trigger": row["trigger"],
                    "state": row["state"],
                    "phase": row["phase"] or "completed",
                    "message": row["message"],
                    "error_kind": "legacy_failure" if row["state"] == "failed" else None,
                    "updated_cookie_names": row["updated_cookie_names"] or "[]",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "next_attempt_at": row["next_attempt_at"],
                    "created_at": started_at,
                    "updated_at": row["updated_at"],
                },
            )
