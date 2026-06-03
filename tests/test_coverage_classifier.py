from app.classifiers.coverage_classifier import CoverageClassifier


def test_cancer_diagnosis():
    result = CoverageClassifier().classify("암진단비")
    assert result.risk_area == "암"
    assert result.benefit_type == "진단"


def test_cancer_treatment():
    result = CoverageClassifier().classify("항암약물치료비")
    assert result.risk_area == "암"
    assert result.benefit_type == "치료"


def test_disease_surgery():
    result = CoverageClassifier().classify("질병수술비")
    assert result.risk_area == "질병"
    assert result.benefit_type == "수술"


def test_daily_hospitalization():
    result = CoverageClassifier().classify("입원일당")
    assert result.benefit_type in {"입원", "일당"}


def test_driver_costs():
    result = CoverageClassifier().classify("교통사고처리지원금")
    assert result.risk_area == "운전자"
    assert result.benefit_type == "비용보상"


def test_lawyer_costs():
    result = CoverageClassifier().classify("변호사선임비용")
    assert result.risk_area == "운전자"
    assert result.benefit_type == "법률비용"
