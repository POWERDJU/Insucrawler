from __future__ import annotations

from dataclasses import dataclass


INVALID_NONLIFE_TYPES = {
    "DEATH_WHOLELIFE",
    "VARIABLE_UL",
}

INVALID_LIFE_TYPES = {
    "AUTO",
    "TRAVEL_LEISURE",
    "PET",
    "PROPERTY_EXPENSE",
}


@dataclass(frozen=True)
class ProductTypeIndustryValidationResult:
    valid: bool
    needs_review: bool
    exclusion_reason: str | None = None
    proposed_status: str | None = None
    reason: str | None = None


class ProductTypeIndustryValidationService:
    """Validate representative product type against insurer industry.

    Secondary product type assignments are intentionally ignored. The dashboard
    and exports use only dim_product.primary_product_type_code.
    """

    excluded_status = "excluded_invalid_industry_product_type"
    exclusion_reason = "invalid_industry_product_type"

    def validate(
        self,
        *,
        insurance_type: str | None,
        primary_product_type_code: str | None,
        product_name: str | None = None,
        company_name: str | None = None,
    ) -> ProductTypeIndustryValidationResult:
        normalized_industry = (insurance_type or "").strip()
        type_code = (primary_product_type_code or "UNKNOWN").strip().upper()
        if normalized_industry in {"", "unknown", "UNKNOWN"}:
            return ProductTypeIndustryValidationResult(
                valid=True,
                needs_review=True,
                reason="insurance_type_unknown",
            )
        if normalized_industry == "손해보험" and type_code in INVALID_NONLIFE_TYPES:
            return self._invalid(normalized_industry, type_code, product_name, company_name)
        if normalized_industry == "생명보험" and type_code in INVALID_LIFE_TYPES:
            return self._invalid(normalized_industry, type_code, product_name, company_name)
        return ProductTypeIndustryValidationResult(valid=True, needs_review=False)

    def _invalid(
        self,
        insurance_type: str,
        type_code: str,
        product_name: str | None,
        company_name: str | None,
    ) -> ProductTypeIndustryValidationResult:
        return ProductTypeIndustryValidationResult(
            valid=False,
            needs_review=True,
            exclusion_reason=self.exclusion_reason,
            proposed_status=self.excluded_status,
            reason=f"{insurance_type} company/product '{company_name or ''}' has incompatible representative product type {type_code}: {product_name or ''}".strip(),
        )
