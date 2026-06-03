from app.extractors.product_launch_candidate import (
    extract_launch_product_candidates,
    is_negative_product_name,
    normalize_launch_product_name,
)


SHINHANEZ_TEXT = """
신한EZ손해보험은 2026년 새해를 맞아 고객 혜택을 대폭 강화한 '신한SOL 다이렉트' 보험의 할인 구조 개편과 함께 신규 상품을 선보였다고 밝혔다.

해당 할인 혜택은 운전자보험(티맵 안전운전 점수 연계 '쏠Drive' 서비스), 건강보험(애플·삼성헬스 걸음 수 연동 '쏠Walk' 서비스), 주택화재보험(소화설비 구비 주택 할인) 등 주요 상품 라인업에 적용된다.

또한 신한EZ손해보험은 최근 건강 관리에 대한 사회적 관심이 높아지는 트렌드를 반영해 '면역질환보험'을 신규 출시했다.

해당 상품은 특정 자가면역질환을 비롯해 대상포진, 통풍, 갑상선 기능 저하 등 현대인에게 발병률이 높은 주요 면역 관련 질환을 집중적으로 보장한다.
"""


def test_extract_launch_product_candidate_prefers_immune_product():
    candidates = extract_launch_product_candidates(SHINHANEZ_TEXT)

    assert any(item.normalized_name == "면역질환보험" for item in candidates)
    immune = next(item for item in candidates if item.normalized_name == "면역질환보험")
    assert immune.trigger.startswith("신규 출시")
    assert immune.confidence >= 0.9
    assert "면역질환보험" in immune.evidence_text


def test_service_and_discount_names_are_rejected_as_products():
    for name in ["신한SOL", "신한SOL 다이렉트", "신한SOL EZ손보", "쏠Drive", "쏠Walk", "삼성 인터넷", "삼성인터넷"]:
        assert is_negative_product_name(name)
        assert normalize_launch_product_name(name) is None


def test_negative_prefix_with_real_insurance_product_keeps_product_part():
    assert not is_negative_product_name("신한SOL 면역질환보험")
    assert normalize_launch_product_name("신한SOL 면역질환보험") == "면역질환보험"
    assert not is_negative_product_name("삼성 인터넷 (신간편) 뇌심건강보험")
