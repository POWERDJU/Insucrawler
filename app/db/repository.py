from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.classifiers.coverage_classifier import CoverageClassifier
from app.db.models import (
    DimCompany,
    DimPartnerCompany,
    DimProduct,
    DimProductAlias,
    FactArticle,
    FactCoverageEvidence,
    FactExtractionComparison,
    FactExtractionFieldAudit,
    FactLLMRun,
    FactManualIngestion,
    FactProductArticle,
    FactProductMergeDecision,
    FactProductMajorCoverage,
    FactProductNarrativeInsight,
    FactProductObservation,
    FactProductPartner,
    FactProductStructuredFeature,
    FactProductTypeAssignment,
    FactSalesMetricStructured,
)
from app.normalizers.amount_normalizer import normalize_coverage_amount
from app.normalizers.company_normalizer import CompanyNormalizer
from app.normalizers.product_name_normalizer import (
    build_product_identity_key,
    normalize_product_name,
    normalize_product_name_core,
    product_core_key_candidates,
    product_search_key,
    validate_product_name_before_save,
)
from app.utils.dates import current_year_month
from app.utils.dates import utcnow
from app.services.company_attribution_service import CompanyAttributionService


PROTECTED_RELEASE_BASES = {"explicit_in_article", "manual", "external_grounded_source"}
INFERABLE_RELEASE_BASES = {None, "", "unknown", "first_seen_only", "earliest_related_article_month"}


def get_or_create_company(db: Session, raw_name: str | None, insurance_type: str | None = None) -> DimCompany | None:
    match = CompanyNormalizer().normalize(raw_name)
    if not match or not match.is_known_insurer or not match.company_name_normalized:
        return None
    normalized = match.company_name_normalized
    company = db.query(DimCompany).filter(DimCompany.company_name_normalized == normalized).first()
    if not company:
        company = DimCompany(
            company_name_normalized=normalized,
            company_name_raw=match.company_name_raw if match else raw_name,
            alias=raw_name,
            insurance_type=insurance_type or (match.insurance_type if match else None),
            insurance_type_default=insurance_type or (match.insurance_type_default if match else None),
            company_role=match.company_role if match else None,
            status_2024_2026=match.status_2024_2026 if match else "unknown",
            include_in_product_news_default=match.include_in_product_news_default if match else "Y",
            active_yn="Y",
            notes=match.notes if match else None,
        )
        db.add(company)
        db.flush()
    elif raw_name and match and match.match_type == "alias" and not company.company_name_raw:
        company.company_name_raw = raw_name
        db.flush()
    return company


def resolve_company_for_product(
    db: Session,
    raw_name: str | None,
    insurance_type: str | None = None,
    context_text: str | None = None,
    product_name: str | None = None,
) -> tuple[DimCompany | None, str | None, bool]:
    attribution = CompanyAttributionService().resolve_company_for_context(
        db,
        raw_company_name=raw_name,
        local_text=context_text,
        full_text=context_text,
        expected_insurance_type=None,
        product_or_subject_name=product_name,
    )
    if not attribution.company_name_normalized:
        return None, raw_name, True
    company = get_or_create_company(db, attribution.company_name_normalized, insurance_type or attribution.insurance_type)
    return company, attribution.matched_alias or raw_name, attribution.needs_review


def company_aliases_for_company(company: DimCompany | None) -> list[str]:
    if not company:
        return []
    aliases = [company.company_name_normalized, company.company_name_raw]
    aliases.extend([item.strip() for item in (company.alias or "").split("|") if item.strip()])
    aliases.extend(CompanyNormalizer().known_aliases(company.company_name_normalized))
    return [item for item in dict.fromkeys(alias for alias in aliases if alias)]


