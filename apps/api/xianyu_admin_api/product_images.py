"""Persistent, account-scoped storage for normalized product images."""

from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from integrations.xianyu_core.images import PreparedImage, prepare_image

from .settings import settings


SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(slots=True, frozen=True)
class StoredProductImage:
    asset_id: str
    prepared: PreparedImage


class ProductImageStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.product_image_dir).resolve()

    def save(self, account_id: str, raw: bytes) -> StoredProductImage:
        self._validate_id(account_id, "account ID")
        prepared = prepare_image(raw)
        asset_id = uuid.uuid4().hex
        target = self.path(account_id, asset_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(prepared.data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return StoredProductImage(asset_id=asset_id, prepared=prepared)

    def read(self, account_id: str, asset_id: str) -> bytes:
        return self.path(account_id, asset_id).read_bytes()

    def delete(self, account_id: str, asset_id: str) -> None:
        self.path(account_id, asset_id).unlink(missing_ok=True)

    def delete_account(self, account_id: str) -> None:
        self._validate_id(account_id, "account ID")
        directory = (self.root / account_id).resolve()
        if self.root not in directory.parents:
            raise ValueError("product image path escapes storage root")
        shutil.rmtree(directory, ignore_errors=True)

    def path(self, account_id: str, asset_id: str) -> Path:
        self._validate_id(account_id, "account ID")
        self._validate_id(asset_id, "asset ID")
        target = (self.root / account_id / f"{asset_id}.jpg").resolve()
        if self.root not in target.parents:
            raise ValueError("product image path escapes storage root")
        return target

    @staticmethod
    def _validate_id(value: str, label: str) -> None:
        if not SAFE_ID.fullmatch(value):
            raise ValueError(f"invalid {label}")


product_image_storage = ProductImageStorage()
