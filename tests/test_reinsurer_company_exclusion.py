from app.db.models import DimCompany
from app.services.product_company_eligibility import is_product_news_eligible_company


def test_reinsurer_and_foreign_branch_are_not_product_news_eligible(db_session):
    generali = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "제너럴리").one()
    korean_re = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "코리안리재보험").one()
    samsung = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "삼성화재").one()

    assert is_product_news_eligible_company(generali) is False
    assert is_product_news_eligible_company(korean_re) is False
    assert is_product_news_eligible_company(samsung) is True
