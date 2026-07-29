import os
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import (
    Base,
    _migrate_auto_reply_ownership,
    _migrate_auto_reply_v2,
)
from apps.api.xianyu_admin_api.orm import (
    AIProviderSettingORM,
    AutoReplySettingORM,
    UserAutoReplyRuleORM,
    UserAutoReplySettingORM,
)
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    AccountUpdatePayload,
    AccountAutoReplyUpdatePayload,
    AccountWorkspaceVisibilityUpdatePayload,
    AIProviderSettingUpdatePayload,
    AutoReplyPreviewRequestPayload,
    AutoReplyRuleCreatePayload,
    AutoReplyRuleReorderPayload,
    AutoReplySettingUpdatePayload,
    UserCreatePayload,
)
from apps.api.xianyu_admin_api.store import AccountStore
from apps.api.xianyu_admin_api.sensitive import decrypt_sensitive


class AutoReplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.engine = engine
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.user = await self.store.create_user(
            UserCreatePayload(username="reply-owner", password="password-123")
        )
        self.account = await self.store.create_account(
            AccountCreatePayload(enabled=False),
            automation_owner_user_id=self.user.user_id,
        )
        self.account = await self.store.update_account_platform_identity(
            self.account.account_id,
            platform_user_id="seller-test-account",
            display_name="test-account",
            avatar_url=None,
        )
        assert self.account is not None
        await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            direction="inbound",
            message_type="text",
            content="请问还在吗",
            peer_user_id="buyer-1",
        )

    async def test_manual_takeover_suppresses_automatic_reply(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                trigger_type="fallback",
                reply_text="在的",
            ),
        )
        until = await self.store.set_manual_takeover(
            self.account.account_id, "conversation-1", active=True, minutes=30
        )

        decision = await self.store.decide_auto_reply(
            self.account.account_id, "请问还在吗", "conversation-1"
        )
        self.assertIsNotNone(until)
        self.assertFalse(decision.should_reply)
        self.assertEqual(decision.reason, "manual takeover active")

        await self.store.set_manual_takeover(
            self.account.account_id, "conversation-1", active=False, minutes=30
        )
        decision = await self.store.decide_auto_reply(
            self.account.account_id, "请问还在吗", "conversation-1"
        )
        self.assertTrue(decision.should_reply)
        self.assertEqual(decision.reply_text, "在的")

    async def test_account_remark_is_optional_and_can_be_cleared(self) -> None:
        unnamed = await self.store.create_account(
            AccountCreatePayload(enabled=False),
            automation_owner_user_id=self.user.user_id,
        )
        self.assertTrue(unnamed.display_name.startswith("闲鱼账户-"))
        self.assertIsNone(unnamed.remark)

        account = await self.store.create_account(
            AccountCreatePayload(remark="售后备用账户", enabled=False),
            automation_owner_user_id=self.user.user_id,
        )
        self.assertEqual(account.remark, "售后备用账户")
        self.assertTrue(account.display_name.startswith("闲鱼账户-"))

        updated = await self.store.update_account(
            account.account_id,
            AccountUpdatePayload(remark=""),
        )
        assert updated is not None
        self.assertIsNone(updated.remark)

    async def test_manual_takeover_after_decision_blocks_execution_claim(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        rule = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(keyword="还在吗", reply_text="在的"),
        )
        decision = await self.store.decide_auto_reply(
            self.account.account_id,
            "还在吗",
            "conversation-1",
        )
        self.assertTrue(decision.should_reply)
        self.assertIsNotNone(rule)

        await self.store.set_manual_takeover(
            self.account.account_id, "conversation-1", active=True, minutes=30
        )
        execution_id = await self.store.claim_auto_reply_execution(
            account_id=self.account.account_id,
            conversation_id="conversation-1",
            inbound_message_pk=None,
            rule_id=rule.rule_id if rule else None,
            matched_keyword="还在吗",
            reply_text="在的",
        )

        self.assertIsNone(execution_id)
        self.assertEqual(await self.store.list_user_auto_reply_logs(self.user.user_id), [])

    async def test_permanent_takeover_survives_store_restart_until_restored(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(trigger_type="fallback", reply_text="自动回复"),
        )

        until = await self.store.set_manual_takeover(
            self.account.account_id,
            "conversation-1",
            mode="permanent",
        )
        restarted_store = AccountStore(
            session_factory=self.store._session_factory,
            initialize=False,
        )
        conversation = await restarted_store.get_conversation(
            self.account.account_id,
            "conversation-1",
        )
        decision = await restarted_store.decide_auto_reply(
            self.account.account_id,
            "请问还在吗",
            "conversation-1",
        )

        self.assertIsNone(until)
        assert conversation is not None
        self.assertEqual(conversation.manual_takeover_mode, "permanent")
        self.assertIsNone(conversation.manual_takeover_until)
        self.assertFalse(decision.should_reply)
        self.assertEqual(decision.reason, "manual takeover active")

        await restarted_store.set_manual_takeover(
            self.account.account_id,
            "conversation-1",
            mode="auto",
        )
        restored = await restarted_store.decide_auto_reply(
            self.account.account_id,
            "请问还在吗",
            "conversation-1",
        )
        self.assertTrue(restored.should_reply)

    async def test_ai_credentials_are_redacted_and_context_is_bounded(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        setting = await self.store.update_ai_provider_setting(
            AIProviderSettingUpdatePayload(
                base_url="https://llm.example/v1/",
                api_key="secret-key",
                model="test-model",
            )
        )
        rule = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                trigger_type="fallback",
                action_type="ai",
                context_message_count=1,
                context_fields=["message.text"],
                ai_system_prompt="只回答当前问题",
            ),
        )

        self.assertTrue(setting.has_api_key)
        self.assertFalse(hasattr(setting, "api_key"))
        request = await self.store.get_ai_reply_request(
            self.account.account_id,
            "conversation-1",
            rule.rule_id if rule else None,
        )
        self.assertIsNotNone(request)
        self.assertEqual(request.api_key, "secret-key")
        self.assertEqual(len(request.messages), 1)
        self.assertIn('"text":"请问还在吗"', request.system_prompt)

        cleared = await self.store.update_ai_provider_setting(
            AIProviderSettingUpdatePayload(clear_api_key=True)
        )
        self.assertFalse(cleared.has_api_key)
        self.assertEqual(cleared.base_url, "https://llm.example/v1/")
        self.assertEqual(cleared.model, "test-model")

    async def test_account_switches_are_independent(self) -> None:
        second = await self.store.create_account(
            AccountCreatePayload(enabled=False),
            automation_owner_user_id=self.user.user_id,
        )
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                trigger_type="fallback",
                reply_text="{{ account.name }}：你好，{{ sender.name }}",
            ),
        )
        inbound = await self.store.record_message(
            account_id=self.account.account_id,
            conversation_id="owned-conversation",
            direction="inbound",
            message_type="text",
            content="在吗",
            peer_user_id="buyer-2",
            peer_name="小明",
        )

        first_decision = await self.store.decide_auto_reply(
            self.account.account_id,
            "在吗",
            "owned-conversation",
            inbound_message=inbound,
        )
        second_decision = await self.store.decide_auto_reply(
            second.account_id,
            "在吗",
            "excluded-conversation",
        )

        self.assertTrue(first_decision.should_reply)
        self.assertEqual(first_decision.reply_text, "test-account：你好，小明")
        self.assertFalse(second_decision.should_reply)
        self.assertEqual(second_decision.reason, "auto reply disabled")

    async def test_workspace_visibility_does_not_disable_auto_reply(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(trigger_type="fallback", reply_text="仍然回复"),
        )
        updated = await self.store.update_account_workspace_visibility(
            self.account.account_id,
            AccountWorkspaceVisibilityUpdatePayload(
                conversation_visible=False,
                order_management_visible=False,
                product_management_visible=False,
            ),
        )
        assert updated is not None
        self.assertTrue(updated.auto_reply_enabled)
        self.assertFalse(updated.conversation_visible)
        self.assertFalse(updated.order_management_visible)
        self.assertFalse(updated.product_management_visible)

        decision = await self.store.decide_auto_reply(
            self.account.account_id,
            "还在吗",
            "conversation-1",
        )
        self.assertTrue(decision.should_reply)
        self.assertEqual(decision.reply_text, "仍然回复")

    async def test_user_rule_scope_and_inbound_claim_are_idempotent(self) -> None:
        account = await self.store.create_account(
            AccountCreatePayload(enabled=False),
            automation_owner_user_id=self.user.user_id,
        )
        await self.store.update_account_auto_reply(
            account.account_id, AccountAutoReplyUpdatePayload(enabled=True)
        )
        rule = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                keyword="价格",
                account_ids=[account.account_id],
                reply_text="商品 {{ item.title }} 售价 {{ item.price }}",
            ),
        )
        inbound = await self.store.record_message(
            account_id=account.account_id,
            conversation_id="rule-conversation",
            direction="inbound",
            message_type="text",
            content="什么价格",
            peer_user_id="buyer-3",
            item_id="item-1",
        )
        decision = await self.store.decide_auto_reply(
            account.account_id,
            "什么价格",
            "rule-conversation",
            "item-1",
            inbound,
        )
        first_claim = await self.store.claim_auto_reply_execution(
            account_id=account.account_id,
            conversation_id="rule-conversation",
            inbound_message_pk=inbound.message_pk,
            rule_id=rule.rule_id if rule else None,
            matched_keyword="价格",
            reply_text=decision.reply_text or "",
        )
        second_claim = await self.store.claim_auto_reply_execution(
            account_id=account.account_id,
            conversation_id="rule-conversation",
            inbound_message_pk=inbound.message_pk,
            rule_id=rule.rule_id if rule else None,
            matched_keyword="价格",
            reply_text=decision.reply_text or "",
        )

        self.assertTrue(decision.should_reply)
        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)

    async def test_rule_level_continue_and_fallback(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                keyword="价格",
                reply_text="第一段",
                priority=10,
                continue_matching=True,
            ),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                keyword="价格",
                reply_text="第二段",
                priority=20,
            ),
        )
        await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                trigger_type="fallback",
                reply_text="兜底",
                priority=100,
            ),
        )

        matched = await self.store.decide_auto_reply(
            self.account.account_id,
            "请问价格",
            "conversation-1",
        )
        fallback = await self.store.decide_auto_reply(
            self.account.account_id,
            "其他问题",
            "conversation-1",
        )

        self.assertEqual(matched.reply_text, "第一段\n第二段")
        self.assertEqual(fallback.reply_text, "兜底")

    async def test_rules_reorder_atomically_and_keep_fallback_last(self) -> None:
        first = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(keyword="第一", reply_text="first"),
        )
        fallback = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(trigger_type="fallback", reply_text="fallback"),
        )
        second = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(keyword="第二", reply_text="second"),
        )
        assert first and fallback and second

        reordered = await self.store.reorder_user_auto_reply_rules(
            self.user.user_id,
            AutoReplyRuleReorderPayload(
                rule_ids=[fallback.rule_id, second.rule_id, first.rule_id]
            ),
        )

        self.assertIsNotNone(reordered)
        self.assertEqual(
            [rule.rule_id for rule in reordered or []],
            [second.rule_id, first.rule_id, fallback.rule_id],
        )
        self.assertEqual([rule.priority for rule in reordered or []], [100, 200, 300])
        with self.assertRaisesRegex(ValueError, "规则列表已经变化"):
            await self.store.reorder_user_auto_reply_rules(
                self.user.user_id,
                AutoReplyRuleReorderPayload(rule_ids=[first.rule_id]),
            )

    async def test_rule_issues_detect_overlapping_fallbacks_and_missing_ai_provider(self) -> None:
        fallback_one = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(trigger_type="fallback", reply_text="one"),
        )
        fallback_two = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(trigger_type="fallback", reply_text="two"),
        )
        ai_rule = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                keyword="人工智能",
                action_type="ai",
                reply_text="",
            ),
        )
        assert fallback_one and fallback_two and ai_rule

        issues = await self.store.list_user_auto_reply_rule_issues(self.user.user_id)
        issue_codes = {issue.code for issue in issues}

        self.assertIn("overlapping_fallbacks", issue_codes)
        self.assertIn("ai_provider_incomplete", issue_codes)

    async def test_preview_is_read_only_and_reports_blocking_gates(self) -> None:
        await self.store.update_account_auto_reply(
            self.account.account_id,
            AccountAutoReplyUpdatePayload(enabled=True),
        )
        rule = await self.store.create_user_auto_reply_rule(
            self.user.user_id,
            AutoReplyRuleCreatePayload(
                keyword="还在吗",
                reply_text="在的，{{ sender.id }}",
            ),
        )
        assert rule

        preview = await self.store.preview_user_auto_reply(
            self.user.user_id,
            AutoReplyPreviewRequestPayload(
                account_id=self.account.account_id,
                content="商品还在吗",
                sender_user_id="buyer-preview",
                conversation_id="conversation-1",
            ),
        )

        self.assertIsNotNone(preview)
        assert preview
        self.assertTrue(preview.should_reply)
        self.assertFalse(preview.executable)
        self.assertEqual(preview.reply_preview, "在的，buyer-preview")
        self.assertEqual(preview.matched_rule_ids, [rule.rule_id])
        self.assertEqual(preview.reason, "平台账户已禁用")
        self.assertFalse(next(gate for gate in preview.gates if gate.key == "account_enabled").passed)
        self.assertEqual(await self.store.list_user_auto_reply_logs(self.user.user_id), [])

    async def test_v2_migration_preserves_effective_behavior_once(self) -> None:
        await self.store.update_user_auto_reply_setting(
            self.user.user_id,
            AutoReplySettingUpdatePayload(
                enabled=True,
                default_reply_enabled=True,
                default_reply_text="旧兜底",
                ai_enabled=True,
                ai_base_url="https://legacy.example/v1",
                ai_api_key="legacy-secret",
                ai_model="legacy-model",
                ai_context_messages=7,
            ),
        )

        _migrate_auto_reply_ownership(self.engine)
        _migrate_auto_reply_v2(self.engine)
        _migrate_auto_reply_v2(self.engine)

        with self.store._session_factory() as session:
            provider = session.get(AIProviderSettingORM, "default")
            account_setting = session.get(AutoReplySettingORM, self.account.account_id)
            user_setting = session.get(UserAutoReplySettingORM, self.user.user_id)
            fallback_rules = (
                session.query(UserAutoReplyRuleORM)
                .filter(
                    UserAutoReplyRuleORM.user_id == self.user.user_id,
                    UserAutoReplyRuleORM.trigger_type == "fallback",
                )
                .all()
            )

            self.assertIsNotNone(provider)
            self.assertEqual(decrypt_sensitive(provider.api_key_encrypted), "legacy-secret")
            self.assertTrue(account_setting.enabled)
            self.assertFalse(user_setting.enabled)
            self.assertIsNone(user_setting.ai_api_key)
            self.assertEqual(len(fallback_rules), 2)


if __name__ == "__main__":
    unittest.main()