def upsert_product(db: Session, product: dict[str, Any], *, allow_unknown_company: bool = True) -> DimProduct | None:
    raw_name = product.get("raw_product_name") or product.get("normalized_product_name") or "unknown"
    original_raw_name = raw_name
    company, resolved_company_raw, company_needs_review = resolve_company_for_product(
        db,
        product.get("company_name") or product.get("company_name_raw"),
        product.get("insurance_type"),
        product.get("context_text"),
        product_name=raw_name,
    )
    company_aliases = company_aliases_for_company(company)
    validation = validate_product_name_before_save(
        raw_name,
        evidence_text=product.get("evidence_text"),
        context_text=product.get("context_text"),
        company_aliases=company_aliases,
    )
    if not validation.accepted:
        return None
    raw_name = validation.cleaned_name
    normalized_name = normalize_product_name(product.get("normalized_product_name") or raw_name, company_aliases)
    product_insurance_type = product.get("insurance_type")
    if company:
        company_insurance_type = company.insurance_type_default or company.insurance_type or "unknown"
        if product_insurance_type and product_insurance_type != "unknown" and product_insurance_type != company_insurance_type:
            company_needs_review = True
        product_insurance_type = company_insurance_type
    product_insurance_type = product_insurance_type or "unknown"
    company_id = company.company_id if company else None
    if company_id is None and not allow_unknown_company:
        return None
    company_name_for_key = company.company_name_normalized if company else None
    key = product_search_key(normalized_name, company_name_for_key)
    core_key_candidates = product_core_key_candidates(normalized_name or raw_name, company_aliases)
    product_core_key = core_key_candidates[0] if core_key_candidates else normalize_product_name_core(normalized_name or raw_name, company_aliases)
    product_identity_key = build_product_identity_key(company_id, normalized_name or raw_name, company_aliases)
    existing = _find_existing_product(db, company_id, key, product_core_key, product_identity_key, core_key_candidates)
    needs_review = bool(product.get("needs_review", True) or company_needs_review or not company_id)
    values = {
        "normalized_product_name": normalized_name,
        "raw_product_name": raw_name,
        "company_name_raw": resolved_company_raw or product.get("company_name") or product.get("company_name_raw"),
        "product_search_key": key,
        "product_core_key": product_core_key,
        "product_identity_key": product_identity_key,
        "company_id": company_id,
        "insurance_type": product_insurance_type,
        "release_year_month": product.get("release_year_month"),
        "release_year_month_basis": product.get("release_year_month_basis") or "unknown",
        "first_seen_month": product.get("first_seen_month") or current_year_month(),
        "primary_product_type_code": product.get("primary_product_type_code") or "UNKNOWN",
        "product_category_summary": product.get("product_category_summary"),
        "confidence_total": float(product.get("confidence_total") or 0.0),
        "needs_review": needs_review,
        "product_status": product.get("product_status") or "active",
        "canonical_product_id": product.get("canonical_product_id"),
        "partner_company_name": product.get("partner_company_name"),
        "partner_context_summary": product.get("partner_context_summary"),
    }
    if existing:
        conflicting_unique_keys: set[str] = set()
        search_key_owner = (
            db.query(DimProduct)
            .filter(
                DimProduct.company_id == company_id,
                DimProduct.product_search_key == key,
                DimProduct.product_id != existing.product_id,
            )
            .first()
        )
        if search_key_owner:
            conflicting_unique_keys.add("product_search_key")
        identity_key_owner = None
        if product_identity_key:
            identity_key_owner = (
                db.query(DimProduct)
                .filter(
                    DimProduct.product_identity_key == product_identity_key,
                    DimProduct.product_id != existing.product_id,
                )
                .first()
            )
        if identity_key_owner:
            conflicting_unique_keys.add("product_identity_key")
        for key_name, value in values.items():
            if key_name in conflicting_unique_keys:
                continue
            if key_name == "release_year_month" and value is None:
                continue
            if key_name == "product_status" and getattr(existing, "product_status", None) in {"active", "review"}:
                continue
            if value is not None or key_name in {"product_category_summary"}:
                setattr(existing, key_name, value)
        db.flush()
        record_product_alias(db, existing, raw_name, normalized_name, product_core_key, article_id=product.get("article_id"), source_type=product.get("source_type") or "llm")
        if original_raw_name and original_raw_name != raw_name:
            record_product_alias(
                db,
                existing,
                original_raw_name,
                normalized_name,
                product_core_key,
                article_id=product.get("article_id"),
                source_type=product.get("source_type") or "llm",
            )
        if product.get("partner_company_name"):
            add_product_partner(
                db,
                existing.product_id,
                product.get("partner_company_name"),
                article_id=product.get("article_id"),
                partner_role=product.get("partner_role") or "distribution_partner",
                evidence_text=product.get("partner_context_summary"),
                confidence=float(product.get("partner_confidence") or 0.8),
            )
        return existing
    created = DimProduct(**values)
    db.add(created)
    db.flush()
    if not created.canonical_product_id:
        created.canonical_product_id = created.product_id
    record_product_alias(db, created, raw_name, normalized_name, product_core_key, article_id=product.get("article_id"), source_type=product.get("source_type") or "llm")
    if original_raw_name and original_raw_name != raw_name:
        record_product_alias(
            db,
            created,
            original_raw_name,
            normalized_name,
            product_core_key,
            article_id=product.get("article_id"),
            source_type=product.get("source_type") or "llm",
        )
    if product.get("partner_company_name"):
        add_product_partner(
            db,
            created.product_id,
            product.get("partner_company_name"),
            article_id=product.get("article_id"),
            partner_role=product.get("partner_role") or "distribution_partner",
            evidence_text=product.get("partner_context_summary"),
            confidence=float(product.get("partner_confidence") or 0.8),
        )
    return created


