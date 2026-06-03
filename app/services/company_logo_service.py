from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
BUCKETS = {"life", "nonlife"}


class CompanyLogoService:
    def __init__(self, life_dir: str | None = None, nonlife_dir: str | None = None) -> None:
        self.life_dir = self._resolve_dir(life_dir or os.getenv("COMPANY_LOGO_LIFE_DIR") or "LOGO/LIFE")
        self.nonlife_dir = self._resolve_dir(nonlife_dir or os.getenv("COMPANY_LOGO_NONLIFE_DIR") or "LOGO/NONLIFE")

    def get_logo_path(self, company_name: str | None, insurance_type: str | None = None) -> Path | None:
        key = self.normalize_logo_filename_key(company_name)
        if not key:
            return None
        for bucket in self._bucket_order(insurance_type):
            path = self.scan_logo_index().get(bucket, {}).get(key)
            if path and path.exists():
                return path
        return None

    def get_logo_url(self, company_name: str | None, insurance_type: str | None = None) -> str | None:
        path = self.get_logo_path(company_name, insurance_type)
        if path is None:
            return None
        bucket = "life" if self._is_relative_to(path, self.life_dir) else "nonlife"
        version = path.stat().st_mtime_ns
        return f"/api/company-logos/file/{bucket}/{quote(path.name)}?v={version}"

    def get_logo_file(self, bucket: str, filename: str) -> Path | None:
        normalized_bucket = (bucket or "").casefold()
        if normalized_bucket not in BUCKETS:
            return None
        if Path(filename).name != filename:
            return None
        if Path(filename).suffix.casefold() not in ALLOWED_LOGO_EXTENSIONS:
            return None
        for path in self.scan_logo_index().get(normalized_bucket, {}).values():
            if path.name == filename and path.exists():
                return path
        return None

    def scan_logo_index(self) -> dict[str, dict[str, Path]]:
        return _scan_logo_index(str(self.life_dir), str(self.nonlife_dir))

    def refresh_logo_index(self) -> None:
        _scan_logo_index.cache_clear()

    @staticmethod
    def normalize_logo_filename_key(name: str | None) -> str:
        value = unicodedata.normalize("NFKC", name or "").casefold()
        value = Path(value).stem
        return re.sub(r"[^0-9a-z가-힣]", "", value)

    @staticmethod
    def _resolve_dir(value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    @staticmethod
    def _bucket_order(insurance_type: str | None) -> list[str]:
        value = insurance_type or ""
        if "생명" in value:
            return ["life", "nonlife"]
        if "손해" in value or "화재" in value:
            return ["nonlife", "life"]
        return ["life", "nonlife"]

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False


@lru_cache(maxsize=16)
def _scan_logo_index(life_dir: str, nonlife_dir: str) -> dict[str, dict[str, Path]]:
    index: dict[str, dict[str, Path]] = {"life": {}, "nonlife": {}}
    for bucket, directory in {"life": Path(life_dir), "nonlife": Path(nonlife_dir)}.items():
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.casefold() not in ALLOWED_LOGO_EXTENSIONS:
                continue
            key = CompanyLogoService.normalize_logo_filename_key(path.name)
            if key and key not in index[bucket]:
                index[bucket][key] = path.resolve()
    return index
