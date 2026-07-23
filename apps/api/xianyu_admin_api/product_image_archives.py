"""Safe ZIP archive imports for staged product images."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile, ZipInfo

from integrations.xianyu_core.images import MAX_IMAGE_INPUT_BYTES, ImageValidationError

from .product_images import ProductImageStorage, StoredProductImage


MAX_PRODUCT_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_PRODUCT_ARCHIVE_ENTRIES = 200
MAX_PRODUCT_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
SUPPORTED_ARCHIVE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class ProductImageArchiveError(ValueError):
    """Raised when a product image archive is unsafe or cannot be parsed."""


@dataclass(slots=True, frozen=True)
class RejectedArchiveImage:
    filename: str
    reason: str


@dataclass(slots=True, frozen=True)
class StoredArchiveImage:
    original_filename: str
    stored: StoredProductImage


@dataclass(slots=True, frozen=True)
class ProductImageArchiveImport:
    images: tuple[StoredArchiveImage, ...]
    ignored_non_image_count: int
    rejected_images: tuple[RejectedArchiveImage, ...]
    skipped_limit_count: int


def _archive_size(source: BinaryIO) -> int:
    current = source.tell()
    source.seek(0, 2)
    size = source.tell()
    source.seek(current)
    return size


def _open_archive(source: BinaryIO) -> ZipFile:
    source.seek(0)
    try:
        # Many Chinese marketplace exports use legacy GBK names without the UTF-8 flag.
        return ZipFile(source, mode="r", metadata_encoding="gbk")
    except UnicodeDecodeError:
        source.seek(0)
        return ZipFile(source, mode="r")


def _normalized_name(info: ZipInfo) -> str:
    return info.filename.replace("\\", "/")


def _is_unsafe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.is_absolute()
        or ".." in path.parts
        or bool(re.match(r"^[A-Za-z]:", name))
    )


def _natural_sort_key(info: ZipInfo) -> tuple[tuple[int, object], ...]:
    parts = re.split(r"(\d+)", _normalized_name(info).casefold())
    return tuple((1, int(part)) if part.isdigit() else (0, part) for part in parts)


def import_product_image_archive(
    source: BinaryIO,
    *,
    account_id: str,
    limit: int,
    storage: ProductImageStorage,
) -> ProductImageArchiveImport:
    """Validate a ZIP and persist up to ``limit`` normalized images.

    Archive members are read directly and are never extracted to caller-controlled paths.
    Database records are created by the API after this blocking media operation completes.
    """

    if not 1 <= limit <= 9:
        raise ProductImageArchiveError("压缩包图片导入数量必须为 1 到 9 张")
    size = _archive_size(source)
    if size <= 0:
        raise ProductImageArchiveError("压缩包为空")
    if size > MAX_PRODUCT_ARCHIVE_BYTES:
        raise ProductImageArchiveError("ZIP 压缩包不能超过 50 MB")

    saved: list[StoredArchiveImage] = []
    try:
        try:
            archive = _open_archive(source)
        except BadZipFile as exc:
            raise ProductImageArchiveError("文件不是有效的 ZIP 压缩包") from exc

        with archive:
            infos = archive.infolist()
            if len(infos) > MAX_PRODUCT_ARCHIVE_ENTRIES:
                raise ProductImageArchiveError("ZIP 压缩包内文件数量不能超过 200 个")
            if any(info.flag_bits & 0x1 for info in infos):
                raise ProductImageArchiveError("暂不支持加密 ZIP 压缩包")

            files = [info for info in infos if not info.is_dir()]
            if any(_is_unsafe_name(_normalized_name(info)) for info in files):
                raise ProductImageArchiveError("ZIP 压缩包包含不安全的文件路径")
            if sum(max(0, info.file_size) for info in files) > MAX_PRODUCT_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ProductImageArchiveError("ZIP 压缩包解压后的文件总量不能超过 100 MB")

            candidates = sorted(
                (
                    info
                    for info in files
                    if PurePosixPath(_normalized_name(info)).suffix.casefold()
                    in SUPPORTED_ARCHIVE_IMAGE_SUFFIXES
                ),
                key=_natural_sort_key,
            )
            ignored_count = len(files) - len(candidates)
            rejected: list[RejectedArchiveImage] = []
            skipped_limit_count = 0

            for index, info in enumerate(candidates):
                if len(saved) >= limit:
                    skipped_limit_count = len(candidates) - index
                    break
                normalized_name = _normalized_name(info)
                original_filename = PurePosixPath(normalized_name).name or "product-image.jpg"
                if info.file_size <= 0:
                    rejected.append(RejectedArchiveImage(original_filename, "图片文件为空"))
                    continue
                if info.file_size > MAX_IMAGE_INPUT_BYTES:
                    rejected.append(
                        RejectedArchiveImage(original_filename, "图片大小不能超过 10 MB")
                    )
                    continue
                try:
                    with archive.open(info, mode="r") as member:
                        raw = member.read(MAX_IMAGE_INPUT_BYTES + 1)
                except (BadZipFile, EOFError, OSError, RuntimeError) as exc:
                    raise ProductImageArchiveError("ZIP 压缩包已损坏，无法读取图片") from exc
                if len(raw) > MAX_IMAGE_INPUT_BYTES:
                    rejected.append(
                        RejectedArchiveImage(original_filename, "图片大小不能超过 10 MB")
                    )
                    continue
                try:
                    stored = storage.save(account_id, raw)
                except ImageValidationError as exc:
                    rejected.append(RejectedArchiveImage(original_filename, str(exc)))
                    continue
                saved.append(StoredArchiveImage(original_filename, stored))

            return ProductImageArchiveImport(
                images=tuple(saved),
                ignored_non_image_count=ignored_count,
                rejected_images=tuple(rejected),
                skipped_limit_count=skipped_limit_count,
            )
    except Exception:
        for image in saved:
            storage.delete(account_id, image.stored.asset_id)
        raise

