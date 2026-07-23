"""Pinned administrative-region catalog used by product publishing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import ProductLocationPayload, ProductRegionCatalogPayload, ProductRegionPayload


@dataclass(frozen=True, slots=True)
class _Region:
    code: str
    parent_code: str
    name: str
    level: str
    longitude: float
    latitude: float


class ProductRegionCatalog:
    def __init__(self, path: Path | None = None) -> None:
        catalog_path = path or Path(__file__).with_name("product_regions.json")
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.source = str(raw["source"])
        self.version = str(raw["source_commit"])
        self._regions = {
            str(item[0]): _Region(
                code=str(item[0]),
                parent_code=str(item[1]),
                name=str(item[2]),
                level=str(item[3]),
                longitude=float(item[4]),
                latitude=float(item[5]),
            )
            for item in raw["items"]
        }
        self._children: dict[str, list[str]] = {}
        for region in self._regions.values():
            self._children.setdefault(region.parent_code, []).append(region.code)
        for children in self._children.values():
            children.sort()
        self._payloads = tuple(
            self._to_region_payload(self._regions[code]) for code in sorted(self._regions)
        )

    def catalog_payload(self) -> ProductRegionCatalogPayload:
        return ProductRegionCatalogPayload(
            source=self.source,
            version=self.version,
            items=list(self._payloads),
        )

    def get(self, code: str) -> ProductRegionPayload | None:
        region = self._regions.get(str(code))
        return self._to_region_payload(region) if region is not None else None

    def expand_selectable_codes(self, codes: list[str]) -> list[str]:
        selected: set[str] = set()
        for raw_code in codes:
            code = str(raw_code)
            if code not in self._regions:
                raise ValueError(f"行政区域不存在: {code}")
            self._collect_selectable_codes(code, selected)
        return sorted(selected)

    def location_for(self, code: str) -> ProductLocationPayload:
        payload = self.get(code)
        if payload is None:
            raise ValueError(f"行政区域不存在: {code}")
        if not payload.selectable:
            raise ValueError(f"请选择 {payload.name} 下的具体区域")
        return ProductLocationPayload(
            prov=payload.prov,
            city=payload.city,
            area=payload.area,
            division_id=payload.region_code,
            longitude=payload.longitude,
            latitude=payload.latitude,
            poi_id="",
            poi_name=payload.name,
        )

    def label_for(self, code: str) -> str:
        payload = self.get(code)
        if payload is None:
            raise ValueError(f"行政区域不存在: {code}")
        return " ".join(dict.fromkeys(part for part in (payload.prov, payload.city, payload.area) if part))

    def _collect_selectable_codes(self, code: str, selected: set[str]) -> None:
        children = self._children.get(code, [])
        if not children:
            selected.add(code)
            return
        for child_code in children:
            self._collect_selectable_codes(child_code, selected)

    def _to_region_payload(self, region: _Region) -> ProductRegionPayload:
        ancestors: list[_Region] = []
        cursor: _Region | None = region
        seen: set[str] = set()
        while cursor is not None and cursor.code not in seen:
            ancestors.append(cursor)
            seen.add(cursor.code)
            cursor = self._regions.get(cursor.parent_code)
        ancestors.reverse()

        province = next((item for item in ancestors if item.level == "province"), region)
        city_region = next((item for item in ancestors if item.level == "city"), None)
        if city_region is None and region.level == "city":
            city_region = region
        city = city_region.name if city_region is not None else province.name
        area = region.name if region.level == "district" else ""
        return ProductRegionPayload(
            region_code=region.code,
            parent_code=region.parent_code,
            name=region.name,
            level=region.level,  # type: ignore[arg-type]
            longitude=region.longitude,
            latitude=region.latitude,
            selectable=not self._children.get(region.code),
            prov=province.name,
            city=city,
            area=area,
        )


product_region_catalog = ProductRegionCatalog()
