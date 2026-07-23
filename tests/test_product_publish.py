import io
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

import requests
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.xianyu_admin_api.database import Base
from apps.api.xianyu_admin_api.product_images import ProductImageStorage
from apps.api.xianyu_admin_api.product_image_archives import (
    ProductImageArchiveError,
    import_product_image_archive,
)
from apps.api.xianyu_admin_api.product_publish_service import (
    _request_from_snapshot,
    list_platform_product_locations,
    merge_account_cookie_updates,
)
from apps.api.xianyu_admin_api.product_regions import product_region_catalog
from apps.api.xianyu_admin_api.schemas import (
    AccountCreatePayload,
    BackgroundTaskCreatePayload,
    ProductDraftCreatePayload,
    ProductPublishJobCreatePayload,
    ProductPublishRetryPayload,
    ProductLocationOptionPayload,
    ProductLocationPayload,
    ProductDraftUpdatePayload,
    ProductPublishTaskCreatePayload,
    PublishAddressCreatePayload,
    PublishAddressGroupCreatePayload,
    PublishAddressRegionSelectionPayload,
)
from apps.api.xianyu_admin_api.store import AccountStore
from apps.api.xianyu_admin_api.orm import (
    ProductLocationCacheORM,
    ProductPublishTaskAssetORM,
    PublishAddressUsageORM,
)
from integrations.xianyu_core import (
    AccountConfig,
    MtopProductPublisher,
    PublishedImage,
    ProductImageData,
    ProductPublishError,
    ProductPublishRequest,
)


def jpeg_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "green").save(output, format="JPEG")
    return output.getvalue()


class FakeResponse:
    def __init__(self, payload=None, *, body=b"", status_code=200, headers=None):
        self._payload = payload
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.is_redirect = 300 <= status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, _size):
        yield self._body

    def close(self):
        return None


class FakeSession:
    def __init__(self, *, posts=None, get_response=None):
        self.trust_env = True
        self.headers = {}
        self.proxies = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self.posts = list(posts or [])
        self.get_response = get_response
        self.post_calls = []
        self.get_calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def close(self):
        self.closed = True

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs, self.cookies.get_dict()))
        assert self.get_response is not None
        return self.get_response

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        result = self.posts.pop(0)
        if isinstance(result, BaseException):
            raise result
        response, cookie_updates = result if isinstance(result, tuple) else (result, {})
        self.cookies.update(cookie_updates)
        return response


def success(data):
    return FakeResponse({"ret": ["SUCCESS::调用成功"], "data": data})


def location_candidate():
    return {
        "location_id": "location-nanjing",
        "label": "江苏省 南京市 江宁区 测试地址",
        "source": "platform_common",
        "area": "江宁区",
        "city": "南京市",
        "division_id": "320115",
        "longitude": 118.8,
        "latitude": 31.9,
        "poi_id": "poi-1",
        "poi_name": "测试地址",
        "prov": "江苏省",
    }


def publisher_responses(*, publish_result=None):
    category = {
        "categoryPredictResult": {
            "catId": "1",
            "catName": "数码",
            "channelCatId": "2",
            "tbCatId": "3",
        },
        "cardList": [],
    }
    location = {
        "commonAddresses": [
            {
                "area": "江宁区",
                "city": "南京市",
                "divisionId": 320115,
                "longitude": 118.8,
                "latitude": 31.9,
                "poiId": "poi-1",
                "poi": "测试地址",
                "prov": "江苏省",
            }
        ]
    }
    return [
        success(location),
        FakeResponse({"object": {"url": "https://img.alicdn.com/item.jpg", "pix": "32x24"}}),
        success(category),
        publish_result or (success({"itemId": "123456789"}), {"_m_h5_tk": "newtoken_2"}),
        success({"items": [{"itemId": "123456789"}]}),
    ]


