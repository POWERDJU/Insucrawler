from __future__ import annotations

from app.db.models import DimCompany


DISALLOWED_PRODUCT_COMPANY_ROLES = {
    "foreign_branch",
    "reinsurer",
    "reinsurer_or_foreign_branch",
    "association",
    "agency",
    "affiliate",
    "distribution",
    "platform",
    "partner",
    "bank",
    "card",
    "short_term_pet_insurer",
}


def is_product_news_eligible_company(company: DimCompany | None) -> bool:
    """Return whether a company can own ordinary product-news records.

    The company dictionary includes reinsurers, foreign branches, and partners
    so they can be detected in articles, but those rows must not become the
    insurer for product catalog rows unless explicitly modeled elsewhere.
    """

    if company is None:
        return False
    if (company.include_in_product_news_default or "Y") != "Y":
        return False
    role = (company.company_role or "").strip().lower()
    return role not in DISALLOWED_PRODUCT_COMPANY_ROLES