def _find_existing_product(
    db: Session,
    company_id: int | None,
    product_search_key_value: str,
    product_core_key: str | None,
    product_identity_key: str | None,
    product_core_key_candidates: list[str] | None = None,
) -> DimProduct | None:
    if company_id is None:
        return None
    candidate_keys = [item for item in dict.fromkeys(product_core_key_candidates or [product_core_key]) if item]
    if product_identity_key:
        existing = db.query(DimProduct).filter(DimProduct.product_identity_key == product_identity_key).first()
        if existing:
            return canonical_product_for(db, existing)
    if candidate_keys:
        existing = db.query(DimProduct).filter(DimProduct.company_id == company_id, DimProduct.product_core_key.in_(candidate_keys)).first()
        if existing:
            return canonical_product_for(db, existing)
        alias = db.query(DimProductAlias).filter(DimProductAlias.company_id == company_id, DimProductAlias.product_core_key.in_(candidate_keys)).first()
        if alias:
            product = db.get(DimProduct, alias.product_id)
            return canonical_product_for(db, product) if product else None
        for existing_product in db.query(DimProduct).filter(DimProduct.company_id == company_id).all():
            existing_keys = set(product_core_key_candidates_for_existing(existing_product))
            if existing_keys.intersection(candidate_keys):
                return canonical_product_for(db, existing_product)
    existing = db.query(DimProduct).filter(DimProduct.product_search_key == product_search_key_value, DimProduct.company_id == company_id).first()
    return canonical_product_for(db, existing) if existing else None


def canonical_product_for(db: Session, product: DimProduct) -> DimProduct:
    if getattr(product, "product_status", None) == "merged" and product.merged_into_product_id:
        canonical = db.get(DimProduct, product.merged_into_product_id)
        if canonical:
            return canonical
    return product


def product_core_key_candidates_for_existing(product: DimProduct) -> list[str]:
    return product_core_key_candidates(product.normalized_product_name or product.raw_product_name, [])