class ProductPublisherTests(unittest.TestCase):
    def make_request(self):
        return ProductPublishRequest(
            title="测试商品",
            description="九成新测试商品",
            image_urls=("https://example.com/item.jpg",),
            price=Decimal("19.90"),
            original_price=Decimal("29.90"),
            stock=1,
            delivery_choice="free_shipping",
            unique_code="123456789012345678",
        )

    def test_publish_payload_uses_first_image_as_main_and_forces_pickup_only(self):
        platform = FakeSession()
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            sign_handler=lambda *_args: "sign",
        )
        request = replace(
            self.make_request(),
            delivery_choice="pickup_only",
            can_self_pickup=False,
        )
        images = [
            PublishedImage(url="https://img.alicdn.com/first.jpg", width=32, height=24),
            PublishedImage(url="https://img.alicdn.com/second.jpg", width=32, height=24),
        ]
        try:
            payload = publisher._build_publish_payload(
                request,
                images,
                {},
                {"channelCatId": "2"},
                {
                    "prov": "浙江省",
                    "city": "杭州市",
                    "area": "西湖区",
                    "division_id": "330106",
                    "longitude": 120.1,
                    "latitude": 30.2,
                    "poi_id": "poi-hz",
                    "poi_name": "西湖区",
                },
            )
        finally:
            publisher.close()

        self.assertEqual(
            [image["major"] for image in payload["imageInfoDOList"]],
            [True, False],
        )
        self.assertTrue(payload["itemPostFeeDTO"]["onlyTakeSelf"])
        self.assertTrue(payload["onlyTakeSelf"])

    def test_optional_pickup_preserves_fixed_freight(self):
        platform = FakeSession()
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            sign_handler=lambda *_args: "sign",
        )
        request = replace(
            self.make_request(),
            delivery_choice="fixed",
            post_price=Decimal("8.00"),
            can_self_pickup=True,
        )
        try:
            payload = publisher._build_publish_payload(
                request,
                [PublishedImage(url="https://img.alicdn.com/first.jpg", width=32, height=24)],
                {},
                {"channelCatId": "2"},
                {
                    "prov": "浙江省",
                    "city": "杭州市",
                    "area": "西湖区",
                    "division_id": "330106",
                    "longitude": 120.1,
                    "latitude": 30.2,
                    "poi_id": "poi-hz",
                    "poi_name": "西湖区",
                },
            )
        finally:
            publisher.close()

        self.assertTrue(payload["onlyTakeSelf"])
        self.assertFalse(payload["itemPostFeeDTO"]["onlyTakeSelf"])
        self.assertTrue(payload["itemPostFeeDTO"]["supportFreight"])
        self.assertEqual(payload["itemPostFeeDTO"]["postPriceInCent"], "800")

    @patch.object(MtopProductPublisher, "_validate_public_url", return_value=None)
    def test_full_http_chain_and_cookie_isolation(self, _validate):
        platform = FakeSession(posts=publisher_responses())
        downloader = FakeSession(get_response=FakeResponse(body=jpeg_bytes()))
        publisher = MtopProductPublisher(
            AccountConfig(
                account_id="account-1",
                cookie="unb=10001; _m_h5_tk=oldtoken_1; secret=do-not-leak",
            ),
            session_factory=lambda: platform,
            download_session_factory=lambda: downloader,
            sign_handler=lambda timestamp, token, data: f"{timestamp}:{token}:{len(data)}",
        )

        result = publisher.publish(self.make_request())

        self.assertEqual(result.item_id, "123456789")
        self.assertTrue(result.verified)
        self.assertEqual(result.cookie_updates, {"_m_h5_tk": "newtoken_2"})
        self.assertEqual(downloader.get_calls[0][2], {})
        self.assertEqual(len(platform.post_calls), 5)
        publish_url, publish_kwargs = platform.post_calls[3]
        self.assertIn("mtop.idle.pc.idleitem.publish", publish_url)
        publish_payload = json.loads(publish_kwargs["data"]["data"])
        self.assertEqual(publish_payload["itemPriceDTO"]["priceInCent"], "1990")
        self.assertEqual(publish_payload["itemCatDTO"]["channelCatId"], "2")
        self.assertEqual(publish_payload["itemAddrDTO"]["divisionId"], "320115")
        self.assertEqual(publish_payload["itemAddrDTO"]["poiName"], "测试地址")
        self.assertTrue(publish_kwargs["params"]["sign"])

    @patch.object(MtopProductPublisher, "_validate_public_url", return_value=None)
    def test_selected_location_skips_default_location_request(self, _validate):
        responses = publisher_responses()
        responses.pop(0)
        platform = FakeSession(posts=responses)
        downloader = FakeSession(get_response=FakeResponse(body=jpeg_bytes()))
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            download_session_factory=lambda: downloader,
            sign_handler=lambda *_args: "sign",
        )
        request = replace(
            self.make_request(),
            location={
                "prov": "浙江省",
                "city": "杭州市",
                "area": "西湖区",
                "division_id": "330106",
                "longitude": 120.1,
                "latitude": 30.2,
                "poi_id": "poi-hz",
                "poi_name": "西湖区",
            },
        )

        result = publisher.publish(request)

        self.assertTrue(result.verified)
        self.assertFalse(any("idle.local.poi.get" in call[0] for call in platform.post_calls))
        publish_call = next(call for call in platform.post_calls if "idleitem.publish" in call[0])
        publish_payload = json.loads(publish_call[1]["data"]["data"])
        self.assertEqual(publish_payload["itemAddrDTO"]["divisionId"], "330106")
        self.assertEqual(publish_payload["itemAddrDTO"]["city"], "杭州市")

    def test_location_candidates_accept_current_selected_poi_shape(self):
        platform = FakeSession(
            posts=[
                success(
                    {
                        "selectedPoi": {
                            "area": "江宁区",
                            "city": "南京市",
                            "divisionId": 320115,
                            "longitude": 118.8,
                            "latitude": 31.9,
                            "prov": "江苏省",
                        }
                    }
                )
            ]
        )
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            sign_handler=lambda *_args: "sign",
        )
        try:
            candidates = publisher.list_location_candidates()
        finally:
            publisher.close()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source"], "platform_selected")
        self.assertEqual(candidates[0]["poi_name"], "江宁区")

    @patch("integrations.xianyu_core.product_publisher.time.sleep", return_value=None)
    def test_location_retries_with_fresh_sessions(self, _sleep):
        sessions = [
            FakeSession(posts=[requests.exceptions.SSLError("tls eof")]),
            FakeSession(posts=[requests.Timeout("location timeout")]),
            FakeSession(
                posts=[
                    success(
                        {
                            "selectedPoi": {
                                "area": "江宁区",
                                "city": "南京市",
                                "divisionId": 320115,
                                "longitude": 118.8,
                                "latitude": 31.9,
                                "prov": "江苏省",
                            }
                        }
                    )
                ]
            ),
        ]
        created_sessions = list(sessions)
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: sessions.pop(0),
            sign_handler=lambda *_args: "sign",
        )
        try:
            candidates = publisher.list_location_candidates()
        finally:
            publisher.close()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["poi_name"], "江宁区")
        self.assertTrue(created_sessions[0].closed)
        self.assertTrue(created_sessions[1].closed)
        self.assertTrue(created_sessions[2].closed)
        self.assertEqual(_sleep.call_count, 2)

    @patch("integrations.xianyu_core.product_publisher.time.sleep", return_value=None)
    def test_location_network_failure_is_classified_as_retryable(self, _sleep):
        sessions = [
            FakeSession(posts=[requests.Timeout("location timeout")])
            for _ in range(3)
        ]
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: sessions.pop(0),
            sign_handler=lambda *_args: "sign",
        )
        try:
            with self.assertRaises(ProductPublishError) as raised:
                publisher.list_location_candidates()
        finally:
            publisher.close()

        self.assertEqual(raised.exception.kind, "network")
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(_sleep.call_count, 2)

    def test_location_http_error_is_not_blindly_retried(self):
        platform = FakeSession(posts=[requests.HTTPError("HTTP 400")])
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            sign_handler=lambda *_args: "sign",
        )
        try:
            with self.assertRaises(ProductPublishError) as raised:
                publisher.list_location_candidates()
        finally:
            publisher.close()

        self.assertFalse(raised.exception.retryable)
        self.assertEqual(len(platform.post_calls), 1)

    @patch.object(MtopProductPublisher, "_validate_public_url", return_value=None)
    def test_publish_timeout_requires_verification_and_is_not_retryable(self, _validate):
        responses = publisher_responses()
        responses[3] = requests.Timeout("read timeout")
        platform = FakeSession(posts=responses)
        downloader = FakeSession(get_response=FakeResponse(body=jpeg_bytes()))
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            download_session_factory=lambda: downloader,
            sign_handler=lambda *_args: "sign",
        )

        with self.assertRaises(ProductPublishError) as raised:
            publisher.publish(self.make_request())

        self.assertEqual(raised.exception.kind, "publish_result_unknown")
        self.assertTrue(raised.exception.uncertain)
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(
            len([call for call in platform.post_calls if "idleitem.publish" in call[0]]),
            1,
        )

    def test_local_asset_bytes_skip_external_download(self):
        platform = FakeSession(posts=publisher_responses())
        downloader = FakeSession(get_response=FakeResponse(body=jpeg_bytes()))
        raw = jpeg_bytes()
        image_ref = "asset:local-image"
        publisher = MtopProductPublisher(
            AccountConfig(account_id="account-1", cookie="unb=10001; _m_h5_tk=oldtoken_1"),
            session_factory=lambda: platform,
            download_session_factory=lambda: downloader,
            sign_handler=lambda *_args: "sign",
        )
        request = replace(
            self.make_request(),
            image_urls=(image_ref,),
            image_data={
                image_ref: ProductImageData(
                    data=raw,
                    filename="local.jpg",
                    mime_type="image/jpeg",
                    width=32,
                    height=24,
                    size_bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            },
        )

        result = publisher.publish(request)

        self.assertTrue(result.verified)
        self.assertEqual(downloader.get_calls, [])


class ProductImageStorageTests(unittest.TestCase):
    def test_storage_normalizes_reads_and_deletes_account_asset(self):
        raw = io.BytesIO()
        Image.new("RGBA", (40, 30), (0, 128, 255, 128)).save(raw, format="PNG")
        with tempfile.TemporaryDirectory() as directory:
            storage = ProductImageStorage(directory)
            saved = storage.save("account-1", raw.getvalue())

            content = storage.read("account-1", saved.asset_id)
            self.assertEqual(content, saved.prepared.data)
            self.assertTrue(storage.path("account-1", saved.asset_id).is_file())
            self.assertEqual(saved.prepared.mime_type, "image/jpeg")
            storage.delete("account-1", saved.asset_id)
            self.assertFalse(storage.path("account-1", saved.asset_id).exists())

    def test_storage_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = ProductImageStorage(directory)
            with self.assertRaises(ValueError):
                storage.path("../other", "asset")


class ProductImageArchiveTests(unittest.TestCase):
    @staticmethod
    def archive_bytes(entries: list[tuple[str, bytes]]) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, content in entries:
                archive.writestr(filename, content)
        return output.getvalue()

    def test_imports_images_in_natural_order_and_ignores_other_files(self):
        raw = jpeg_bytes()
        archive_raw = self.archive_bytes(
            [
                ("主图/010-last.jpg", raw),
                ("SKU明细.xls", b"not-an-image"),
                ("主图/002-middle.jpg", raw),
                ("主图/001-cover.jpg", raw),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            storage = ProductImageStorage(directory)
            result = import_product_image_archive(
                io.BytesIO(archive_raw),
                account_id="account-1",
                limit=9,
                storage=storage,
            )

            self.assertEqual(
                [image.original_filename for image in result.images],
                ["001-cover.jpg", "002-middle.jpg", "010-last.jpg"],
            )
            self.assertEqual(result.ignored_non_image_count, 1)
            self.assertEqual(result.rejected_images, ())
            self.assertEqual(result.skipped_limit_count, 0)
            self.assertTrue(
                all(storage.path("account-1", image.stored.asset_id).is_file() for image in result.images)
            )

    def test_skips_invalid_images_and_stops_at_import_limit(self):
        raw = jpeg_bytes()
        archive_raw = self.archive_bytes(
            [
                ("001-invalid.jpg", b"not-an-image"),
                ("002-valid.jpg", raw),
                ("003-valid.jpg", raw),
                ("004-over-limit.jpg", raw),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            result = import_product_image_archive(
                io.BytesIO(archive_raw),
                account_id="account-1",
                limit=2,
                storage=ProductImageStorage(directory),
            )

            self.assertEqual(len(result.images), 2)
            self.assertEqual(len(result.rejected_images), 1)
            self.assertEqual(result.rejected_images[0].filename, "001-invalid.jpg")
            self.assertEqual(result.skipped_limit_count, 1)

    def test_rejects_unsafe_paths_and_invalid_zip_files(self):
        unsafe = self.archive_bytes([("../image.jpg", jpeg_bytes())])
        with tempfile.TemporaryDirectory() as directory:
            storage = ProductImageStorage(directory)
            with self.assertRaises(ProductImageArchiveError):
                import_product_image_archive(
                    io.BytesIO(unsafe),
                    account_id="account-1",
                    limit=9,
                    storage=storage,
                )
            with self.assertRaises(ProductImageArchiveError):
                import_product_image_archive(
                    io.BytesIO(b"not-a-zip"),
                    account_id="account-1",
                    limit=9,
                    storage=storage,
                )


class ProductPublishStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.session_factory = factory
        self.store = AccountStore(session_factory=factory, initialize=False)
        self.account = await self.store.create_account(
            AccountCreatePayload(
                account_name="publish-account",
                cookie="unb=10001; _m_h5_tk=oldtoken_1; keep=value",
                enabled=True,
            )
        )

    async def asyncTearDown(self):
        self.engine.dispose()

    async def test_task_freezes_draft_and_idempotency_returns_same_task(self):
        draft = await self.store.create_product_draft(
            self.account.account_id,
            ProductDraftCreatePayload(
                title="旧标题",
                description="旧描述",
                price="19.90",
                original_price="29.90",
                stock=1,
                category_hint="手机配件",
                images=["https://example.com/item.jpg"],
                delivery_choice="fixed",
                post_price="5.00",
                can_self_pickup=True,
                location_mode="selected",
                location=ProductLocationPayload(
                    prov="浙江省",
                    city="杭州市",
                    area="西湖区",
                    division_id="330106",
                    longitude=120.1,
                    latitude=30.2,
                    poi_id="poi-hz",
                    poi_name="西湖区",
                ),
            ),
        )
        assert draft is not None
        request = ProductPublishTaskCreatePayload(
            draft_id=draft.draft_id,
            mode="platform_api",
            idempotency_key="request-123456",
        )
        first = await self.store.create_product_publish_task(self.account.account_id, request)
        assert first is not None
        await self.store.update_product_draft(
            self.account.account_id,
            draft.draft_id,
            ProductDraftUpdatePayload(title="新标题"),
        )
        second = await self.store.create_product_publish_task(self.account.account_id, request)

        assert second is not None
        self.assertEqual(second.task_id, first.task_id)
        self.assertEqual(first.snapshot["title"], "旧标题")
        self.assertEqual(first.snapshot["delivery_choice"], "fixed")
        self.assertEqual(first.snapshot["post_price"], "5.00")
        self.assertEqual(first.snapshot["location"]["division_id"], "330106")

    async def test_direct_publish_job_retains_assets_without_creating_draft(self):
        raw = jpeg_bytes()
        asset = await self.store.create_product_image_asset(
            account_id=self.account.account_id,
            asset_id="direct-asset",
            original_filename="direct.jpg",
            mime_type="image/jpeg",
            width=32,
            height=24,
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            upload_session_id="upload-session-123",
        )
        assert asset is not None
        payload = ProductPublishJobCreatePayload(
            title="直接发布商品",
            description="不经过草稿",
            price="18.80",
            images=[asset.image_ref],
            upload_session_id="upload-session-123",
            idempotency_key="direct-publish-request",
        )
        first = await self.store.create_direct_product_publish_task(self.account.account_id, payload)
        repeated = await self.store.create_direct_product_publish_task(self.account.account_id, payload)

        assert first is not None and repeated is not None
        self.assertEqual(first.task_id, repeated.task_id)
        self.assertIsNone(first.draft_id)
        self.assertEqual(first.snapshot["title"], "直接发布商品")
        self.assertEqual(await self.store.list_product_drafts(self.account.account_id), [])
        self.assertEqual(
            await self.store.delete_product_image_asset(self.account.account_id, asset.asset_id),
            "in_use",
        )
        with self.session_factory() as session:
            link = session.query(ProductPublishTaskAssetORM).filter_by(task_id=first.task_id).one()
            self.assertEqual(link.asset_id, asset.asset_id)

    async def test_direct_publish_rejects_disabled_account(self):
        disabled = await self.store.create_account(
            AccountCreatePayload(
                account_name="disabled-publish-account",
                cookie="unb=10002; _m_h5_tk=token_1",
                enabled=False,
            )
        )
        with self.assertRaisesRegex(ValueError, "账户已禁用"):
            await self.store.create_direct_product_publish_task(
                disabled.account_id,
                ProductPublishJobCreatePayload(
                    title="不应发布",
                    price="10",
                    images=["asset:not-used"],
                    idempotency_key="disabled-publish-request",
                ),
            )

    async def test_retry_publish_job_copies_snapshot_and_attempt_lineage(self):
        raw = jpeg_bytes()
        asset = await self.store.create_product_image_asset(
            account_id=self.account.account_id,
            asset_id="retry-asset",
            original_filename="retry.jpg",
            mime_type="image/jpeg",
            width=32,
            height=24,
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            upload_session_id="retry-session-123",
        )
        assert asset is not None
        source = await self.store.create_direct_product_publish_task(
            self.account.account_id,
            ProductPublishJobCreatePayload(
                title="网络失败商品",
                price="20",
                images=[asset.image_ref],
                upload_session_id="retry-session-123",
                idempotency_key="retry-source-request",
            ),
        )
        assert source is not None
        source = await self.store.update_product_publish_task_after_execute(
            account_id=self.account.account_id,
            task_id=source.task_id,
            status="failed",
            phase="failed",
            failure_kind="network",
            error="timeout",
            retryable=True,
            result_certainty="confirmed_failed",
        )
        assert source is not None
        retried = await self.store.retry_product_publish_task(
            self.account.account_id,
            source.task_id,
            ProductPublishRetryPayload(idempotency_key="retry-attempt-request"),
        )

        assert retried is not None
        self.assertEqual(retried.retry_of_task_id, source.task_id)
        self.assertEqual(retried.attempt_no, 2)
        self.assertEqual(retried.snapshot["title"], source.snapshot["title"])
        self.assertNotEqual(retried.snapshot["unique_code"], source.snapshot["unique_code"])

    async def test_abandoned_upload_session_is_cleaned(self):
        raw = jpeg_bytes()
        asset = await self.store.create_product_image_asset(
            account_id=self.account.account_id,
            asset_id="abandoned-asset",
            original_filename="unused.jpg",
            mime_type="image/jpeg",
            width=32,
            height=24,
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            upload_session_id="abandoned-session",
        )
        assert asset is not None
        deleted = await self.store.cleanup_product_upload_session(
            self.account.account_id,
            "abandoned-session",
        )
        self.assertEqual(deleted, [asset.asset_id])
        self.assertIsNone(await self.store.get_product_image_asset(self.account.account_id, asset.asset_id))

    async def test_administrative_regions_are_materialized_and_publishable(self):
        catalog = product_region_catalog.catalog_payload()
        self.assertEqual(len(catalog.items), 3237)
        self.assertEqual(product_region_catalog.location_for("110106").city, "北京市")

        group = await self.store.create_publish_address_group(
            PublishAddressGroupCreatePayload(
                name="全国区域组",
                account_ids=[self.account.account_id],
                avoid_recent_count=1,
            )
        )
        beijing = await self.store.replace_publish_address_regions(
            group.group_id,
            PublishAddressRegionSelectionPayload(region_codes=["110000"]),
        )
        assert beijing is not None
        self.assertEqual(beijing.address_count, 16)

        groups = await self.store.list_publish_address_groups(self.account.account_id)
        self.assertEqual(groups[0].address_count, 16)
        draft = await self.store.create_product_draft(
            self.account.account_id,
            ProductDraftCreatePayload(
                title="区域随机商品",
                price="10",
                images=["https://example.com/item.jpg"],
                location_mode="group_random",
                location_group_id=group.group_id,
            ),
        )
        assert draft is not None
        task = await self.store.create_product_publish_task(
            self.account.account_id,
            ProductPublishTaskCreatePayload(
                draft_id=draft.draft_id,
                mode="platform_api",
                idempotency_key="administrative-region-random",
            ),
        )
        assert task is not None
        self.assertEqual(task.snapshot["location"]["prov"], "北京市")
        self.assertEqual(task.snapshot["location"]["poi_id"], "")
        self.assertTrue(task.snapshot["location"]["division_id"].startswith("11"))

        hangzhou = await self.store.replace_publish_address_regions(
            group.group_id,
            PublishAddressRegionSelectionPayload(region_codes=["330106"]),
        )
        assert hangzhou is not None
        self.assertEqual(hangzhou.region_codes, ["330106"])
        groups = await self.store.list_publish_address_groups(self.account.account_id)
        self.assertEqual(groups[0].address_count, 1)

    async def test_direct_region_draft_uses_canonical_catalog_location(self):
        draft = await self.store.create_product_draft(
            self.account.account_id,
            ProductDraftCreatePayload(
                title="指定区域商品",
                price="10",
                images=["https://example.com/item.jpg"],
                location_mode="region",
                location=ProductLocationPayload(
                    prov="伪造省份",
                    city="伪造城市",
                    area="伪造区域",
                    division_id="330106",
                    longitude=0,
                    latitude=0,
                    poi_name="伪造位置",
                ),
            ),
        )
        assert draft is not None and draft.location is not None
        self.assertEqual(draft.location.prov, "浙江省")
        self.assertEqual(draft.location.city, "杭州市")
        self.assertEqual(draft.location.area, "西湖区")
        self.assertNotEqual(draft.location.longitude, 0)

    async def test_random_address_group_avoids_recent_and_freezes_task_snapshot(self):
        locations = [
            ProductLocationOptionPayload(
                location_id=f"location-{index}",
                label=f"浙江省 杭州市 地址 {index}",
                source="platform_common",
                prov="浙江省",
                city="杭州市",
                area="西湖区",
                division_id="330106",
                longitude=120.10 + index / 100,
                latitude=30.20 + index / 100,
                poi_id=f"poi-{index}",
                poi_name=f"地址 {index}",
            )
            for index in (1, 2)
        ]
        await self.store.upsert_product_platform_locations(self.account.account_id, locations)
        group = await self.store.create_publish_address_group(
            PublishAddressGroupCreatePayload(
                name="杭州随机地址",
                account_ids=[self.account.account_id],
                avoid_recent_count=1,
            )
        )
        for location in locations:
            await self.store.create_publish_address(
                group.group_id,
                PublishAddressCreatePayload(
                    source_account_id=self.account.account_id,
                    location_id=location.location_id,
                ),
            )
        draft = await self.store.create_product_draft(
            self.account.account_id,
            ProductDraftCreatePayload(
                title="随机地址商品",
                price="10",
                images=["https://example.com/item.jpg"],
                location_mode="group_random",
                location_group_id=group.group_id,
            ),
        )
        assert draft is not None
        first_request = ProductPublishTaskCreatePayload(
            draft_id=draft.draft_id,
            mode="platform_api",
            idempotency_key="random-location-1",
        )
        first = await self.store.create_product_publish_task(self.account.account_id, first_request)
        repeated = await self.store.create_product_publish_task(self.account.account_id, first_request)
        second = await self.store.create_product_publish_task(
            self.account.account_id,
            ProductPublishTaskCreatePayload(
                draft_id=draft.draft_id,
                mode="platform_api",
                idempotency_key="random-location-2",
            ),
        )

        assert first is not None and repeated is not None and second is not None
        self.assertEqual(repeated.task_id, first.task_id)
        self.assertEqual(first.snapshot["location_group_id"], group.group_id)
        self.assertNotEqual(
            first.snapshot["selected_address_id"],
            second.snapshot["selected_address_id"],
        )
        self.assertNotEqual(first.snapshot["location"]["poi_id"], second.snapshot["location"]["poi_id"])

        await self.store.update_product_publish_task_after_execute(
            account_id=self.account.account_id,
            task_id=first.task_id,
            status="success",
            phase="completed",
        )
        with self.session_factory() as session:
            usage = session.query(PublishAddressUsageORM).filter_by(task_id=first.task_id).one()
            self.assertEqual(usage.status, "success")

    async def test_idempotency_is_account_scoped_and_background_task_is_deduped(self):
        second_account = await self.store.create_account(
            AccountCreatePayload(
                account_name="publish-account-two",
                cookie="unb=10002; _m_h5_tk=oldtoken_1",
                enabled=False,
            )
        )
        first_draft = await self.store.create_product_draft(
            self.account.account_id,
            ProductDraftCreatePayload(title="账号一", price="10", images=["https://example.com/1.jpg"]),
        )
        second_draft = await self.store.create_product_draft(
            second_account.account_id,
            ProductDraftCreatePayload(title="账号二", price="20", images=["https://example.com/2.jpg"]),
        )
        assert first_draft is not None and second_draft is not None
        shared_key = "shared-request-key"
        first_task = await self.store.create_product_publish_task(
            self.account.account_id,
            ProductPublishTaskCreatePayload(
                draft_id=first_draft.draft_id,
                mode="platform_api",
                idempotency_key=shared_key,
            ),
        )
        second_task = await self.store.create_product_publish_task(
            second_account.account_id,
            ProductPublishTaskCreatePayload(
                draft_id=second_draft.draft_id,
                mode="platform_api",
                idempotency_key=shared_key,
            ),
        )
        assert first_task is not None and second_task is not None
        self.assertNotEqual(first_task.task_id, second_task.task_id)

        background_payload = BackgroundTaskCreatePayload(
            account_id=self.account.account_id,
            task_type="product.publish_task",
            dedupe_key=f"product-publish:{first_task.task_id}",
            payload={"account_id": self.account.account_id, "task_id": first_task.task_id},
        )
        first_background = await self.store.create_background_task(background_payload)
        second_background = await self.store.create_background_task(background_payload)
        assert first_background is not None and second_background is not None
        self.assertEqual(first_background.task_id, second_background.task_id)

    async def test_publish_cookie_delta_merges_onto_latest_cookie(self):
        changed = await merge_account_cookie_updates(
            self.store,
            self.account.account_id,
            {"_m_h5_tk": "newtoken_2", "new_cookie": "new-value"},
        )
        latest = await self.store.get_account(self.account.account_id)

        assert latest is not None
        self.assertTrue(changed)
        self.assertIn("keep=value", latest.cookie)
        self.assertIn("_m_h5_tk=newtoken_2", latest.cookie)
        self.assertEqual(latest.cookie_update_source, "product_publish")

    async def test_location_service_uses_fresh_persistent_cache(self):
        publisher_calls = 0

        class LocationPublisher:
            def __init__(self, _account):
                nonlocal publisher_calls
                publisher_calls += 1

            def list_location_candidates(self, **_kwargs):
                return [location_candidate()]

            def cookie_updates(self):
                return {}

            def close(self):
                return None

        live = await list_platform_product_locations(
            self.store,
            self.account.account_id,
            publisher_factory=LocationPublisher,
        )
        cached = await list_platform_product_locations(
            self.store,
            self.account.account_id,
            publisher_factory=LocationPublisher,
        )

        self.assertEqual(live.data_source, "live")
        self.assertEqual(cached.data_source, "cache")
        self.assertEqual(cached.items[0].poi_name, "测试地址")
        self.assertEqual(publisher_calls, 1)

    async def test_location_service_falls_back_to_recent_stale_cache_on_network_error(self):
        class LivePublisher:
            def __init__(self, _account):
                pass

            def list_location_candidates(self, **_kwargs):
                return [location_candidate()]

            def cookie_updates(self):
                return {}

            def close(self):
                return None

        await list_platform_product_locations(
            self.store,
            self.account.account_id,
            publisher_factory=LivePublisher,
        )
        with self.session_factory() as session:
            cache = session.get(
                ProductLocationCacheORM,
                {
                    "account_id": self.account.account_id,
                    "cache_key": "118.7825:31.9163",
                },
            )
            assert cache is not None
            cache.fetched_at = cache.fetched_at - timedelta(minutes=20)
            session.commit()

        class FailingPublisher(LivePublisher):
            def list_location_candidates(self, **_kwargs):
                raise ProductPublishError("network", "tls eof", retryable=True)

        stale = await list_platform_product_locations(
            self.store,
            self.account.account_id,
            publisher_factory=FailingPublisher,
        )

        self.assertEqual(stale.data_source, "stale")
        self.assertEqual(stale.items[0].division_id, "320115")
        self.assertIsNotNone(stale.warning)

    async def test_location_service_does_not_hide_business_error_with_cache(self):
        class LivePublisher:
            def __init__(self, _account):
                pass

            def list_location_candidates(self, **_kwargs):
                return [location_candidate()]

            def cookie_updates(self):
                return {}

            def close(self):
                return None

        await list_platform_product_locations(
            self.store,
            self.account.account_id,
            publisher_factory=LivePublisher,
        )

        class AuthFailurePublisher(LivePublisher):
            def list_location_candidates(self, **_kwargs):
                raise ProductPublishError("auth", "cookie expired")

        with self.assertRaises(ProductPublishError) as raised:
            await list_platform_product_locations(
                self.store,
                self.account.account_id,
                force_refresh=True,
                publisher_factory=AuthFailurePublisher,
            )

        self.assertEqual(raised.exception.kind, "auth")

    async def test_worker_request_resolves_persisted_asset_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = ProductImageStorage(directory)
            stored = storage.save(self.account.account_id, jpeg_bytes())
            prepared = stored.prepared
            asset = await self.store.create_product_image_asset(
                account_id=self.account.account_id,
                asset_id=stored.asset_id,
                original_filename="商品图.jpg",
                mime_type=prepared.mime_type,
                width=prepared.width,
                height=prepared.height,
                size_bytes=prepared.size_bytes,
                sha256=prepared.sha256,
            )
            assert asset is not None
            snapshot = {
                "title": "测试商品",
                "description": "测试描述",
                "price": "19.90",
                "stock": 1,
                "images": [asset.image_ref],
                "delivery_choice": "free_shipping",
                "unique_code": "123456789012345678",
                "location": {
                    "prov": "浙江省",
                    "city": "杭州市",
                    "area": "西湖区",
                    "division_id": "330106",
                    "longitude": 120.1,
                    "latitude": 30.2,
                    "poi_id": "poi-hz",
                    "poi_name": "西湖区",
                },
            }
            with patch(
                "apps.api.xianyu_admin_api.product_publish_service.product_image_storage",
                storage,
            ):
                request = await _request_from_snapshot(
                    self.store,
                    self.account.account_id,
                    snapshot,
                    snapshot["unique_code"],
                )

            self.assertEqual(request.image_urls, (asset.image_ref,))
            self.assertEqual(request.image_data[asset.image_ref].sha256, prepared.sha256)
            self.assertEqual(request.location["division_id"], "330106")


if __name__ == "__main__":
    unittest.main()
