from app.normalizers.product_name_normalizer import validate_product_name_before_save


def test_discourse_fragment_issneun_insurance_is_rejected():
    result = validate_product_name_before_save("\uc788\ub294\ubcf4\ud5d8")

    assert result.accepted is False
    assert result.reason == "weak_or_generic_product_name"