def record_product_alias(
    db: Session,
    product: DimProduct,
    raw_product_name: str | None,
    normalized_product_name_candidate: str | None,
    product_core_key: str | None,
    *,
    article_id: int | None = None,
    source_type: str | None = None,
) -> DimProductAlias:
    raw = raw_product_name or product.raw_product_name
    existing = (
        db.query(DimProductAlias)
        .filter(
            DimProductAlias.product_id == product.product_id,
            DimProductAlias.raw_product_name == raw,
            DimProductAlias.article_id == article_id,
        )
        .first()
    )
    if existing:
        existing.last_seen_at = utcnow()
        existing.observation_count += 1
        product.alias_count = (product.alias_count or 0) + 1
        db.flush()
        return existing
    item = DimProductAlias(
        product_id=product.product_id,
        raw_product_name=raw,
        normalized_product_name_candidate=normalized_product_name_candidate,
        product_core_key=product_core_key,
        company_id=product.company_id,
        article_id=article_id,
        source_type=source_type,
    )
    db.add(item)
    product.alias_count = (product.alias_count or 0) + 1
    db.flush()
    return item


def record_product_observation(
    db: Session,
    *,
    product: DimProduct | None = None,
    article: FactArticle | None = None,
    raw_product_name: str | None,
    normalized_product_name_candidate: str | None = None,
    product_core_key: str | None = None,
    company_id: int | None = None,
    company_name_raw: str | None = None,
    partner_company_name: str | None = None,
    product_type_code: str | None = None,
    release_year_month: str | None = None,
    observation_context_text: str | None = None,
    candidate_type: str = "unknown",
    confidence: float = 0.0,
) -> FactProductObservation | None:
    raw = (raw_product_name or normalized_product_name_candidate or "").strip()
    if not raw:
        return None
    source_url = None
    if article:
        source_url = article.original_url or article.url
    product_id = product.product_id if product else None
    article_id = article.article_id if article else None
    candidate = candidate_type or "unknown"
    existing = (
        db.query(FactProductObservation)
        .filter(
            FactProductObservation.product_id == product_id,
            FactProductObservation.article_id == article_id,
            FactProductObservation.raw_product_name == raw,
            FactProductObservation.candidate_type == candidate,
        )
        .first()
    )
    if existing:
        existing.normalized_product_name_candidate = normalized_product_name_candidate or existing.normalized_product_name_candidate
        existing.product_core_key = product_core_key or existing.product_core_key
        existing.company_id = company_id if company_id is not None else existing.company_id
        existing.company_name_raw = company_name_raw or existing.company_name_raw
        existing.partner_company_name = partner_company_name or existing.partner_company_name
        existing.product_type_code = product_type_code or existing.product_type_code
        existing.release_year_month = release_year_month or existing.release_year_month
        existing.article_title = article.title if article else existing.article_title
        existing.article_description = article.description if article else existing.article_description
        existing.source_url = source_url or existing.source_url
        existing.observation_context_text = observation_context_text or existing.observation_context_text
        existing.confidence = max(float(existing.confidence or 0.0), float(confidence or 0.0))
        db.flush()
        return existing
    item = FactProductObservation(
        product_id=product_id,
        article_id=article_id,
        raw_product_name=raw,
        normalized_product_name_candidate=normalized_product_name_candidate,
        product_core_key=product_core_key,
        company_id=company_id if company_id is not None else (product.company_id if product else None),
        company_name_raw=company_name_raw or (product.company_name_raw if product else None),
        partner_company_name=partner_company_name or (product.partner_company_name if product else None),
        product_type_code=product_type_code or (product.primary_product_type_code if product else None),
        release_year_month=release_year_month or (product.release_year_month if product else None),
        article_title=article.title if article else None,
        article_description=article.description if article else None,
        source_url=source_url,
        observation_context_text=observation_context_text,
        candidate_type=candidate,
        confidence=float(confidence or 0.0),
    )
    db.add(item)
    db.flush()
    return item


