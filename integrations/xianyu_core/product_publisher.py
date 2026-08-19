"""Account-scoped HTTP/MTOP product publishing adapter."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import random
import socket
import time
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from .client import IMAGE_UPLOAD_URL
from .images import MAX_IMAGE_INPUT_BYTES, ImageValidationError, prepare_image
from .models import AccountConfig
from .product_models import (
    DELIVERY_CHOICES,
    ProductPublishError,
    ProductImageData,
    ProductPublishRequest,
    ProductPublishResult,
    PublishedImage,
)
from .proxy import build_socks_proxy_url
from .upstream import load_upstream_modules


APP_KEY = "34839810"
MTOP_ROOT = "https://h5api.m.goofish.com/h5"
TOKEN_ERROR_MARKERS = (
    "FAIL_SYS_TOKEN_EXOIRED",
    "FAIL_SYS_TOKEN_EXPIRED",
    "FAIL_SYS_ILLEGAL_ACCESS",
    "FAIL_SYS_SESSION_EXPIRED",
)
RISK_MARKERS = ("RGV587", "RISK", "CAPTCHA", "VALIDATE")
CATEGORY_ERROR = "FAIL_BIZ_CHANNEL_CAT_ID_PATH_QUERY_ERROR"
LOCATION_MAX_ATTEMPTS = 3
LOCATION_RETRY_DELAYS = (0.5, 1.5)
LOCATION_RETRY_HTTP_STATUSES = {502, 503, 504}

logger = logging.getLogger(__name__)

ProgressHandler = Callable[[str], None]
SignHandler = Callable[[str, str, str], str]


class MtopProductPublisher:
    """Publish one product without sharing the long-lived IM HTTP session."""

    def __init__(
        self,
        account: AccountConfig,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
        download_session_factory: Callable[[], requests.Session] = requests.Session,
        sign_handler: SignHandler | None = None,
        progress_handler: ProgressHandler | None = None,
        timeout: tuple[float, float] = (10.0, 40.0),
    ) -> None:
        self.account = account
        self._session_factory = session_factory
        self._download_session_factory = download_session_factory
        self._timeout = timeout
        self._progress_handler = progress_handler
        self._sign_handler = sign_handler

        cookies = self._parse_cookie(account.cookie)
        if not cookies.get("unb"):
            raise ProductPublishError("auth", "Cookie 缺少 unb，无法发布商品")
        self._initial_cookies = dict(cookies)
        proxy_url = build_socks_proxy_url(account.proxy)
        self._proxy_url = proxy_url
        self._session = self._create_session(cookies)

    def close(self) -> None:
        self._session.close()

    def _create_session(self, cookies: Mapping[str, str]) -> requests.Session:
        session = self._session_factory()
        session.trust_env = False
        for key, value in cookies.items():
            session.cookies.set(key, value, domain=".goofish.com", path="/")
        session.headers.update(
            {
                "User-Agent": self.account.client_identity.user_agent,
                "Accept-Language": self.account.client_identity.accept_language,
                # The web publisher includes this trace context on MTOP calls. Without it,
                # the location endpoint can return only selectedPoi and omit common/nearby.
                "EagleEye-UserData": "spm-cnt=a21ybx",
            }
        )
        if self._proxy_url:
            session.proxies.update({"http": self._proxy_url, "https": self._proxy_url})
        return session

    def _reset_session(self) -> None:
        cookies = {cookie.name: cookie.value for cookie in self._session.cookies if cookie.value}
        self._session.close()
        self._session = self._create_session(cookies)

    def publish(self, request: ProductPublishRequest) -> ProductPublishResult:
        self._validate_request(request)
        try:
            self._progress("resolving_location")
            location = (
                self._validate_location(request.location)
                if request.location is not None
                else self.get_default_location()
            )

            images = []
            for index, image_url in enumerate(request.image_urls, start=1):
                self._progress(f"uploading_image:{index}/{len(request.image_urls)}")
                image_data = request.image_data.get(image_url)
                images.append(
                    self._upload_image_data(image_data)
                    if image_data is not None
                    else self._download_and_upload(image_url)
                )

            self._progress("resolving_category")
            category_response = self._recommend_category(request, images)
            category = self._extract_category(category_response)

            payload = self._build_publish_payload(request, images, category_response, category, location)
            self._progress("publishing")
            try:
                publish_response = self._post_mtop(
                    "mtop.idle.pc.idleitem.publish",
                    "1.0",
                    payload,
                    spm_pre="a21ybx.home.sidebar.1.46413da6EPl7v5",
                )
            except requests.RequestException as exc:
                raise ProductPublishError(
                    "publish_result_unknown",
                    "发布请求已发出但未收到明确结果，请先到闲鱼核对，禁止直接重试",
                    uncertain=True,
                    cookie_updates=self.cookie_updates(),
                ) from exc
            except ProductPublishError as exc:
                if exc.kind != "platform_response":
                    raise
                raise ProductPublishError(
                    "publish_result_unknown",
                    "发布接口返回内容无法解析，请先到闲鱼核对，禁止直接重试",
                    uncertain=True,
                    cookie_updates=self.cookie_updates(),
                ) from exc

            self._ensure_success(publish_response, operation="发布商品")
            item_id = self._find_item_id(publish_response.get("data"))
            if not item_id:
                raise ProductPublishError(
                    "publish_result_unknown",
                    "平台返回发布成功，但响应中没有商品 ID，请到闲鱼核对",
                    uncertain=True,
                    cookie_updates=self.cookie_updates(),
                    raw_response=publish_response,
                )

            self._progress("verifying")
            verified = self._verify_item(item_id)
            self._progress("completed" if verified else "verification_required")
            return ProductPublishResult(
                item_id=item_id,
                item_url=f"https://www.goofish.com/item?id={item_id}",
                verified=verified,
                cookie_updates=self.cookie_updates(),
                raw_response=publish_response,
            )
        except ProductPublishError as exc:
            exc.cookie_updates.update(self.cookie_updates())
            raise
        except ImageValidationError as exc:
            raise ProductPublishError("image_invalid", str(exc)) from exc
        except requests.RequestException as exc:
            raise ProductPublishError(
                "network",
                f"商品发布网络请求失败（{exc.__class__.__name__}）",
                retryable=True,
            ) from exc
        finally:
            self.close()

    def list_location_candidates(
        self,
        *,
        longitude: float = 118.78248347393424,
        latitude: float = 31.91629189813543,
    ) -> list[dict[str, Any]]:
        response: dict[str, Any] | None = None
        for attempt in range(1, LOCATION_MAX_ATTEMPTS + 1):
            started_at = time.monotonic()
            try:
                response = self._post_mtop(
                    "mtop.taobao.idle.local.poi.get",
                    "1.0",
                    {"longitude": longitude, "latitude": latitude},
                    spm_pre="a21ybx.item.sidebar.1.38262218ame5nr",
                )
                logger.info(
                    "Xianyu location request succeeded account=%s attempt=%s duration_ms=%s route=%s",
                    self.account.account_id,
                    attempt,
                    round((time.monotonic() - started_at) * 1000),
                    "proxy" if self._proxy_url else "direct",
                )
                break
            except requests.RequestException as exc:
                retryable = self._is_retryable_location_error(exc)
                logger.warning(
                    "Xianyu location request failed account=%s attempt=%s duration_ms=%s route=%s "
                    "error_type=%s retryable=%s",
                    self.account.account_id,
                    attempt,
                    round((time.monotonic() - started_at) * 1000),
                    "proxy" if self._proxy_url else "direct",
                    exc.__class__.__name__,
                    retryable,
                )
                if not retryable or attempt >= LOCATION_MAX_ATTEMPTS:
                    raise ProductPublishError(
                        "network",
                        f"获取宝贝所在地网络请求失败（{exc.__class__.__name__}），已尝试 {attempt} 次",
                        retryable=retryable,
                        cookie_updates=self.cookie_updates(),
                    ) from exc
                self._reset_session()
                delay = LOCATION_RETRY_DELAYS[attempt - 1] + random.uniform(0, 0.2)
                time.sleep(delay)
        assert response is not None
        self._ensure_success(response, operation="获取宝贝所在地")
        data = response.get("data") if isinstance(response, Mapping) else {}
        selected_poi = (data or {}).get("selectedPoi") if isinstance(data, Mapping) else None
        if isinstance(selected_poi, Mapping):
            try:
                selected_longitude = float(selected_poi.get("longitude"))
                selected_latitude = float(selected_poi.get("latitude"))
            except (TypeError, ValueError):
                selected_longitude = longitude
                selected_latitude = latitude
            if (
                abs(selected_longitude - longitude) > 0.05
                or abs(selected_latitude - latitude) > 0.05
            ):
                try:
                    centered_response = self._post_mtop(
                        "mtop.taobao.idle.local.poi.get",
                        "1.0",
                        {"longitude": selected_longitude, "latitude": selected_latitude},
                        spm_pre="a21ybx.item.sidebar.1.38262218ame5nr",
                    )
                    self._ensure_success(centered_response, operation="获取默认所在地附近地址")
                    centered_data = centered_response.get("data") or {}
                    if isinstance(centered_data, Mapping):
                        merged_data = dict(data) if isinstance(data, Mapping) else {}
                        for key in ("commonAddresses", "nearbyAddresses", "pois"):
                            values: list[object] = []
                            for source_data in (data, centered_data):
                                source_values = (
                                    source_data.get(key) if isinstance(source_data, Mapping) else None
                                )
                                if isinstance(source_values, list):
                                    values.extend(source_values)
                            if values:
                                merged_data[key] = values
                        merged_data["selectedPoi"] = centered_data.get("selectedPoi") or selected_poi
                        data = merged_data
                except (requests.RequestException, ProductPublishError):
                    logger.warning(
                        "Failed to load Xianyu locations around selected POI account=%s",
                        self.account.account_id,
                        exc_info=True,
                    )
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        sources: list[tuple[str, object]] = [
            ("commonAddresses", (data or {}).get("commonAddresses") or []),
            ("nearbyAddresses", (data or {}).get("nearbyAddresses") or []),
            ("pois", (data or {}).get("pois") or []),
        ]
        selected_poi = (data or {}).get("selectedPoi")
        if isinstance(selected_poi, Mapping):
            sources.insert(0, ("selectedPoi", [selected_poi]))
        for source_key, values in sources:
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, Mapping):
                    continue
                try:
                    location = self._validate_location(value)
                except ProductPublishError:
                    continue
                identity = json.dumps(location, ensure_ascii=False, sort_keys=True)
                location_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
                if location_id in seen:
                    continue
                seen.add(location_id)
                label_parts: list[str] = []
                for part in (
                    location["prov"],
                    location["city"],
                    location["area"],
                    location["poi_name"],
                ):
                    if part and part not in label_parts:
                        label_parts.append(part)
                candidates.append(
                    {
                        **location,
                        "location_id": location_id,
                        "label": " ".join(part for part in label_parts if part),
                        "source": (
                            "platform_common"
                            if source_key == "commonAddresses"
                            else "platform_selected"
                            if source_key == "selectedPoi"
                            else "platform_nearby"
                        ),
                    }
                )
        if not candidates:
            raise ProductPublishError("location", "账号未返回可用的宝贝所在地")
        return candidates

    @staticmethod
    def _is_retryable_location_error(exc: requests.RequestException) -> bool:
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            return exc.response.status_code in LOCATION_RETRY_HTTP_STATUSES
        return False

    def get_default_location(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.list_location_candidates()[0].items()
            if key not in {"location_id", "label", "source"}
        }

    def cookie_updates(self) -> dict[str, str]:
        current = {cookie.name: cookie.value for cookie in self._session.cookies}
        return {
            key: value
            for key, value in current.items()
            if value and self._initial_cookies.get(key) != value
        }

    def _download_and_upload(self, image_url: str) -> PublishedImage:
        current_url = image_url
        response: requests.Response | None = None
        # Product cookies are deliberately excluded from external image downloads.
        with self._download_session_factory() as downloader:
            downloader.trust_env = False
            downloader.headers.update(
                {"User-Agent": self.account.client_identity.user_agent}
            )
            if self._proxy_url:
                downloader.proxies.update({"http": self._proxy_url, "https": self._proxy_url})
            for _ in range(4):
                self._validate_public_url(current_url)
                response = downloader.get(
                    current_url,
                    stream=True,
                    allow_redirects=False,
                    timeout=self._timeout,
                )
                if response.is_redirect:
                    location = response.headers.get("Location")
                    response.close()
                    if not location:
                        raise ProductPublishError("image_download", "图片重定向缺少地址")
                    current_url = urljoin(current_url, location)
                    continue
                break
            else:
                raise ProductPublishError("image_download", "图片重定向次数过多")

            assert response is not None
            try:
                response.raise_for_status()
                content_length = int(response.headers.get("Content-Length") or 0)
                if content_length > MAX_IMAGE_INPUT_BYTES:
                    raise ProductPublishError("image_invalid", "图片大小不能超过 10 MB")
                body = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_IMAGE_INPUT_BYTES:
                        raise ProductPublishError("image_invalid", "图片大小不能超过 10 MB")
            finally:
                response.close()

        prepared = prepare_image(bytes(body))
        return self._upload_image_data(
            ProductImageData(
                data=prepared.data,
                filename=prepared.filename,
                mime_type=prepared.mime_type,
                width=prepared.width,
                height=prepared.height,
                size_bytes=prepared.size_bytes,
                sha256=prepared.sha256,
            )
        )

    def _upload_image_data(self, image: ProductImageData) -> PublishedImage:
        upload = self._session.post(
            IMAGE_UPLOAD_URL,
            params={"floderId": "0", "appkey": "xy_chat", "_input_charset": "utf-8"},
            files={"file": (image.filename, image.data, image.mime_type)},
            headers={"Accept": "*/*", "Origin": "https://www.goofish.com", "Referer": "https://www.goofish.com/"},
            timeout=self._timeout,
        )
        upload.raise_for_status()
        try:
            result = upload.json()
        except ValueError as exc:
            raise ProductPublishError("image_upload", "图片上传返回非 JSON 响应") from exc
        image_object = result.get("object") or result.get("data") or result.get("result") or {}
        uploaded_url = image_object.get("url") or result.get("url")
        if not uploaded_url:
            raise ProductPublishError("image_upload", f"图片上传失败: {self._error_message(result)}")
        width, height = image.width, image.height
        pix = str(image_object.get("pix") or "")
        if "x" in pix.lower():
            try:
                width, height = (int(value) for value in pix.lower().split("x", 1))
            except ValueError:
                pass
        return PublishedImage(url=str(uploaded_url), width=width, height=height)

    def _recommend_category(
        self, request: ProductPublishRequest, images: list[PublishedImage]
    ) -> dict[str, Any]:
        title = request.title
        description = request.description
        if request.category_hint:
            hint = request.category_hint.strip()
            if hint and hint not in title:
                title = f"{hint} {title}"
            description = f"类目提示：{hint}\n{description}"
        payload = {
            "title": title[:120],
            "lockCpv": False,
            "multiSKU": False,
            "publishScene": "mainPublish",
            "scene": "newPublishChoice",
            "description": description[:5000],
            "imageInfos": [
                self._image_payload(image, major=index == 0)
                for index, image in enumerate(images)
            ],
            "uniqueCode": request.unique_code,
        }
        response = self._post_mtop(
            "mtop.taobao.idle.kgraph.property.recommend",
            "2.0",
            payload,
            spm_pre="a21ybx.item.sidebar.1.67321598K9Vgx8",
        )
        self._ensure_success(response, operation="识别商品类目")
        return response

    def _post_mtop(
        self,
        api_name: str,
        version: str,
        payload: Mapping[str, Any],
        *,
        spm_pre: str,
        spm_cnt: str = "a21ybx.publish.0.0",
        allow_token_retry: bool = True,
        extra_params: Mapping[str, str] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        tracking_log_prefix: str | None = "publish",
    ) -> dict[str, Any]:
        data_value = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time() * 1000))
        token = self._cookie_value("_m_h5_tk").split("_", 1)[0]
        if not token:
            raise ProductPublishError("auth", "Cookie 缺少 _m_h5_tk，无法生成发布签名")
        if self._sign_handler is None:
            self._sign_handler = load_upstream_modules().generate_sign
        params = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": timestamp,
            "sign": self._sign_handler(timestamp, token, data_value),
            "v": version,
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": api_name,
            "sessionOption": "AutoLoginOnly",
        }
        if spm_cnt:
            params["spm_cnt"] = spm_cnt
        if spm_pre:
            params["spm_pre"] = spm_pre
        if tracking_log_prefix:
            params["log_id"] = f"{tracking_log_prefix}{timestamp}"
        if extra_params:
            params.update(extra_params)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self._session.post(
            f"{MTOP_ROOT}/{api_name}/{version}/",
            params=params,
            data={"data": data_value},
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError as exc:
            raise ProductPublishError("platform_response", f"{api_name} 返回非 JSON 响应") from exc
        if allow_token_retry and self._contains_marker(result, TOKEN_ERROR_MARKERS):
            return self._post_mtop(
                api_name,
                version,
                payload,
                spm_pre=spm_pre,
                spm_cnt=spm_cnt,
                allow_token_retry=False,
                extra_params=extra_params,
                extra_headers=extra_headers,
                tracking_log_prefix=tracking_log_prefix,
            )
        return result

    def _verify_item(self, item_id: str) -> bool:
        try:
            result = self._post_mtop(
                "mtop.idle.web.xyh.item.list",
                "1.0",
                {
                    "needGroupInfo": False,
                    "pageNumber": 1,
                    "pageSize": 20,
                    "groupName": "在售",
                    "groupId": "58877261",
                    "defaultGroup": True,
                    "userId": self._cookie_value("unb"),
                },
                spm_pre="a21ybx.collection.menu.1.272b5141NafCNK",
                spm_cnt="a21ybx.im.0.0",
            )
            if not self._is_success(result):
                return False
            return self._find_item_id(result.get("data"), expected=item_id) == item_id
        except (ProductPublishError, requests.RequestException):
            return False

    def _build_publish_payload(
        self,
        request: ProductPublishRequest,
        images: list[PublishedImage],
        category_response: Mapping[str, Any],
        category: Mapping[str, str],
        location: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "freebies": False,
            "itemTypeStr": "b",
            "quantity": str(request.stock),
            "simpleItem": "true",
            "imageInfoDOList": [
                self._image_payload(image, major=index == 0)
                for index, image in enumerate(images)
            ],
            "itemTextDTO": {
                "desc": request.description,
                "title": request.title,
                "titleDescSeparate": request.description != request.title,
            },
            "itemLabelExtList": self._build_labels(category_response),
            "itemPriceDTO": {},
            "userRightsProtocols": [{"enable": False, "serviceCode": "SKILL_PLAY_NO_MIND"}],
            "itemPostFeeDTO": {
                "canFreeShipping": False,
                "supportFreight": False,
                "onlyTakeSelf": False,
            },
            "itemAddrDTO": {
                "area": location.get("area", ""),
                "city": location.get("city", ""),
                "divisionId": location.get("division_id", ""),
                "gps": f'{location.get("longitude")},{location.get("latitude")}',
                "poiId": location.get("poi_id", ""),
                "poiName": location.get("poi_name", ""),
                "prov": location.get("prov", ""),
            },
            "defaultPrice": request.price is None,
            "itemCatDTO": dict(category),
            "uniqueCode": request.unique_code,
            "sourceId": "pcMainPublish",
            "bizcode": "pcMainPublish",
            "publishScene": "pcMainPublish",
        }
        if request.price is not None:
            payload["itemPriceDTO"]["priceInCent"] = self._to_cents(request.price)
        if request.original_price is not None:
            payload["itemPriceDTO"]["origPriceInCent"] = self._to_cents(request.original_price)

        post_fee = payload["itemPostFeeDTO"]
        if request.delivery_choice == "free_shipping":
            post_fee.update({"canFreeShipping": True, "supportFreight": True})
        elif request.delivery_choice == "distance":
            post_fee.update({"supportFreight": True, "templateId": "-100"})
        elif request.delivery_choice == "fixed":
            post_fee.update(
                {
                    "supportFreight": True,
                    "templateId": "0",
                    "postPriceInCent": self._to_cents(request.post_price or Decimal("0")),
                }
            )
        elif request.delivery_choice == "pickup_only":
            post_fee.update({"templateId": "0", "onlyTakeSelf": True})
            payload["onlyTakeSelf"] = True
        if request.can_self_pickup:
            # The platform keeps optional pickup at the item level. Setting the
            # post-fee flag here would replace the selected freight mode with pickup-only.
            payload["onlyTakeSelf"] = True
        return payload

    @classmethod
    def _build_labels(cls, response: Mapping[str, Any]) -> list[dict[str, Any]]:
        labels = []
        data = response.get("data") if isinstance(response, Mapping) else {}
        for card in (data or {}).get("cardList") or []:
            card_data = card.get("cardData") or {}
            selected = next((value for value in card_data.get("valuesList") or [] if value.get("isClicked")), None)
            if not selected:
                continue
            cat_name = selected.get("catName") or selected.get("channelCatName")
            channel_id = selected.get("channelCatId")
            if not cat_name or not channel_id:
                continue
            labels.append(
                {
                    "channelCateName": cat_name,
                    "channelCateId": channel_id,
                    "tbCatId": selected.get("tbCatId"),
                    "labelType": "common",
                    "propertyName": card_data.get("propertyName"),
                    "isUserClick": "1",
                    "from": "newPublishChoice",
                    "propertyId": card_data.get("propertyId"),
                    "labelFrom": "newPublish",
                    "text": cat_name,
                    "properties": f'{card_data.get("propertyId")}##{card_data.get("propertyName")}:{channel_id}##{cat_name}',
                }
            )
        return labels

    @classmethod
    def _extract_category(cls, response: Mapping[str, Any]) -> dict[str, str]:
        data = response.get("data") if isinstance(response, Mapping) else {}
        source = (data or {}).get("categoryPredictResult") or {}
        category = {
            "catId": str(source.get("catId") or source.get("cat_id") or ""),
            "catName": str(source.get("catName") or source.get("cat_name") or ""),
            "channelCatId": str(source.get("channelCatId") or source.get("channel_cat_id") or ""),
            "tbCatId": str(source.get("tbCatId") or source.get("tb_cat_id") or ""),
        }
        missing = [key for key, value in category.items() if not value]
        if missing:
            raise ProductPublishError("category", f"自动识别类目不完整，缺少: {', '.join(missing)}")
        return category

    @staticmethod
    def _extract_location(response: Mapping[str, Any]) -> Mapping[str, Any]:
        MtopProductPublisher._ensure_success(response, operation="获取默认地址")
        data = response.get("data") if isinstance(response, Mapping) else {}
        addresses = (data or {}).get("commonAddresses") or []
        if not addresses:
            raise ProductPublishError("location", "账号未配置默认发货地址")
        return MtopProductPublisher._validate_location(addresses[0])

    @staticmethod
    def _validate_location(location: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(location, Mapping):
            raise ProductPublishError("location", "宝贝所在地格式无效")
        normalized = {
            "prov": str(location.get("prov") or "").strip(),
            "city": str(location.get("city") or "").strip(),
            "area": str(location.get("area") or "").strip(),
            "division_id": str(location.get("division_id") or location.get("divisionId") or "").strip(),
            "longitude": location.get("longitude"),
            "latitude": location.get("latitude"),
            "poi_id": str(location.get("poi_id") or location.get("poiId") or "").strip(),
            "poi_name": str(
                location.get("poi_name")
                or location.get("poiName")
                or location.get("poi")
                or location.get("area")
                or location.get("city")
                or ""
            ).strip(),
        }
        missing = [
            key
            for key in ("prov", "city", "division_id", "longitude", "latitude", "poi_name")
            if normalized[key] in (None, "")
        ]
        if missing:
            raise ProductPublishError("location", f"宝贝所在地信息不完整，缺少: {', '.join(missing)}")
        try:
            normalized["longitude"] = float(normalized["longitude"])
            normalized["latitude"] = float(normalized["latitude"])
        except (TypeError, ValueError) as exc:
            raise ProductPublishError("location", "宝贝所在地经纬度无效") from exc
        return normalized

    @staticmethod
    def _image_payload(image: PublishedImage, *, major: bool = False) -> dict[str, Any]:
        return {
            "extraInfo": {"isH": "false", "isT": "false", "raw": "false"},
            "isQrCode": False,
            "url": image.url,
            "heightSize": image.height,
            "widthSize": image.width,
            "major": major,
            "type": 0,
            "status": "done",
        }

    @staticmethod
    def _validate_request(request: ProductPublishRequest) -> None:
        if not 1 <= len(request.image_urls) <= 9:
            raise ProductPublishError("validation", "商品图片数量必须为 1 到 9 张")
        if not request.unique_code:
            raise ProductPublishError("validation", "发布任务缺少唯一编码")
        if request.stock < 1:
            raise ProductPublishError("validation", "商品库存必须大于 0")
        if request.delivery_choice not in DELIVERY_CHOICES:
            raise ProductPublishError("validation", "不支持的运费方式")
        if request.delivery_choice == "fixed" and request.post_price is None:
            raise ProductPublishError("validation", "固定运费方式必须填写邮费")

    @staticmethod
    def _validate_public_url(value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ProductPublishError("image_url", "图片地址必须是有效的 HTTP/HTTPS URL")
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise ProductPublishError("image_url", f"无法解析图片地址: {parsed.hostname}") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ProductPublishError("image_url", "图片地址不能指向内网或本机")

    @staticmethod
    def _to_cents(value: Decimal) -> str:
        return str(int((value * 100).quantize(Decimal("1"))))

    @staticmethod
    def _is_success(response: Mapping[str, Any]) -> bool:
        ret = response.get("ret") if isinstance(response, Mapping) else None
        return isinstance(ret, list) and any(str(value).startswith("SUCCESS::") for value in ret)

    @classmethod
    def _ensure_success(cls, response: Mapping[str, Any], *, operation: str) -> None:
        if cls._is_success(response):
            return
        message = cls._error_message(response)
        if CATEGORY_ERROR in message:
            raise ProductPublishError("category", "闲鱼类目识别失败，请调整标题、类目提示或首图后重试", raw_response=response)
        if cls._contains_marker(response, RISK_MARKERS):
            raise ProductPublishError("risk_control", f"{operation}触发风控: {message}", raw_response=response)
        if cls._contains_marker(response, TOKEN_ERROR_MARKERS):
            raise ProductPublishError("auth", f"{operation}登录凭据已失效: {message}", raw_response=response)
        raise ProductPublishError("platform_rejected", f"{operation}失败: {message}", raw_response=response)

    @staticmethod
    def _error_message(response: Mapping[str, Any]) -> str:
        ret = response.get("ret") if isinstance(response, Mapping) else None
        if isinstance(ret, list) and ret:
            return str(ret[0])
        for key in ("message", "errorMsg", "msg"):
            if response.get(key):
                return str(response[key])
        return "平台返回未知错误"

    @staticmethod
    def _contains_marker(response: Mapping[str, Any], markers: tuple[str, ...]) -> bool:
        text = json.dumps(response, ensure_ascii=False).upper()
        return any(marker in text for marker in markers)

    @classmethod
    def _find_item_id(cls, node: Any, expected: str | None = None) -> str | None:
        if isinstance(node, Mapping):
            for key in ("itemId", "item_id", "idleItemId", "idleId"):
                candidate = str(node.get(key) or "")
                if candidate.isdigit() and len(candidate) >= 6 and (not expected or candidate == expected):
                    return candidate
            for value in node.values():
                found = cls._find_item_id(value, expected)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = cls._find_item_id(value, expected)
                if found:
                    return found
        return None

    def _progress(self, phase: str) -> None:
        if self._progress_handler:
            self._progress_handler(phase)

    def _cookie_value(self, name: str) -> str:
        value = ""
        for cookie in self._session.cookies:
            if cookie.name == name:
                value = str(cookie.value or "")
        return value

    @staticmethod
    def _parse_cookie(value: str) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for part in value.split(";"):
            key, separator, cookie_value = part.strip().partition("=")
            if separator and key:
                cookies[key] = cookie_value
        return cookies
