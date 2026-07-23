import unittest

from pydantic import ValidationError
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import _normalize_account_sort_order
from apps.api.xianyu_admin_api.orm import AccountORM, Base
from apps.api.xianyu_admin_api.schemas import AccountCreatePayload, AccountReorderPayload
from apps.api.xianyu_admin_api.store import AccountStore


class AccountOrderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.store = AccountStore(session_factory=self.factory, initialize=False)

    async def asyncTearDown(self) -> None:
        self.engine.dispose()

    async def test_create_appends_and_reorder_persists(self) -> None:
        first = await self.store.create_account(AccountCreatePayload(account_name="first"))
        second = await self.store.create_account(AccountCreatePayload(account_name="second"))
        third = await self.store.create_account(AccountCreatePayload(account_name="third"))

        self.assertEqual([first.sort_order, second.sort_order, third.sort_order], [100, 200, 300])

        reordered = await self.store.reorder_accounts(
            AccountReorderPayload(
                account_ids=[third.account_id, first.account_id, second.account_id]
            )
        )
        self.assertEqual(
            [account.account_id for account in reordered],
            [third.account_id, first.account_id, second.account_id],
        )
        self.assertEqual([account.sort_order for account in reordered], [100, 200, 300])

        persisted = await self.store.list_accounts()
        self.assertEqual(
            [account.account_id for account in persisted],
            [third.account_id, first.account_id, second.account_id],
        )

        fourth = await self.store.create_account(AccountCreatePayload(account_name="fourth"))
        self.assertEqual(fourth.sort_order, 400)
        self.assertEqual(
            [account.account_id for account in await self.store.list_accounts()],
            [third.account_id, first.account_id, second.account_id, fourth.account_id],
        )

    async def test_reorder_rejects_stale_account_set(self) -> None:
        first = await self.store.create_account(AccountCreatePayload(account_name="first"))
        await self.store.create_account(AccountCreatePayload(account_name="second"))

        with self.assertRaisesRegex(ValueError, "账户列表已经变化"):
            await self.store.reorder_accounts(
                AccountReorderPayload(account_ids=[first.account_id])
            )

    async def test_legacy_zero_sort_order_is_backfilled_in_creation_order(self) -> None:
        first = await self.store.create_account(AccountCreatePayload(account_name="first"))
        second = await self.store.create_account(AccountCreatePayload(account_name="second"))
        third = await self.store.create_account(AccountCreatePayload(account_name="third"))
        with self.factory() as session:
            session.execute(update(AccountORM).values(sort_order=0))
            session.commit()

        _normalize_account_sort_order(self.engine)

        with self.factory() as session:
            rows = session.scalars(
                select(AccountORM).order_by(AccountORM.sort_order)
            ).all()
        self.assertEqual(
            [row.account_id for row in rows],
            [first.account_id, second.account_id, third.account_id],
        )
        self.assertEqual([row.sort_order for row in rows], [100, 200, 300])

    def test_reorder_payload_rejects_empty_and_duplicate_ids(self) -> None:
        with self.assertRaises(ValidationError):
            AccountReorderPayload(account_ids=[])
        with self.assertRaises(ValidationError):
            AccountReorderPayload(account_ids=["account-1", "account-1"])
        with self.assertRaises(ValidationError):
            AccountReorderPayload(account_ids=["account-1", ""])