def get_or_create_partner_company(db: Session, partner_name: str | None, partner_type: str = "unknown") -> DimPartnerCompany | None:
    name = (partner_name or "").strip()
    if not name:
        return None
    existing = db.query(DimPartnerCompany).filter(DimPartnerCompany.partner_name_normalized == name).first()
    if existing:
        return existing
    item = DimPartnerCompany(partner_name_normalized=name, alias=name, partner_type=partner_type)
    db.add(item)
    db.flush()
    return item


def add_product_partner(
    db: Session,
    product_id: int,
    partner_name: str | None,
    *,
    article_id: int | None = None,
    partner_role: str = "distribution_partner",
    partner_type: str = "unknown",
    evidence_text: str | None = None,
    confidence: float = 0.0,
) -> FactProductPartner | None:
    partner = get_or_create_partner_company(db, partner_name, partner_type=partner_type)
    if not partner:
        return None
    existing = (
        db.query(FactProductPartner)
        .filter(
            FactProductPartner.product_id == product_id,
            FactProductPartner.partner_id == partner.partner_id,
            FactProductPartner.article_id == article_id,
            FactProductPartner.partner_role == partner_role,
        )
        .first()
    )
    if existing:
        existing.evidence_text = existing.evidence_text or evidence_text
        existing.confidence = max(float(existing.confidence or 0), float(confidence or 0))
        db.flush()
        return existing
    item = FactProductPartner(
        product_id=product_id,
        partner_id=partner.partner_id,
        article_id=article_id,
        partner_role=partner_role,
        evidence_text=evidence_text,
        confidence=float(confidence or 0),
    )
    db.add(item)
    db.flush()
    return item


def add_type_assignment(db: Session, product_id: int, assignment: dict[str, Any], article_id: int | None = None) -> FactProductTypeAssignment:
    item = FactProductTypeAssignment(
        product_id=product_id,
        article_id=article_id,
        product_type_code=assignment.get("product_type_code") or assignment.get("code") or "UNKNOWN",
        assignment_role=assignment.get("assignment_role") or assignment.get("role") or "tag",
        classification_basis=assignment.get("classification_basis") or assignment.get("basis"),
        evidence_text=assignment.get("evidence_text"),
        confidence=float(assignment.get("confidence") or 0.0),
        needs_human_review=bool(assignment.get("needs_human_review", False)),
    )
    db.add(item)
    db.flush()
    return item


def add_structured_feature(db: Session, product_id: int, feature: dict[str, Any], article_id: int | None = None) -> FactProductStructuredFeature:
    sales_channel = feature.get("sales_channel")
    if sales_channel is None and feature.get("sales_channels") is not None:
        sales_channel = ",".join(feature.get("sales_channels") or [])
    item = FactProductStructuredFeature(
        product_id=product_id,
        article_id=article_id,
        join_age_min=feature.get("join_age_min"),
        join_age_max=feature.get("join_age_max"),
        notification_type=feature.get("notification_type"),
        sales_channel=sales_channel,
        simple_underwriting_yn=feature.get("simple_underwriting_yn"),
        non_face_to_face_yn=feature.get("non_face_to_face_yn"),
        renewal_type=feature.get("renewal_type"),
        payment_period=feature.get("payment_period"),
        coverage_period=feature.get("coverage_period"),
        evidence_text=feature.get("evidence_text"),
        confidence=float(feature.get("confidence") or 0.0),
    )
    db.add(item)
    db.flush()
    return item


def add_narrative_insight(db: Session, product_id: int, insight: dict[str, Any], article_id: int | None = None) -> FactProductNarrativeInsight:
    item = FactProductNarrativeInsight(
        product_id=product_id,
        article_id=article_id,
        feature_summary=insight.get("feature_summary"),
        product_development_summary=insight.get("product_development_summary"),
        marketing_summary=insight.get("marketing_summary"),
        target_customer_summary=insight.get("target_customer_summary"),
        underwriting_summary=insight.get("underwriting_summary"),
        channel_summary=insight.get("channel_summary"),
        coverage_summary=insight.get("coverage_summary"),
        sales_summary=insight.get("sales_summary"),
        differentiation_summary=insight.get("differentiation_summary"),
        risk_note_summary=insight.get("risk_note_summary"),
        missing_info_summary=insight.get("missing_info_summary"),
        missing_fields_json=json.dumps(insight.get("missing_fields") or insight.get("missing_fields_json") or [], ensure_ascii=False),
        evidence_text=insight.get("evidence_text"),
        confidence=float(insight.get("confidence") or 0.0),
        needs_review=bool(insight.get("needs_review", False)),
    )
    db.add(item)
    db.flush()
    return item


def add_major_coverage(db: Session, product_id: int, coverage: dict[str, Any], article_id: int | None = None) -> FactProductMajorCoverage:
    classifier = CoverageClassifier()
    classified = classifier.classify(coverage.get("coverage_name_normalized") or coverage.get("coverage_name_raw"), coverage.get("coverage_summary"))
    max_amount = coverage.get("max_amount_krw")
    if max_amount is None and coverage.get("raw_amount_text"):
        max_amount = normalize_coverage_amount(coverage.get("raw_amount_text"))
    item = FactProductMajorCoverage(
        product_id=product_id,
        article_id=article_id,
        coverage_name_raw=coverage.get("coverage_name_raw"),
        coverage_name_normalized=coverage.get("coverage_name_normalized") or coverage.get("coverage_name_raw"),
        risk_area=coverage.get("risk_area") or classified.risk_area,
        benefit_type=coverage.get("benefit_type") or classified.benefit_type,
        coverage_group=coverage.get("coverage_group") or classified.coverage_group,
        max_amount_krw=max_amount,
        raw_amount_text=coverage.get("raw_amount_text"),
        amount_basis=coverage.get("amount_basis"),
        condition_text=coverage.get("condition_text"),
        limit_text=coverage.get("limit_text"),
        coverage_summary=coverage.get("coverage_summary"),
        detail_level=coverage.get("detail_level") or "unknown",
        is_main_coverage=bool(coverage.get("is_main_coverage", True)),
        display_order=int(coverage.get("display_order") or 0),
        evidence_text=coverage.get("evidence_text"),
        confidence=float(coverage.get("confidence") or 0.0),
        needs_human_review=bool(coverage.get("needs_human_review", False)),
    )
    db.add(item)
    db.flush()
    if item.evidence_text:
        db.add(
            FactCoverageEvidence(
                coverage_id=item.coverage_id,
                product_id=product_id,
                article_id=article_id,
                raw_coverage_text=item.coverage_name_raw,
                evidence_text=item.evidence_text,
                extraction_confidence=item.confidence,
            )
        )
    return item


def add_sales_metric(db: Session, product_id: int, metric: dict[str, Any], article_id: int | None = None) -> FactSalesMetricStructured:
    item = FactSalesMetricStructured(
        product_id=product_id,
        article_id=article_id,
        metric_name=metric.get("metric_name") or "기타",
        metric_value=Decimal(str(metric.get("metric_value") or 0)),
        metric_unit=metric.get("metric_unit"),
        metric_period=metric.get("metric_period"),
        metric_basis=metric.get("metric_basis"),
        evidence_text=metric.get("evidence_text"),
        confidence=float(metric.get("confidence") or 0.0),
        needs_human_review=bool(metric.get("needs_human_review", False)),
    )
    db.add(item)
    db.flush()
    return item


def link_product_article(db: Session, product_id: int, article_id: int, confidence_total: float = 0.0, needs_review: bool = False, evidence_summary: str | None = None) -> None:
    existing = db.query(FactProductArticle).filter_by(product_id=product_id, article_id=article_id).first()
    if existing:
        update_release_month_if_unknown(db, product_id)
        return
    db.add(
        FactProductArticle(
            product_id=product_id,
            article_id=article_id,
            confidence_total=confidence_total,
            needs_review=needs_review,
            evidence_summary=evidence_summary,
        )
    )
    db.flush()
    update_release_month_if_unknown(db, product_id)


