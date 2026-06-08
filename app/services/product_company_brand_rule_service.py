from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct, DimProductAlias, FactProductObservation, FactQwenReviewAudit
from app.normalizers.product_name_normalizer import build_product_identity_key, normalize_product_name_core, product_search_key
from app.services.company_attribution_service import CompanyAttributionService, ProductNameBrandCompanyResult
from app.utils.dates import utcnow


PRODUCT_COMPANY_BRAND_RULE_TASK_TYPE = "product_company_brand_rule_review"
PRODUCT_COMPANY_BRAND_RULE_APPLY_REASON = "product_name_unique_company_brand"


@dataclass(frozen=True)
class ProductCompanyBrandRuleRow:
    product_id: int
    product_name: str
    old_company_id: int | None
    old_company_name: str | None
    new_company_id: int | None
    new_company_name: str | None
    matched_brand: str | None
    candidates: tuple[str, ...]
    action: str
    reason: str


class ProductCompanyBrandRuleService:
    """Correct company attribution when a product name embeds a unique insurer brand."""

    def __init__(self, attribution: CompanyAttributionService | None = None) -> None:
        self.attribution = attribution or CompanyAttributionService()

    def build_plan(
        self,
        db: Session,
        *,
        product_id: int | None = None,
        limit: int | None = None,
    ) -> list[ProductCompanyBrandRuleRow]:
        query = (
            db.query(DimProduct)
            .filter(DimProduct.merged_into_product_id.is_(None))
            .filter(DimProduct.product_status.in_(["active", "review", "provisional"]))
            .order_by(DimProduct.product_id.asc())
        )
        if product_id is not None:
            query = query.filter(DimProduct.product_id == product_id)
        if limit:
            query = query.limit(limit)
        rows: list[ProductCompanyBrandRuleRow] = []
        for product in query.all():
            result = self._best_brand_result(db, product)
            current_company = db.get(DimCompany, product.company_id) if product.company_id else None
            current_company_name = current_company.company_name_normalized if current_company else product.company_name_raw
            if result.ambiguous:
                if current_company_name and current_company_name in result.candidate_company_names:
                    continue
                rows.append(
                    ProductCompanyBrandRuleRow(
                        product_id=product.product_id,
                        product_name=product.normalized_product_name or product.raw_product_name,
                        old_company_id=product.company_id,
                        old_company_name=current_company_name,
                        new_company_id=None,
                        new_company_name=None,
                        matched_brand=result.matched_brand,
                        candidates=result.candidate_company_names,
                        action="mark_review_for_qwen",
                        reason=result.reason,
                    )
                )
                continue
            if not result.company_id or result.company_id == product.company_id:
                continue
            target_company = db.get(DimCompany, result.company_id)
            if not target_company:
                continue
            duplicate = self._conflicting_product(db, product, target_company)
            if duplicate:
                rows.append(
                    ProductCompanyBrandRuleRow(
                        product_id=product.product_id,
                        product_name=product.normalized_product_name or product.raw_product_name,
                        old_company_id=product.company_id,
                        old_company_name=current_company_name,
                        new_company_id=target_company.company_id,
                        new_company_name=target_company.company_name_normalized,
                        matched_brand=result.matched_brand,
                        candidates=result.candidate_company_names,
                        action="mark_review_conflict",
                        reason=f"{result.reason}; target duplicate product_id={duplicate.product_id}",
                    )
                )
                continue
            rows.append(
                ProductCompanyBrandRuleRow(
                    product_id=product.product_id,
                    product_name=product.normalized_product_name or product.raw_product_name,
                    old_company_id=product.company_id,
                    old_company_name=current_company_name,
                    new_company_id=target_company.company_id,
                    new_company_name=target_company.company_name_normalized,
                    matched_brand=result.matched_brand,
                    candidates=result.candidate_company_names,
                    action="update_company",
                    reason=result.reason,
                )
            )
        return rows

    def apply_plan(self, db: Session, rows: list[ProductCompanyBrandRuleRow]) -> dict[str, int]:
        summary = {"update_company": 0, "mark_review_for_qwen": 0, "mark_review_conflict": 0, "skipped": 0}
        for row in rows:
            product = db.get(DimProduct, row.product_id)
            if not product:
                summary["skipped"] += 1
                continue
            before = self._product_snapshot(db, product)
            if row.action == "update_company" and row.new_company_id:
                target_company = db.get(DimCompany, row.new_company_id)
                if not target_company or self._conflicting_product(db, product, target_company):
                    self._mark_review(product)
                    summary["mark_review_conflict"] += 1
                    self._add_audit(db, product, row, before, self._product_snapshot(db, product), "review_conflict")
                    continue
                self._update_product_company(db, product, target_company)
                summary["update_company"] += 1
                self._add_audit(db, product, row, before, self._product_snapshot(db, product), "applied")
            elif row.action in {"mark_review_for_qwen", "mark_review_conflict"}:
                self._mark_review(product)
                summary[row.action] += 1
                self._add_audit(db, product, row, before, self._product_snapshot(db, product), "review")
            else:
                summary["skipped"] += 1
        db.flush()
        return summary

    def run(
        self,
        db: Session,
        *,
        apply: bool = False,
        product_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        rows = self.build_plan(db, product_id=product_id, limit=limit)
        summary = {"plan_count": len(rows), "actions": self._action_counts(rows), "applied": {}}
        if apply:
            summary["applied"] = self.apply_plan(db, rows)
        return summary | {"rows": [asdict(row) for row in rows]}

    def _best_brand_result(self, db: Session, product: DimProduct) -> ProductNameBrandCompanyResult:
        names = [
            product.normalized_product_name,
            product.raw_product_name,
        ]
        results = [self.attribution.resolve_company_from_product_name_brand(db, name) for name in names if name]
        actionable = [item for item in results if item.ambiguous or item.company_id]
        if not actionable:
            return ProductNameBrandCompanyResult(
                company_id=None,
                company_name_normalized=None,
                insurance_type=None,
                matched_brand=None,
                matched_token=None,
                candidate_company_names=(),
                ambiguous=False,
                confidence=0.0,
                reason="no company brand token found in product name",
            )
        actionable.sort(key=lambda item: (not item.ambiguous, -len(item.matched_token or ""), -(item.confidence or 0.0)))
        unique = [item for item in actionable if item.company_id]
        if unique:
            unique.sort(key=lambda item: (-len(item.matched_token or ""), -(item.confidence or 0.0), item.company_name_normalized or ""))
            return unique[0]
        return actionable[0]

    @staticmethod
    def _action_counts(rows: list[ProductCompanyBrandRuleRow]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.action] = counts.get(row.action, 0) + 1
        return counts

    @staticmethod
    def _company_aliases(company: DimCompany) -> list[str]:
        values = [company.company_name_normalized, company.company_name_raw]
        values.extend(item.strip() for item in (company.alias or "").split("|") if item.strip())
        return [item for item in dict.fromkeys(value for value in values if value)]

    def _conflicting_product(self, db: Session, product: DimProduct, target_company: DimCompany) -> DimProduct | None:
        new_key = product_search_key(product.normalized_product_name or product.raw_product_name, target_company.company_name_normalized)
        return (
            db.query(DimProduct)
            .filter(DimProduct.product_id != product.product_id)
            .filter(DimProduct.company_id == target_company.company_id)
            .filter(DimProduct.product_search_key == new_key)
            .filter(DimProduct.merged_into_product_id.is_(None))
            .first()
        )

    def _update_product_company(self, db: Session, product: DimProduct, target_company: DimCompany) -> None:
        old_company_id = product.company_id
        aliases = self._company_aliases(target_company)
        product.company_id = target_company.company_id
        product.company_name_raw = target_company.company_name_normalized
        product.insurance_type = target_company.insurance_type_default or target_company.insurance_type or product.insurance_type or "unknown"
        product.product_core_key = normalize_product_name_core(product.raw_product_name or product.normalized_product_name, aliases)
        product.product_identity_key = build_product_identity_key(
            target_company.company_id,
            product.raw_product_name or product.normalized_product_name,
            aliases,
        )
        product.product_search_key = product_search_key(
            product.normalized_product_name or product.raw_product_name,
            target_company.company_name_normalized,
        )
        product.needs_review = False
        product.consolidation_status = product.consolidation_status or "pending"
        product.updated_at = utcnow()
        for alias in db.query(DimProductAlias).filter(DimProductAlias.product_id == product.product_id).all():
            if alias.company_id in {None, old_company_id}:
                alias.company_id = target_company.company_id
        for observation in db.query(FactProductObservation).filter(FactProductObservation.product_id == product.product_id).all():
            if observation.company_id in {None, old_company_id}:
                observation.company_id = target_company.company_id
                observation.company_name_raw = target_company.company_name_normalized

    @staticmethod
    def _mark_review(product: DimProduct) -> None:
        product.needs_review = True
        product.consolidation_status = "review"
        product.updated_at = utcnow()

    @staticmethod
    def _product_snapshot(db: Session, product: DimProduct) -> dict[str, Any]:
        company = db.get(DimCompany, product.company_id) if product.company_id else None
        return {
            "product_id": product.product_id,
            "normalized_product_name": product.normalized_product_name,
            "raw_product_name": product.raw_product_name,
            "company_id": product.company_id,
            "company_name": company.company_name_normalized if company else product.company_name_raw,
            "insurance_type": product.insurance_type,
            "product_search_key": product.product_search_key,
            "product_identity_key": product.product_identity_key,
            "needs_review": bool(product.needs_review),
            "consolidation_status": product.consolidation_status,
        }

    @staticmethod
    def _add_audit(
        db: Session,
        product: DimProduct,
        row: ProductCompanyBrandRuleRow,
        before: dict[str, Any],
        after: dict[str, Any],
        apply_status: str,
    ) -> None:
        db.add(
            FactQwenReviewAudit(
                target_type="product",
                target_id=product.product_id,
                task_type=PRODUCT_COMPANY_BRAND_RULE_TASK_TYPE,
                provider="rule",
                decision=row.action,
                confidence=0.9 if row.action == "update_company" else 0.45,
                reason=row.reason,
                evidence_text=row.matched_brand,
                before_json=json.dumps(before, ensure_ascii=False),
                after_json=json.dumps(after, ensure_ascii=False),
                warnings_json=json.dumps({"candidates": row.candidates}, ensure_ascii=False),
                hard_gate_status="passed" if row.action == "update_company" else "not_applicable",
                apply_status=apply_status,
                override_reason=PRODUCT_COMPANY_BRAND_RULE_APPLY_REASON,
            )
        )
