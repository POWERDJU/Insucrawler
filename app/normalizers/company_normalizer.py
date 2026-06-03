from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from app.utils.text import compact_spaces, normalize_search_key


@dataclass(frozen=True)
class CompanyMatch:
    company_name_raw: str
    company_name_normalized: str | None
    insurance_type: str | None
    insurance_type_default: str | None
    basis: str
    confidence: float
    match_type: str
    company_role: str | None = None
    status_2024_2026: str | None = None
    include_in_product_news_default: str | None = None
    notes: str | None = None
    is_known_insurer: bool = True
    needs_review: bool = False
    start: int | None = None
    end: int | None = None
    alias_length: int = 0
    is_short_alias: bool = False


class CompanyNormalizer:
    def __init__(self, dictionary_path: str | Path = "config/company_dictionary.csv") -> None:
        self.dictionary_path = Path(dictionary_path)
        self._aliases: list[dict[str, str | None]] = []
        self._exact: dict[str, dict[str, str | None]] = {}
        self._companies_by_alias_key: dict[str, set[str]] = {}
        self.load()

    def load(self) -> None:
        self._aliases.clear()
        self._exact.clear()
        self._companies_by_alias_key.clear()
        if not self.dictionary_path.exists():
            return
        with self.dictionary_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                normalized = row.get("company_name_normalized") or ""
                insurance_type = row.get("insurance_type") or row.get("insurance_type_default") or None
                alias_values = [normalized]
                if row.get("company_name_raw"):
                    alias_values.append(row["company_name_raw"])
                alias_values.extend([value.strip() for value in (row.get("alias") or "").split("|") if value.strip()])
                for value in alias_values:
                    key = normalize_search_key(value)
                    if not key:
                        continue
                    entry = {
                        "alias_key": key,
                        "company_name_raw": value,
                        "company_name_normalized": normalized,
                        "insurance_type": insurance_type,
                        "insurance_type_default": row.get("insurance_type_default") or insurance_type,
                        "match_type": "normalized" if value == normalized else "alias",
                        "company_role": row.get("company_role"),
                        "status_2024_2026": row.get("status_2024_2026"),
                        "include_in_product_news_default": row.get("include_in_product_news_default"),
                        "notes": row.get("notes"),
                    }
                    self._aliases.append(entry)
                    self._exact[key] = entry
                    self._companies_by_alias_key.setdefault(key, set()).add(normalized)
        self._aliases.sort(key=lambda item: len(item["alias_key"] or ""), reverse=True)

    def normalize(self, raw_name: str | None) -> CompanyMatch | None:
        key = normalize_search_key(raw_name)
        if not key:
            return None
        if self.is_ambiguous_short_alias(raw_name):
            return CompanyMatch(
                company_name_raw=raw_name or "",
                company_name_normalized=None,
                insurance_type=None,
                insurance_type_default=None,
                basis="ambiguous_short_alias",
                confidence=0.35,
                match_type="short_alias",
                is_known_insurer=False,
                needs_review=True,
                alias_length=len(key),
                is_short_alias=True,
            )
        if key in self._exact:
            return self._to_match(self._exact[key], raw_name or self._exact[key]["company_name_raw"], 0.98)
        for entry in self._aliases:
            alias_key = entry["alias_key"] or ""
            if alias_key and alias_key in key:
                confidence = 0.96 if entry["match_type"] == "alias" else 0.97
                return self._to_match(entry, raw_name or entry["company_name_raw"], confidence)
        for entry in self._aliases:
            alias_key = entry["alias_key"] or ""
            if alias_key and key in alias_key:
                return self._to_match(entry, raw_name or entry["company_name_raw"], 0.9)
        return self._unknown_match(raw_name)

    def detect_all(self, text: str | None) -> list[CompanyMatch]:
        best_by_company: dict[str, CompanyMatch] = {}
        for match in self.detect_all_with_positions(text):
            company_key = match.company_name_normalized or ""
            existing = best_by_company.get(company_key)
            if not existing or self._match_sort_key(match) < self._match_sort_key(existing):
                best_by_company[company_key] = match
        return sorted(best_by_company.values(), key=self._match_sort_key)

    def detect_all_with_positions(self, text: str | None) -> list[CompanyMatch]:
        key = normalize_search_key(text)
        if not key:
            return []
        matches: list[CompanyMatch] = []
        seen: set[tuple[str, str, int]] = set()
        for entry in self._aliases:
            alias_key = entry["alias_key"] or ""
            if not alias_key:
                continue
            start = key.find(alias_key)
            while start >= 0:
                dedupe_key = (entry.get("company_name_normalized") or "", alias_key, start)
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    match_type = self._entry_match_type(entry, alias_key)
                    confidence = self._entry_confidence(entry, alias_key, match_type)
                    matches.append(
                        self._to_match(
                            {**entry, "match_type": match_type},
                            entry.get("company_name_raw"),
                            confidence,
                            start=start,
                            end=start + len(alias_key),
                        )
                    )
                start = key.find(alias_key, start + 1)
        return sorted(matches, key=self._match_sort_key)

    def known_aliases(self, company_name_normalized: str | None = None) -> list[str]:
        aliases: list[str] = []
        seen: set[str] = set()
        for entry in self._aliases:
            if company_name_normalized and entry.get("company_name_normalized") != company_name_normalized:
                continue
            value = entry.get("company_name_raw")
            if value and value not in seen:
                aliases.append(value)
                seen.add(value)
        return aliases

    def is_ambiguous_short_alias(self, raw_name: str | None) -> bool:
        key = normalize_search_key(raw_name)
        if not key:
            return False
        static_ambiguous = {
            "한화",
            "삼성",
            "현대",
            "kb",
            "db",
            "nh",
            "농협",
            "신한",
            "교보",
            "흥국",
            "메리츠",
            "롯데",
            "하나",
        }
        if key in static_ambiguous:
            return True
        companies = self._companies_by_alias_key.get(key) or set()
        if len(companies) > 1:
            return True
        return len(key) <= 2 and any((entry.get("alias_key") or "").startswith(key) for entry in self._aliases)

    def resolve_related_company_by_insurance_type(self, raw_name: str | None, insurance_type: str | None) -> CompanyMatch | None:
        key = normalize_search_key(raw_name)
        target_type = compact_spaces(insurance_type)
        if not key or not target_type:
            return None
        static_group_aliases = [
            normalize_search_key(item)
            for item in ["한화", "삼성", "KB", "DB", "NH", "농협", "신한", "교보", "흥국", "메리츠", "롯데", "하나"]
        ]
        candidate_alias_keys = [
            alias_key
            for alias_key, companies in self._companies_by_alias_key.items()
            if len(companies) > 1 and (key.startswith(alias_key) or alias_key in key)
        ]
        candidate_alias_keys.extend(
            alias_key
            for alias_key in static_group_aliases
            if alias_key and (key.startswith(alias_key) or alias_key in key)
        )
        candidate_alias_keys = list(dict.fromkeys(candidate_alias_keys))
        for alias_key in sorted(candidate_alias_keys, key=len, reverse=True):
            entries = [
                entry
                for entry in self._aliases
                if (
                    entry.get("alias_key") == alias_key
                    or normalize_search_key(entry.get("company_name_normalized")).startswith(alias_key)
                    or alias_key in normalize_search_key(entry.get("company_name_normalized"))
                )
                and (entry.get("insurance_type_default") or entry.get("insurance_type")) == target_type
            ]
            normalized_names = {entry.get("company_name_normalized") for entry in entries if entry.get("company_name_normalized")}
            if len(normalized_names) == 1:
                entry = entries[0]
                return self._to_match(
                    {**entry, "match_type": "industry_reresolve"},
                    entry.get("company_name_raw"),
                    0.86,
                )
        return None

    @staticmethod
    def is_negative_org_candidate(raw_name: str | None) -> bool:
        text = compact_spaces(raw_name)
        if not text:
            return False
        negative_patterns = [
            r"[\uac00-\ud7a3A-Za-z0-9]{1,12}(?:농협|축협)(?:은행)?(?:\s*(?:지점|지역본부|본부))?$",
            r"[\uac00-\ud7a3A-Za-z0-9]{1,12}(?:지점|지역본부|본부)$",
            r"농협중앙회\s*[\uac00-\ud7a3A-Za-z0-9]{0,12}(?:지점|지역본부|본부)?$",
        ]
        return any(re.fullmatch(pattern, text) for pattern in negative_patterns)

    def _unknown_match(self, raw_name: str | None) -> CompanyMatch:
        match_type = "unknown_org_candidate" if self.is_negative_org_candidate(raw_name) else "unknown"
        return CompanyMatch(
            company_name_raw=raw_name or "",
            company_name_normalized=None,
            insurance_type=None,
            insurance_type_default=None,
            basis="unknown",
            confidence=0.2 if match_type == "unknown_org_candidate" else 0.3,
            match_type=match_type,
            is_known_insurer=False,
            needs_review=True,
        )

    def _entry_match_type(self, entry: dict[str, str | None], alias_key: str) -> str:
        if entry.get("match_type") == "normalized":
            return "normalized"
        if self.is_ambiguous_short_alias(entry.get("company_name_raw")) or len(alias_key) <= 2:
            return "short_alias"
        return "full_alias"

    @staticmethod
    def _entry_confidence(entry: dict[str, str | None], alias_key: str, match_type: str) -> float:
        if match_type == "normalized":
            return 0.99
        if match_type == "full_alias":
            return 0.96 if len(alias_key) >= 4 else 0.9
        return 0.55

    @staticmethod
    def _match_sort_key(match: CompanyMatch) -> tuple[int, int, float, int, str]:
        type_rank = {"normalized": 0, "full_alias": 1, "alias": 1, "short_alias": 4}.get(match.match_type, 3)
        return (
            type_rank,
            -(match.alias_length or len(normalize_search_key(match.company_name_raw))),
            -float(match.confidence or 0.0),
            int(match.start if match.start is not None else 10**9),
            match.company_name_normalized or "",
        )

    @staticmethod
    def _to_match(
        entry: dict[str, str | None],
        raw_name: str | None,
        confidence: float,
        *,
        start: int | None = None,
        end: int | None = None,
    ) -> CompanyMatch:
        alias_key = entry.get("alias_key") or normalize_search_key(raw_name)
        match_type = entry.get("match_type") or "alias"
        is_short = match_type == "short_alias"
        return CompanyMatch(
            company_name_raw=raw_name or entry.get("company_name_raw") or "",
            company_name_normalized=entry.get("company_name_normalized") or "",
            insurance_type=entry.get("insurance_type"),
            insurance_type_default=entry.get("insurance_type_default"),
            basis="company_dictionary",
            confidence=confidence,
            match_type=entry.get("match_type") or "alias",
            company_role=entry.get("company_role"),
            status_2024_2026=entry.get("status_2024_2026"),
            include_in_product_news_default=entry.get("include_in_product_news_default"),
            notes=entry.get("notes"),
            is_known_insurer=True,
            needs_review=is_short,
            start=start,
            end=end,
            alias_length=len(alias_key),
            is_short_alias=is_short,
        )