def update_release_month_if_unknown(db: Session, product_id: int) -> bool:
    product = db.get(DimProduct, product_id)
    if not product:
        return False
    if product.release_year_month and product.release_year_month_basis in PROTECTED_RELEASE_BASES:
        return False
    if product.release_year_month and product.release_year_month_basis not in INFERABLE_RELEASE_BASES:
        return False
    article = (
        db.query(FactArticle)
        .join(FactProductArticle, FactProductArticle.article_id == FactArticle.article_id)
        .filter(FactProductArticle.product_id == product_id, FactArticle.pub_date.isnot(None))
        .order_by(FactArticle.pub_date.asc(), FactArticle.article_id.asc())
        .first()
    )
    if not article or not article.pub_date:
        return False
    inferred_month = article.pub_date.strftime("%Y-%m")
    if product.release_year_month_basis == "earliest_related_article_month" and product.release_year_month and product.release_year_month <= inferred_month:
        return False
    if product.release_year_month and product.release_year_month_basis not in INFERABLE_RELEASE_BASES:
        return False
    product.release_year_month = inferred_month
    product.release_year_month_basis = "earliest_related_article_month"
    product.release_year_month_source_article_id = article.article_id
    product.release_year_month_source_type = article.source_api
    product.release_year_month_inferred_at = utcnow()
    db.flush()
    return True


def backfill_unknown_release_months(db: Session) -> int:
    product_ids = [
        row[0]
        for row in db.query(DimProduct.product_id)
        .filter(
            (DimProduct.release_year_month.is_(None))
            | (DimProduct.release_year_month_basis.is_(None))
            | (DimProduct.release_year_month_basis.in_(["unknown", "first_seen_only", "earliest_related_article_month"]))
        )
        .all()
    ]
    updated = 0
    for product_id in product_ids:
        if update_release_month_if_unknown(db, product_id):
            updated += 1
    return updated


def create_manual_ingestion(db: Session, input_type: str, title: str | None = None, text: str | None = None, input_json: dict[str, Any] | None = None, submitted_by: str | None = None) -> FactManualIngestion:
    item = FactManualIngestion(
        input_type=input_type,
        input_title=title,
        input_text=text,
        input_json=json.dumps(input_json, ensure_ascii=False) if input_json is not None else None,
        submitted_by=submitted_by,
        processing_status="pending",
    )
    db.add(item)
    db.flush()
    return item


def create_llm_run(db: Session, **kwargs: Any) -> FactLLMRun:
    item = FactLLMRun(**kwargs)
    db.add(item)
    db.flush()
    return item


def create_comparison(db: Session, **kwargs: Any) -> FactExtractionComparison:
    item = FactExtractionComparison(**kwargs)
    db.add(item)
    db.flush()
    return item


def create_field_audit(db: Session, comparison_id: int, field_check: dict[str, Any]) -> FactExtractionFieldAudit:
    item = FactExtractionFieldAudit(
        comparison_id=comparison_id,
        field_path=field_check.get("field_path", ""),
        extractor_value=json.dumps(field_check.get("extracted_value"), ensure_ascii=False),
        verifier_verdict=field_check.get("verdict"),
        suggested_value=json.dumps(field_check.get("suggested_value"), ensure_ascii=False),
        evidence_text=field_check.get("evidence_text"),
        severity=field_check.get("severity") or "low",
        final_value=json.dumps(field_check.get("final_value"), ensure_ascii=False) if "final_value" in field_check else None,
        final_basis=field_check.get("suggested_basis") or field_check.get("final_basis"),
    )
    db.add(item)
    db.flush()
    return item
