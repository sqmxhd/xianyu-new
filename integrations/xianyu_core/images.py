"""Image validation and normalization for outbound Xianyu messages."""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_INPUT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_OUTPUT_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1920
MAX_IMAGE_PIXELS = 40_000_000
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    """Raised when an uploaded file is not a supported, safe image."""


class ImageUploadError(RuntimeError):
    """Raised when Xianyu's media service rejects an image upload."""


@dataclass(slots=True, frozen=True)
class PreparedImage:
    data: bytes
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    sha256: str


@dataclass(slots=True, frozen=True)
class UploadedImage:
    url: str
    width: int
    height: int
    mime_type: str
    size_bytes: int
    sha256: str


def prepare_image(raw: bytes) -> PreparedImage:
    """Decode, orient and normalize an uploaded image for Xianyu's CDN."""

    if not raw:
        raise ImageValidationError("图片文件为空")
    if len(raw) > MAX_IMAGE_INPUT_BYTES:
        raise ImageValidationError("图片大小不能超过 10 MB")

    try:
        with Image.open(io.BytesIO(raw)) as source:
            image_format = str(source.format or "").upper()
            if image_format not in SUPPORTED_IMAGE_FORMATS:
                raise ImageValidationError("仅支持 JPEG、PNG、WebP 图片")
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ImageValidationError("图片尺寸无效或像素数过大")
            if getattr(source, "n_frames", 1) != 1:
                raise ImageValidationError("暂不支持动态图片")

            oriented = ImageOps.exif_transpose(source)
            oriented.load()
            if oriented.mode in {"RGBA", "LA"} or (
                oriented.mode == "P" and "transparency" in oriented.info
            ):
                rgba = oriented.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, "white")
                flattened.paste(rgba, mask=rgba.getchannel("A"))
                image = flattened
            else:
                image = oriented.convert("RGB")
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("文件不是有效图片") from exc

    image.thumbnail(
        (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
        Image.Resampling.LANCZOS,
    )

    encoded = b""
    for quality in (85, 75, 65, 55, 45, 35):
        output = io.BytesIO()
        image.save(output, "JPEG", quality=quality, optimize=True)
        encoded = output.getvalue()
        if len(encoded) <= MAX_IMAGE_OUTPUT_BYTES:
            break
    if len(encoded) > MAX_IMAGE_OUTPUT_BYTES:
        raise ImageValidationError("图片压缩后仍超过 5 MB")

    width, height = image.size
    return PreparedImage(
        data=encoded,
        filename=f"image_{uuid.uuid4().hex[:12]}.jpg",
        mime_type="image/jpeg",
        width=width,
        height=height,
        size_bytes=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )
