from app.services.product_canonicalization_service import ProductCanonicalizationService


class _Identity:
    def __init__(self, name: str):
        self.raw_product_name = name
        self.normalized_product_name_candidate = None


class _Product:
    def __init__(self, name: str):
        self.identity = _Identity(name)


def test_kidsphone_context_candidates_are_one_canonical_product():
    service = ProductCanonicalizationService()
    names = [
        "키즈폰 전용 어린이 미니 보험",
        "키즈폰 이용 고객인 어린이를 위한 미니 보험",
        "LG유플러스 키즈폰 특화 미니 보험",
        "이번 보험",
        "키즈폰 고객 대상 미니 보험",
        "미니 보험",
        "어린이 특화 미니 보험",
        "키즈폰 이용 고객을 위한 어린이 전용 미니 보험",
        "키즈폰 최초 어린이 미니 보험",
        "LG유플러스 키즈폰 고객 위한 미니 보험",
        "키즈폰 미니 보험",
        "키즈케어 보험",
        "키즈폰 고객 특화 미니 보험",
        "키즈폰 대상 미니 보험",
        "어린이 특화 보험",
    ]

    plans = service.plan_extraction_products(
        [_Product(name) for name in names],
        "LG유플러스 키즈폰 고객을 위한 미니 보험을 출시했다.",
    )

    created = [plan for plan in plans if plan.create_product]
    assert len(created) == 1
    assert "키즈폰" in created[0].canonical_name
    assert "미니보험" in created[0].canonical_name
    assert "미니 보험" in created[0].alias_names
    assert "이번 보험" in created[0].alias_names
    assert "어린이 특화 보험" in created[0].alias_names
    assert created[0].partner_company_name == "LG유플러스"


def test_partner_phrase_is_not_insurer_company_candidate():
    service = ProductCanonicalizationService()

    assert service.classify_product_name_candidate("LG유플러스 키즈폰 특화 미니 보험") == "partner_brand_phrase"
    assert service.canonical_name_from_raw("LG유플러스 키즈폰 특화 미니 보험") == "키즈폰 특화 미니보험"
    assert service.detect_partner_name("LG유플러스 키즈폰 특화 미니 보험") == "LG유플러스"


def test_ai_same_product_judge_result_controls_auto_merge_threshold():
    service = ProductCanonicalizationService()
    left = service.plan_extraction_products([_Product("A 미니 보험")])[0]
    right = service.plan_extraction_products([_Product("B 키즈케어 보험")])[0]

    decision = service.judge_same_product(
        left,
        right,
        ai_judge=lambda *_: {
            "same_product": True,
            "confidence": 0.92,
            "canonical_product_name": "키즈폰 어린이 미니보험",
            "merge_reason": "same article and same coverage context",
            "alias_names": ["A 미니 보험", "B 키즈케어 보험"],
        },
    )

    assert decision.same_product is True
    assert decision.should_auto_merge is True
    assert decision.decision_source == "ai_same_product_judge"

    review_decision = service.judge_same_product(
        left,
        right,
        ai_judge=lambda *_: {"same_product": True, "confidence": 0.7},
    )
    assert review_decision.should_auto_merge is False
    assert review_decision.needs_human_review is True
