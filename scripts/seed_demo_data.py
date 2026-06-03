from __future__ import annotations

import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal  # noqa: E402
from app.db.migrations import init_db  # noqa: E402
from app.db.database import engine  # noqa: E402
from sqlalchemy import or_  # noqa: E402

from app.db.models import DimProduct, FactArticle  # noqa: E402
from app.db.repository import link_product_article  # noqa: E402
from app.db.seed_master_data import seed_all  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402
from app.utils.hashing import article_dedup_hash  # noqa: E402
from app.utils.dates import current_year_month  # noqa: E402


DEMO_PRODUCTS = [
    {
        "product": {
            "raw_product_name": "간편 암보험 A",
            "normalized_product_name": "간편 암보험 A",
            "company_name": "한화생명",
            "insurance_type": "생명보험",
            "release_year_month": "2026-05",
            "release_year_month_basis": "manual",
            "first_seen_month": "2026-05",
            "primary_product_type_code": "CANCER",
            "confidence_total": 0.86,
            "needs_review": False,
        },
        "product_type_assignments": [
            {"product_type_code": "CANCER", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "간편 암보험 A 출시", "confidence": 0.92},
            {"product_type_code": "SIMPLIFIED_IMPAIRED", "assignment_role": "secondary", "classification_basis": "demo", "evidence_text": "간편고지 암보험", "confidence": 0.88},
        ],
        "features": {"join_age_min": 30, "join_age_max": 75, "notification_type": "간편고지", "sales_channels": ["대면", "GA"], "renewal_type": "갱신형", "payment_period": "20년납", "coverage_period": "100세", "evidence_text": "30세부터 75세까지 간편고지로 가입 가능", "confidence": 0.84},
        "narrative_insights": {"feature_summary": "유병력자도 가입 가능한 암 진단 및 항암치료 중심 상품", "product_development_summary": "고령·유병자 암 보장 수요를 겨냥", "marketing_summary": "간편고지와 고액 암진단비를 강조", "underwriting_summary": "간편고지 기반으로 인수 문턱을 낮춤", "channel_summary": "대면과 GA 채널 중심", "coverage_summary": "암진단비와 항암약물치료비 중심", "missing_info_summary": "세부 면책기간과 감액기간 확인 필요"},
        "major_coverages": [
            {"coverage_name_raw": "암진단비", "coverage_name_normalized": "암진단비", "risk_area": "암", "benefit_type": "진단", "coverage_group": "암보장", "max_amount_krw": 100000000, "raw_amount_text": "최대 1억원", "amount_basis": "최초 1회, 세부 조건 확인 필요", "condition_text": "암 진단 확정 시", "coverage_summary": "암 진단 시 최대 1억원", "detail_level": "exact_coverage", "display_order": 1, "evidence_text": "암진단비 최대 1억원", "confidence": 0.91},
            {"coverage_name_raw": "항암약물치료비", "coverage_name_normalized": "항암약물치료비", "risk_area": "암", "benefit_type": "치료", "coverage_group": "암보장", "max_amount_krw": 50000000, "raw_amount_text": "최대 5천만원", "amount_basis": "치료 항목별 한도 확인 필요", "condition_text": "항암약물치료 시", "coverage_summary": "항암약물치료비 보장", "detail_level": "exact_coverage", "display_order": 2, "evidence_text": "항암약물치료비 최대 5천만원", "confidence": 0.88},
        ],
        "sales_metrics": [{"metric_name": "판매건수", "metric_value": 12000, "metric_unit": "건", "metric_period": "출시 후 1개월", "metric_basis": "상품 단위 데모 수치", "evidence_text": "출시 후 1개월 판매건수 1만2000건", "confidence": 0.82}],
        "articles": [
            {"title": "한화생명, 간편 암보험 A 출시", "pub_date": "2026-05-10", "url": "https://example.com/demo/cancer-a-1"},
            {"title": "간편고지 암보험 경쟁 심화", "pub_date": "2026-05-18", "url": "https://example.com/demo/cancer-a-2"},
        ],
    },
    {
        "product": {"raw_product_name": "어린이 종합건강보험 B", "normalized_product_name": "어린이 종합건강보험 B", "company_name": "삼성화재", "insurance_type": "손해보험", "release_year_month": "2026-04", "release_year_month_basis": "manual", "first_seen_month": "2026-04", "primary_product_type_code": "CHILD_ADULT_CHILD", "confidence_total": 0.84, "needs_review": False},
        "product_type_assignments": [
            {"product_type_code": "CHILD_ADULT_CHILD", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "어린이 종합건강보험 B", "confidence": 0.91},
            {"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "secondary", "classification_basis": "demo", "evidence_text": "종합건강보험", "confidence": 0.86},
        ],
        "features": {"join_age_min": 0, "join_age_max": 30, "notification_type": "일반고지", "sales_channels": ["대면", "CM"], "renewal_type": "비갱신형", "payment_period": "20년납", "coverage_period": "100세", "evidence_text": "어린이와 청년층을 위한 종합건강 보장", "confidence": 0.82},
        "narrative_insights": {"feature_summary": "자녀와 청년층의 질병·상해 보장을 묶은 종합형 상품", "product_development_summary": "어른이 보험 수요를 반영", "marketing_summary": "생애 초기부터 긴 보장기간을 강조", "underwriting_summary": "일반고지 기반", "channel_summary": "대면 및 온라인 채널 판매", "coverage_summary": "질병수술비와 상해입원일당 중심", "missing_info_summary": "태아 가입 특약 여부 확인 필요"},
        "major_coverages": [
            {"coverage_name_raw": "질병수술비", "coverage_name_normalized": "질병수술비", "risk_area": "질병", "benefit_type": "수술", "coverage_group": "질병보장", "condition_text": "질병 수술 시", "coverage_summary": "질병 수술 비용 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "질병수술비 보장", "confidence": 0.85},
            {"coverage_name_raw": "상해입원일당", "coverage_name_normalized": "상해입원일당", "risk_area": "상해", "benefit_type": "입원", "coverage_group": "상해보장", "condition_text": "상해 입원 시", "coverage_summary": "상해 입원일당 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "상해입원일당 보장", "confidence": 0.84},
        ],
        "sales_metrics": [{"metric_name": "월초보험료", "metric_value": 350000000, "metric_unit": "원", "metric_period": "출시월", "metric_basis": "상품 단위 데모 수치", "evidence_text": "출시월 월초보험료 3억5000만원", "confidence": 0.8}],
        "articles": [{"title": "삼성화재, 어린이 종합건강보험 B 선보여", "pub_date": "2026-04-12", "url": "https://example.com/demo/child-b"}],
    },
    {
        "product": {"raw_product_name": "운전자보험 C", "normalized_product_name": "운전자보험 C", "company_name": "현대해상", "insurance_type": "손해보험", "release_year_month": "2026-03", "release_year_month_basis": "manual", "first_seen_month": "2026-03", "primary_product_type_code": "ACCIDENT_DRIVER", "confidence_total": 0.88, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "ACCIDENT_DRIVER", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "운전자보험 C", "confidence": 0.94}],
        "features": {"join_age_min": 18, "join_age_max": 70, "notification_type": "일반고지", "sales_channels": ["CM", "대면"], "renewal_type": "갱신형", "payment_period": "전기납", "coverage_period": "20년", "evidence_text": "운전자 비용 보장을 강화", "confidence": 0.83},
        "narrative_insights": {"feature_summary": "교통사고 처리 비용과 법률비용 중심 운전자보험", "product_development_summary": "운전자 법률비용 보장 수요 반영", "marketing_summary": "교통사고처리지원금과 변호사선임비용 강조", "underwriting_summary": "일반고지", "channel_summary": "온라인 및 대면 판매", "coverage_summary": "교통사고처리지원금, 변호사선임비용, 벌금 보장", "missing_info_summary": "도로교통법 개정 반영 조건 확인 필요"},
        "major_coverages": [
            {"coverage_name_raw": "교통사고처리지원금", "coverage_name_normalized": "교통사고처리지원금", "risk_area": "운전자", "benefit_type": "비용보상", "coverage_group": "운전자보장", "coverage_summary": "교통사고 처리 비용 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "교통사고처리지원금 보장", "confidence": 0.89},
            {"coverage_name_raw": "변호사선임비용", "coverage_name_normalized": "변호사선임비용", "risk_area": "운전자", "benefit_type": "법률비용", "coverage_group": "운전자보장", "coverage_summary": "변호사 선임 비용 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "변호사선임비용 보장", "confidence": 0.88},
            {"coverage_name_raw": "벌금", "coverage_name_normalized": "벌금", "risk_area": "운전자", "benefit_type": "법률비용", "coverage_group": "운전자보장", "coverage_summary": "운전자 벌금 보장", "detail_level": "coverage_group", "display_order": 3, "evidence_text": "벌금 보장", "confidence": 0.86},
        ],
        "articles": [{"title": "현대해상, 운전자보험 C 출시", "pub_date": "2026-03-08", "url": "https://example.com/demo/driver-c"}],
    },
    {
        "product": {"raw_product_name": "치매간병보험 D", "normalized_product_name": "치매간병보험 D", "company_name": "한화생명", "insurance_type": "생명보험", "release_year_month": "2026-02", "release_year_month_basis": "manual", "first_seen_month": "2026-02", "primary_product_type_code": "DEMENTIA_CARE", "confidence_total": 0.83, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "DEMENTIA_CARE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "치매간병보험 D", "confidence": 0.92}],
        "features": {"join_age_min": 40, "join_age_max": 80, "notification_type": "일반고지", "sales_channels": ["대면"], "renewal_type": "비갱신형", "payment_period": "20년납", "coverage_period": "종신", "evidence_text": "치매와 간병비를 함께 보장", "confidence": 0.81},
        "narrative_insights": {"feature_summary": "고령층 치매 진단과 간병 비용을 묶은 상품", "product_development_summary": "장기요양 리스크 확대에 대응", "marketing_summary": "가족 간병 부담 완화 메시지", "underwriting_summary": "고령 가입 심사 조건 확인 필요", "channel_summary": "설계사 중심", "coverage_summary": "치매진단비와 간병인사용비 중심", "missing_info_summary": "장기요양등급 연계 조건 확인 필요"},
        "major_coverages": [
            {"coverage_name_raw": "치매진단비", "coverage_name_normalized": "치매진단비", "risk_area": "치매", "benefit_type": "진단", "coverage_group": "치매보장", "coverage_summary": "치매 진단 시 보험금 지급", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "치매진단비 보장", "confidence": 0.85},
            {"coverage_name_raw": "간병인사용비", "coverage_name_normalized": "간병인사용비", "risk_area": "간병", "benefit_type": "비용보상", "coverage_group": "간병보장", "coverage_summary": "간병인 사용 비용 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "간병인사용비 보장", "confidence": 0.84},
        ],
        "articles": [{"title": "한화생명, 치매간병보험 D 출시", "pub_date": "2026-02-14", "url": "https://example.com/demo/dementia-d"}],
    },
    {
        "product": {"raw_product_name": "종신보험 E", "normalized_product_name": "종신보험 E", "company_name": "교보생명", "insurance_type": "생명보험", "release_year_month": "2026-01", "release_year_month_basis": "manual", "first_seen_month": "2026-01", "primary_product_type_code": "DEATH_WHOLELIFE", "confidence_total": 0.87, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "DEATH_WHOLELIFE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "종신보험 E", "confidence": 0.94}],
        "features": {"join_age_min": 15, "join_age_max": 65, "notification_type": "일반고지", "sales_channels": ["대면", "방카슈랑스"], "renewal_type": "비갱신형", "payment_period": "20년납", "coverage_period": "종신", "evidence_text": "사망보장을 종신까지 제공", "confidence": 0.86},
        "narrative_insights": {"feature_summary": "일반사망보험금을 중심으로 한 전통형 종신보험", "product_development_summary": "가족 생활자금 보장 니즈 대응", "marketing_summary": "평생 사망보장 강조", "underwriting_summary": "일반심사", "channel_summary": "대면과 방카슈랑스", "coverage_summary": "일반사망보험금 중심", "missing_info_summary": "해지환급금 구조 확인 필요"},
        "major_coverages": [{"coverage_name_raw": "일반사망보험금", "coverage_name_normalized": "일반사망보험금", "risk_area": "사망", "benefit_type": "사망", "coverage_group": "사망보장", "coverage_summary": "사망 시 보험금 지급", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "일반사망보험금 보장", "confidence": 0.9}],
        "articles": [{"title": "교보생명, 종신보험 E 개정 출시", "pub_date": "2026-01-19", "url": "https://example.com/demo/wholelife-e"}],
    },
    {
        "product": {"raw_product_name": "주택화재보험 F", "normalized_product_name": "주택화재보험 F", "company_name": "DB손해보험", "insurance_type": "손해보험", "release_year_month": "2025-12", "release_year_month_basis": "manual", "first_seen_month": "2025-12", "primary_product_type_code": "PROPERTY_EXPENSE", "confidence_total": 0.85, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "PROPERTY_EXPENSE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "주택화재보험 F", "confidence": 0.93}],
        "features": {"join_age_min": 19, "join_age_max": 80, "notification_type": "일반고지", "sales_channels": ["CM", "대면"], "renewal_type": "갱신형", "payment_period": "전기납", "coverage_period": "1년", "evidence_text": "주택 화재와 배상책임을 보장", "confidence": 0.84},
        "narrative_insights": {"feature_summary": "주택 화재손해와 배상책임을 함께 보장하는 생활밀착형 상품", "product_development_summary": "주거 리스크와 일상 배상책임 수요 대응", "marketing_summary": "화재손해와 배상책임 묶음 보장 강조", "underwriting_summary": "목적물 정보 확인 필요", "channel_summary": "온라인과 대면 판매", "coverage_summary": "화재손해보장과 배상책임 중심", "missing_info_summary": "목적물 소재지와 건물급수별 인수 조건 확인 필요"},
        "major_coverages": [
            {"coverage_name_raw": "화재손해보장", "coverage_name_normalized": "화재손해보장", "risk_area": "화재손해", "benefit_type": "손해보상", "coverage_group": "재물보장", "coverage_summary": "화재로 인한 주택 손해 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "화재손해보장 제공", "confidence": 0.87},
            {"coverage_name_raw": "배상책임", "coverage_name_normalized": "배상책임", "risk_area": "배상책임", "benefit_type": "배상책임", "coverage_group": "배상책임", "coverage_summary": "일상생활 중 배상책임 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "배상책임 보장", "confidence": 0.86},
        ],
        "articles": [{"title": "DB손해보험, 주택화재보험 F 출시", "pub_date": "2025-12-22", "url": "https://example.com/demo/fire-f"}],
    },
    {
        "product": {"raw_product_name": "MG손보 건강보험 상품 예시", "normalized_product_name": "MG손보 건강보험 상품 예시", "company_name": "MG손보", "insurance_type": "손해보험", "release_year_month": "2024-03", "release_year_month_basis": "manual", "first_seen_month": "2024-03", "primary_product_type_code": "HEALTH_COMPREHENSIVE", "confidence_total": 0.79, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "MG손보 건강보험 상품", "confidence": 0.86}],
        "narrative_insights": {"feature_summary": "MG손해보험 과거 건강보험 상품 뉴스 확인용 데모", "coverage_summary": "질병수술비와 상해입원일당 중심", "missing_info_summary": "가교보험사 계약 이전 이후 판매/관리 상태 확인 필요", "evidence_text": "MG손보 건강보험 상품 관련 기사 예시"},
        "major_coverages": [
            {"coverage_name_raw": "질병수술비", "coverage_name_normalized": "질병수술비", "risk_area": "질병", "benefit_type": "수술", "coverage_group": "건강보장", "coverage_summary": "질병 수술 비용 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "질병수술비 보장", "confidence": 0.8},
            {"coverage_name_raw": "상해입원일당", "coverage_name_normalized": "상해입원일당", "risk_area": "상해", "benefit_type": "입원", "coverage_group": "상해보장", "coverage_summary": "상해 입원일당 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "상해입원일당 보장", "confidence": 0.8},
        ],
        "articles": [{"title": "MG손보 건강보험 상품 관련 기사 예시", "pub_date": "2024-03-15", "url": "https://example.com/demo/mg-health"}],
    },
    {
        "product": {"raw_product_name": "예별손보 MG손보 계약관리 예시", "normalized_product_name": "예별손보 MG손보 계약관리 예시", "company_name": "예별손보", "insurance_type": "손해보험", "release_year_month": "2025-07", "release_year_month_basis": "first_seen_only", "first_seen_month": "2025-07", "primary_product_type_code": "OTHER", "confidence_total": 0.72, "needs_review": True},
        "product_type_assignments": [{"product_type_code": "OTHER", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "MG손보 계약 유지관리 목적 가교보험사", "confidence": 0.72, "needs_human_review": True}],
        "narrative_insights": {"feature_summary": "신규 판매 상품이 아니라 MG손보 계약 유지관리 목적 가교보험사 이슈", "coverage_summary": "상품 보장 정보 없음", "missing_info_summary": "상품 단위 출시 여부가 아니므로 피벗 해석 주의", "evidence_text": "예별손보 MG손보 계약 이전 관련 기사 예시", "needs_review": True},
        "major_coverages": [],
        "articles": [{"title": "예별손보 MG손보 계약 이전 관련 기사 예시", "pub_date": "2025-07-01", "url": "https://example.com/demo/yebyul-bridge"}],
    },
    {
        "product": {"raw_product_name": "캐롯 디지털 운전자보험 예시", "normalized_product_name": "캐롯 디지털 운전자보험 예시", "company_name": "캐롯손보", "insurance_type": "손해보험", "release_year_month": "2024-06", "release_year_month_basis": "manual", "first_seen_month": "2024-06", "primary_product_type_code": "ACCIDENT_DRIVER", "confidence_total": 0.81, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "ACCIDENT_DRIVER", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "캐롯손보 디지털보험 상품", "confidence": 0.85}],
        "narrative_insights": {"feature_summary": "캐롯손해보험 합병 전 디지털보험 상품 확인용 데모", "coverage_summary": "자동차/운전자 비용보상 중심", "missing_info_summary": "한화손보 합병 이후 상품 승계 상태 확인 필요", "evidence_text": "캐롯손보 디지털보험 상품 관련 기사 예시"},
        "major_coverages": [{"coverage_name_raw": "자동차/운전자 관련 비용보상", "coverage_name_normalized": "운전자 비용보상", "risk_area": "운전자", "benefit_type": "비용보상", "coverage_group": "운전자보장", "coverage_summary": "운전자 관련 비용 보상 예시", "detail_level": "marketing_statement", "display_order": 1, "evidence_text": "자동차/운전자 관련 비용보상", "confidence": 0.76}],
        "articles": [{"title": "캐롯손보 디지털보험 상품 관련 기사 예시", "pub_date": "2024-06-11", "url": "https://example.com/demo/carrot-digital"}],
    },
    {
        "product": {"raw_product_name": "마이브라운 펫보험 예시", "normalized_product_name": "마이브라운 펫보험 예시", "company_name": "마이브라운", "insurance_type": "손해보험", "release_year_month": "2026-01", "release_year_month_basis": "manual", "first_seen_month": "2026-01", "primary_product_type_code": "OTHER", "confidence_total": 0.78, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "OTHER", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "반려동물 전문보험사", "confidence": 0.78}],
        "narrative_insights": {"feature_summary": "신규 소액단기보험사 성격의 반려동물 전문보험 예시", "coverage_summary": "반려동물 치료비와 수술비 중심", "missing_info_summary": "상품 인가 및 실제 판매 개시일 확인 필요", "evidence_text": "마이브라운 반려동물 전문보험사 관련 기사 예시"},
        "major_coverages": [
            {"coverage_name_raw": "반려동물 치료비", "coverage_name_normalized": "반려동물 치료비", "risk_area": "기타", "benefit_type": "치료", "coverage_group": "펫보험", "coverage_summary": "반려동물 치료비 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "반려동물 치료비", "confidence": 0.8},
            {"coverage_name_raw": "반려동물 수술비", "coverage_name_normalized": "반려동물 수술비", "risk_area": "기타", "benefit_type": "수술", "coverage_group": "펫보험", "coverage_summary": "반려동물 수술비 보장", "detail_level": "coverage_group", "display_order": 2, "evidence_text": "반려동물 수술비", "confidence": 0.8},
        ],
        "articles": [{"title": "마이브라운 반려동물 전문보험사 관련 기사 예시", "pub_date": "2026-01-09", "url": "https://example.com/demo/mybrown-pet"}],
    },
    {
        "product": {"raw_product_name": "DGB생명 건강보험 alias 예시", "normalized_product_name": "iM라이프 건강보험 alias 예시", "company_name": "DGB생명", "insurance_type": "생명보험", "release_year_month": "2024-09", "release_year_month_basis": "manual", "first_seen_month": "2024-09", "primary_product_type_code": "HEALTH_COMPREHENSIVE", "confidence_total": 0.82, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "DGB생명 iM라이프 사명변경 및 상품", "confidence": 0.84}],
        "narrative_insights": {"feature_summary": "DGB생명 alias가 iM라이프생명으로 정규화되는지 확인하는 데모", "coverage_summary": "건강보험 보장군 중심", "missing_info_summary": "사명변경 전후 상품명 승계 확인 필요", "evidence_text": "DGB생명 iM라이프 사명변경 및 상품 관련 기사 예시"},
        "major_coverages": [{"coverage_name_raw": "질병진단비", "coverage_name_normalized": "질병진단비", "risk_area": "질병", "benefit_type": "진단", "coverage_group": "건강보장", "coverage_summary": "질병 진단비 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "질병진단비 보장", "confidence": 0.8}],
        "articles": [{"title": "DGB생명 iM라이프 사명변경 및 상품 관련 기사 예시", "pub_date": "2024-09-05", "url": "https://example.com/demo/imlife-dgb"}],
    },
    {
        "product": {"raw_product_name": "에이스손해보험 건강보험 alias 예시", "normalized_product_name": "라이나손해보험 건강보험 alias 예시", "company_name": "에이스손해보험", "insurance_type": "손해보험", "release_year_month": "2024-10", "release_year_month_basis": "manual", "first_seen_month": "2024-10", "primary_product_type_code": "HEALTH_COMPREHENSIVE", "confidence_total": 0.8, "needs_review": False},
        "product_type_assignments": [{"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "classification_basis": "demo", "evidence_text": "에이스손보 라이나손보 브랜드 변경", "confidence": 0.82}],
        "narrative_insights": {"feature_summary": "에이스손해보험 alias가 라이나손해보험으로 정규화되는지 확인하는 데모", "coverage_summary": "건강보험 보장군 중심", "missing_info_summary": "브랜드 변경 전후 상품 승계 확인 필요", "evidence_text": "에이스손보 라이나손보 브랜드 변경 관련 기사 예시"},
        "major_coverages": [{"coverage_name_raw": "상해치료비", "coverage_name_normalized": "상해치료비", "risk_area": "상해", "benefit_type": "치료", "coverage_group": "건강보장", "coverage_summary": "상해 치료비 보장", "detail_level": "coverage_group", "display_order": 1, "evidence_text": "상해치료비 보장", "confidence": 0.78}],
        "articles": [{"title": "에이스손보 라이나손보 브랜드 변경 관련 기사 예시", "pub_date": "2024-10-22", "url": "https://example.com/demo/lina-ace"}],
    },
]


def ensure_article(db, article: dict, query_group: str, product_name: str) -> FactArticle:
    content_hash = article_dedup_hash(article["url"], article["title"], "")
    existing = db.query(FactArticle).filter(FactArticle.content_hash == content_hash).first()
    if existing:
        return existing
    row = FactArticle(
        source_api="demo",
        title=article["title"],
        description=f"{product_name} 관련 데모 기사",
        publisher="Demo News",
        url=article["url"],
        original_url=article["url"],
        pub_date=datetime.fromisoformat(article["pub_date"]),
        query="demo",
        query_group=query_group,
        content_hash=content_hash,
        extraction_status="extracted",
    )
    db.add(row)
    db.flush()
    return row


def seed_demo_data(db) -> dict[str, int | str]:
    inserted = 0
    skipped = 0
    service = IngestionService()
    demo_month = current_year_month()
    for index, original_item in enumerate(DEMO_PRODUCTS):
        item = deepcopy(original_item)
        if index < 2:
            item["product"]["release_year_month"] = demo_month
            item["product"]["first_seen_month"] = demo_month
            item["product"]["release_year_month_basis"] = "manual"
            for article_index, article in enumerate(item.get("articles") or [], start=1):
                article["pub_date"] = f"{demo_month}-{min(8 + article_index, 28):02d}"
        product_name = item["product"]["normalized_product_name"]
        existing = (
            db.query(DimProduct)
            .filter(
                or_(
                    DimProduct.normalized_product_name == product_name,
                    DimProduct.raw_product_name == item["product"]["raw_product_name"],
                )
            )
            .first()
        )
        if existing:
            skipped += 1
            continue
        existing_product_ids = {row[0] for row in db.query(DimProduct.product_id).all()}
        product = service.upsert_structured_product(db, item, create_manual_record=False)
        for article in item["articles"]:
            article_row = ensure_article(db, article, "demo", product_name)
            link_product_article(
                db,
                product.product_id,
                article_row.article_id,
                confidence_total=item["product"]["confidence_total"],
                needs_review=False,
                evidence_summary=article["title"],
            )
        if product.product_id in existing_product_ids:
            skipped += 1
        else:
            inserted += 1
    db.commit()
    return {"status": "ok", "inserted_products": inserted, "skipped_existing_products": skipped}


def main() -> None:
    init_db(engine)
    with SessionLocal() as db:
        seed_all(db)
        result = seed_demo_data(db)
    print(result)


if __name__ == "__main__":
    main()
