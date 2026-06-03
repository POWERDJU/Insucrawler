from app.db import repository
from app.db.models import FactArticle, FactProductObservation
from app.utils.hashing import sha256_text


def test_product_observation_records_candidate_context(db_session):
    article = FactArticle(
        source_api="naver",
        title="Alpha launches Mini Care Insurance",
        description="The product covers children and device-related risks.",
        url="https://example.test/mini",
        original_url="https://example.test/mini-original",
        content_hash=sha256_text("observation-mini"),
    )
    db_session.add(article)
    db_session.flush()

    observation = repository.record_product_observation(
        db_session,
        article=article,
        raw_product_name="Mini Care Insurance",
        normalized_product_name_candidate="Mini Care Insurance",
        product_core_key="minicareinsurance",
        company_name_raw="Alpha Insurance",
        partner_company_name="Alpha Telecom",
        product_type_code="CHILD_ADULT_CHILD",
        release_year_month="2026-01",
        observation_context_text="Alpha Telecom customers can buy Mini Care Insurance.",
        candidate_type="launch_name",
        confidence=0.91,
    )
    db_session.commit()

    assert observation is not None
    saved = db_session.query(FactProductObservation).one()
    assert saved.raw_product_name == "Mini Care Insurance"
    assert saved.source_url == "https://example.test/mini-original"
    assert saved.candidate_type == "launch_name"
    assert saved.product_id is None
