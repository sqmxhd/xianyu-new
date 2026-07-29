import os
import unittest

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.orm import IMVerificationORM
from apps.api.xianyu_admin_api.schemas import AccountCreatePayload
from apps.api.xianyu_admin_api.store import AccountStore


class IMVerificationPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.store = AccountStore(session_factory=self.sessions, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(cookie="unb=seller-1; _m_h5_tk=token",
            )
        )

    async def test_verification_url_is_encrypted_and_round_trips(self) -> None:
        url = "https://passport.goofish.com/verify?id=sensitive-token"
        verification = await self.store.record_im_verification(
            self.account.account_id,
            "FAIL_SYS_USER_VALIDATE",
            url,
        )
        self.assertIsNotNone(verification)
        assert verification is not None

        with self.sessions() as session:
            row = session.scalar(
                select(IMVerificationORM).where(
                    IMVerificationORM.verification_id == verification.verification_id
                )
            )
            self.assertIsNotNone(row)
            assert row is not None
            self.assertNotEqual(row.verification_url_encrypted, url)
            self.assertNotIn("sensitive-token", row.verification_url_encrypted or "")

        self.assertEqual(
            await self.store.get_im_verification_url(verification.verification_id),
            url,
        )

    async def test_active_verification_is_reused_and_state_is_persisted(self) -> None:
        first = await self.store.record_im_verification(
            self.account.account_id,
            "FAIL_SYS_USER_VALIDATE",
            "https://example.invalid/first",
        )
        second = await self.store.record_im_verification(
            self.account.account_id,
            "RGV587_ERROR",
            "https://example.invalid/second",
        )
        assert first is not None and second is not None
        self.assertEqual(first.verification_id, second.verification_id)
        self.assertEqual(second.reason_code, "RGV587_ERROR")

        ready = await self.store.set_im_verification_state(
            second.verification_id,
            "ready",
            "ready",
            expires_in_seconds=600,
        )
        assert ready is not None
        self.assertEqual(ready.status, "ready")
        self.assertIsNotNone(ready.expires_at)


if __name__ == "__main__":
    unittest.main()
