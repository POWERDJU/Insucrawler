from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models import DimCompany
from app.normalizers.company_normalizer import CompanyMatch, CompanyNormalizer
from app.utils.text import compact_spaces, normalize_search_key


@dataclass(frozen=True)
class CompanyMention:
    company_name_normalized: str
    insurance_type: str | None
    matched_alias: str
    start: int | None
    end: int | None
    alias_length: int
    match_type: str
    is_short_alias: bool
    confidence: float
    source: str
    score: float


@dataclass(frozen=True)
class CompanyAttributionResult:
    company_id: int | None
    company_name_normalized: str | None
    insurance_type: str | None
    matched_alias: str | None
    confidence: float
    basis: str
    needs_review: bool
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    needs_review: bool
    reason: str


class CompanyAttributionService:
    """Deterministic local company resolver shared by product/exclusive paths."""

    def __init__(self, normalizer: CompanyNormalizer | None = None) -> None:
        self.normalizer = normalizer or CompanyNormalizer()

    def resolve_company_for_context(
        self,
        db: Session,
        *,
        raw_company_name: str | None = None,
        local_text: str | None = None,
        previous_text: str | None = None,
        article_title: str | None = None,
        article_description: str | None = None,
        full_text: str | None = None,
        expected_insurance_type: str | None = None,
        association_hint: str | None = None,
        product_or_subject_name: str | None = None,
        company_candidates: Iterable[str] | None = None,
    ) -> CompanyAttributionResult:
        expected = self._expected_insurance_type(expected_insurance_type, association_hint, local_text, full_text)
        mentions: list[CompanyMention] = []
        mentions.extend(self.detect_company_mentions_with_positions(local_text, source="local_text", product_or_subject_name=product_or_subject_name))
        mentions.extend(self.detect_company_mentions_with_positions(previous_text, source="previous_text", product_or_subject_name=product_or_subject_name))
        mentions.extend(self.detect_company_mentions_with_positions(article_title, source="article_title", product_or_subject_name=product_or_subject_name))
        mentions.extend(self.detect_company_mentions_with_positions(article_description, source="article_description", product_or_subject_name=product_or_subject_name))
        mentions.extend(self.detect_company_mentions_with_positions(full_text, source="full_text", product_or_subject_name=product_or_subject_name))
        mentions.extend(self._candidate_mentions(company_candidates, source="company_candidates"))

        raw_match = self.normalizer.normalize(raw_company_name) if raw_company_name else None
        if raw_match and raw_match.is_known_insurer and raw_match.company_name_normalized:
            mentions.append(self._mention_from_match(raw_match, source="raw_candidate", base_score=0.64))
        raw_candidate_review_reason = None
        if raw_match and raw_match.needs_review:
            raw_candidate_review_reason = f"raw company candidate is ambiguous or not a known insurer: {raw_company_name}"
        related_match = self._related_company_for_expected(raw_company_name, expected, mentions, raw_match)
        if related_match:
            mentions.append(self._mention_from_match(related_match, source="industry_reresolve", base_score=0.86))

        if not mentions:
            return CompanyAttributionResult(
                company_id=None,
                company_name_normalized=None,
                insurance_type=expected or "unknown",
                matched_alias=raw_company_name,
                confidence=0.0,
                basis="ambiguous_review",
                needs_review=True,
                reason=raw_candidate_review_reason or "no known insurance company found in local context",
            )

        deduped = self._dedupe_mentions(mentions)
        sorted_mentions = sorted(deduped, key=lambda item: (-item.score, -item.alias_length, item.start if item.start is not None else 10**9))
        chosen = sorted_mentions[0]
        if expected:
            compatible = [item for item in sorted_mentions if item.insurance_type == expected and not item.is_short_alias]
            if compatible:
                chosen = compatible[0]

        company = self._company_by_normalized(db, chosen.company_name_normalized)
        validation = self.validate_company_industry_consistency(chosen, expected)
        short_alias_only = chosen.is_short_alias and not self._has_stronger_same_company(sorted_mentions, chosen)
        needs_review = bool(
            company is None
            or validation.needs_review
            or short_alias_only
            or chosen.score < 0.62
        )
        basis = self._basis_for_mention(chosen, short_alias_only=short_alias_only)
        reason = validation.reason if validation.needs_review else self._reason_for_mention(chosen, expected, short_alias_only)
        if raw_candidate_review_reason and chosen.source != "raw_candidate":
            reason = f"{reason}; ignored {raw_candidate_review_reason}"
        return CompanyAttributionResult(
            company_id=company.company_id if company else None,
            company_name_normalized=chosen.company_name_normalized if company else None,
            insurance_type=(company.insurance_type_default or company.insurance_type) if company else (chosen.insurance_type or expected or "unknown"),
            matched_alias=chosen.matched_alias,
            confidence=max(0.0, min(0.99, chosen.score)),
            basis=basis,
            needs_review=needs_review,
            reason=reason,
        )

    def detect_company_mentions_with_positions(
        self,
        text: str | None,
        *,
        source: str = "local_text",
        product_or_subject_name: str | None = None,
    ) -> list[CompanyMention]:
        text_value = compact_spaces(text)
        if not text_value:
            return []
        mentions: list[CompanyMention] = []
        for match in self.normalizer.detect_all_with_positions(text_value):
            if not match.company_name_normalized:
                continue
            mentions.append(self._mention_from_match(match, source=source, product_or_subject_name=product_or_subject_name, source_text=text_value))
        return mentions

    def score_company_mention(
        self,
        mention: CompanyMention,
        *,
        product_or_subject_name: str | None = None,
        source_text: str | None = None,
    ) -> float:
        score = float(mention.confidence or 0.0)
        source_weight = {
            "local_text": 0.34,
            "previous_text": 0.24,
            "article_title": 0.14,
            "article_description": 0.09,
            "full_text": 0.04,
            "raw_candidate": 0.02,
            "industry_reresolve": 0.18,
            "company_candidates": 0.0,
        }.get(mention.source, 0.0)
        score += source_weight
        if mention.match_type == "normalized":
            score += 0.14
        elif mention.match_type == "full_alias":
            score += 0.08
        elif mention.is_short_alias:
            score -= 0.28
        score += min(0.08, max(0, mention.alias_length - 3) * 0.01)
        if product_or_subject_name and source_text and mention.start is not None:
            score += self._proximity_bonus(source_text, product_or_subject_name, mention.start)
        return max(0.0, score)

    def is_ambiguous_short_alias(self, alias: str | None) -> bool:
        return self.normalizer.is_ambiguous_short_alias(alias)

    def validate_company_industry_consistency(self, company: CompanyMention | CompanyAttributionResult, expected_insurance_type: str | None) -> ValidationResult:
        expected = self._normalize_insurance_type(expected_insurance_type)
        actual = self._normalize_insurance_type(company.insurance_type)
        if expected and actual and expected != actual:
            return ValidationResult(
                valid=False,
                needs_review=True,
                reason=f"company insurance type conflict: expected {expected}, got {actual}",
            )
        return ValidationResult(valid=True, needs_review=False, reason="company insurance type is consistent")

    def _mention_from_match(
        self,
        match: CompanyMatch,
        *,
        source: str,
        base_score: float | None = None,
        product_or_subject_name: str | None = None,
        source_text: str | None = None,
    ) -> CompanyMention:
        mention = CompanyMention(
            company_name_normalized=match.company_name_normalized or "",
            insurance_type=match.insurance_type or match.insurance_type_default,
            matched_alias=match.company_name_raw,
            start=match.start,
            end=match.end,
            alias_length=match.alias_length or len(normalize_search_key(match.company_name_raw)),
            match_type=match.match_type,
            is_short_alias=match.is_short_alias,
            confidence=base_score if base_score is not None else match.confidence,
            source=source,
            score=0.0,
        )
        source_text = source_text or (match.company_name_raw if source in {"raw_candidate", "company_candidates"} else None)
        score = self.score_company_mention(mention, product_or_subject_name=product_or_subject_name, source_text=source_text)
        return CompanyMention(**{**mention.__dict__, "score": score})

    def _candidate_mentions(self, candidates: Iterable[str] | None, *, source: str) -> list[CompanyMention]:
        mentions: list[CompanyMention] = []
        for candidate in candidates or []:
            match = self.normalizer.normalize(candidate)
            if match and match.is_known_insurer and match.company_name_normalized:
                mentions.append(self._mention_from_match(match, source=source, base_score=0.58))
        return mentions

    @staticmethod
    def _dedupe_mentions(mentions: list[CompanyMention]) -> list[CompanyMention]:
        best: dict[tuple[str, str], CompanyMention] = {}
        for mention in mentions:
            key = (mention.company_name_normalized, mention.source)
            existing = best.get(key)
            if not existing or mention.score > existing.score or (mention.score == existing.score and mention.alias_length > existing.alias_length):
                best[key] = mention
        return list(best.values())

    @staticmethod
    def _has_stronger_same_company(mentions: list[CompanyMention], chosen: CompanyMention) -> bool:
        return any(
            item.company_name_normalized == chosen.company_name_normalized
            and not item.is_short_alias
            and item.alias_length >= chosen.alias_length
            for item in mentions
        )

    @staticmethod
    def _basis_for_mention(mention: CompanyMention, *, short_alias_only: bool) -> str:
        if short_alias_only:
            return "ambiguous_review"
        if mention.source == "local_text" and mention.match_type == "normalized":
            return "local_full_name"
        if mention.source == "local_text":
            return "local_alias"
        if mention.source == "previous_text":
            return "previous_sentence"
        if mention.source == "article_title":
            return "title"
        if mention.source == "full_text":
            return "full_text"
        if mention.source == "raw_candidate":
            return "raw_candidate"
        if mention.source == "industry_reresolve":
            return "industry_reresolve"
        return mention.source

    @staticmethod
    def _reason_for_mention(mention: CompanyMention, expected: str | None, short_alias_only: bool) -> str:
        if short_alias_only:
            return f"short alias '{mention.matched_alias}' is ambiguous and requires review"
        if mention.source == "industry_reresolve":
            return f"selected {mention.company_name_normalized} by resolving ambiguous company group against insurance type {expected}"
        expected_part = f"; expected insurance type {expected}" if expected else ""
        return f"selected {mention.company_name_normalized} from {mention.source} using {mention.match_type}{expected_part}"

    @staticmethod
    def _proximity_bonus(text: str, product_or_subject_name: str, mention_start: int) -> float:
        text_key = normalize_search_key(text)
        target_key = normalize_search_key(product_or_subject_name)
        if not text_key or not target_key:
            return 0.0
        target_pos = text_key.find(target_key)
        if target_pos < 0:
            return 0.0
        distance = abs(target_pos - mention_start)
        if distance <= 40:
            return 0.24
        if distance <= 120:
            return 0.16
        if distance <= 240:
            return 0.08
        return 0.0

    def _company_by_normalized(self, db: Session, normalized: str | None) -> DimCompany | None:
        if not normalized:
            return None
        return db.query(DimCompany).filter(DimCompany.company_name_normalized == normalized).first()

    def _expected_insurance_type(
        self,
        expected_insurance_type: str | None,
        association_hint: str | None,
        local_text: str | None,
        full_text: str | None,
    ) -> str | None:
        explicit = self._normalize_insurance_type(expected_insurance_type)
        if explicit:
            return explicit
        text = " ".join(part for part in [association_hint, local_text, full_text] if part)
        if any(token in text for token in ["손해보험협회", "손보협회", "손해보험", "장기 손해보험", "장기손해보험", "손보"]):
            return "손해보험"
        if "장기보험" in text and "생명보험협회" not in text:
            return "손해보험"
        if any(token in text for token in ["생명보험협회", "생보협회", "종신보험"]):
            return "생명보험"
        return None

    @staticmethod
    def _normalize_insurance_type(value: str | None) -> str | None:
        text = compact_spaces(value)
        if text in {"life", "생명보험", "생보"}:
            return "생명보험"
        if text in {"nonlife", "손해보험", "손보"}:
            return "손해보험"
        return text or None

    def _related_company_for_expected(
        self,
        raw_company_name: str | None,
        expected: str | None,
        mentions: list[CompanyMention],
        raw_match: CompanyMatch | None,
    ) -> CompanyMatch | None:
        if not raw_company_name or not expected:
            return None
        expected = self._normalize_insurance_type(expected)
        if not expected:
            return None
        raw_company_name_normalized = raw_match.company_name_normalized if raw_match else None
        if raw_company_name_normalized and any(
            mention.source in {"local_text", "previous_text"}
            and mention.company_name_normalized == raw_company_name_normalized
            and not mention.is_short_alias
            for mention in mentions
        ):
            return None
        raw_type = self._normalize_insurance_type(raw_match.insurance_type if raw_match else None)
        if raw_type == expected:
            return None
        return self.normalizer.resolve_related_company_by_insurance_type(raw_company_name, expected)
