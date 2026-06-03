from app.db.models import DimCompany
from app.db.seed_master_data import seed_all


def test_company_seed_contains_2024_2026_master(db_session):
    life_count = db_session.query(DimCompany).filter(DimCompany.insurance_type == "생명보험").count()
    assert life_count >= 22

    required = {
        "MG손해보험",
        "예별손해보험",
        "캐롯손해보험",
        "마이브라운반려동물전문보험",
    }
    rows = db_session.query(DimCompany).filter(DimCompany.company_name_normalized.in_(required)).all()
    assert {row.company_name_normalized for row in rows} == required
    assert all(row.include_in_product_news_default == "Y" for row in rows)


def test_reinsurers_and_foreign_branches_excluded_by_default(db_session):
    rows = (
        db_session.query(DimCompany)
        .filter(DimCompany.company_name_normalized.in_(["코리안리재보험", "미쓰이스미토모해상화재보험 한국지점"]))
        .all()
    )
    assert {row.company_name_normalized for row in rows} == {"코리안리재보험", "미쓰이스미토모해상화재보험 한국지점"}
    assert all(row.include_in_product_news_default == "N" for row in rows)


def test_company_seed_is_idempotent(db_session):
    before = db_session.query(DimCompany).count()
    seed_all(db_session)
    after = db_session.query(DimCompany).count()
    assert after == before

    names = [row[0] for row in db_session.query(DimCompany.company_name_normalized).all()]
    assert len(names) == len(set(names))
