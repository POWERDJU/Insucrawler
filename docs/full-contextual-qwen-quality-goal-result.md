# Full Contextual Qwen Quality Goal Check

```json
{
  "status": "PASS",
  "failures": [],
  "scope_counts": {
    "products": 1481,
    "exclusive_rights": 915
  },
  "checks": [
    {
      "check": "product_name_reject",
      "id": 1348,
      "ok": true,
      "reason": "bad_sentence_fragment"
    },
    {
      "check": "product_name_reject",
      "id": 1996,
      "ok": true,
      "reason": "bad_sentence_fragment"
    },
    {
      "check": "product_article_reject",
      "id": 1574,
      "ok": true,
      "reason": "non_insurance_financial_product"
    },
    {
      "check": "product_article_reject",
      "id": 1723,
      "ok": true,
      "reason": "multi_financial_institution_roundup"
    },
    {
      "check": "product_article_reject",
      "id": 1996,
      "ok": true,
      "reason": "industry_trend_multi_company_article"
    },
    {
      "check": "exclusive_subject_reject",
      "id": 53,
      "ok": true,
      "reason": "weak_subject_without_resolved_reference"
    },
    {
      "check": "exclusive_subject_reject",
      "id": 151,
      "ok": true,
      "reason": "subject_not_in_local_exclusive_context"
    },
    {
      "check": "exclusive_subject_reject",
      "id": 1134,
      "ok": true,
      "reason": "subject_not_in_local_exclusive_context"
    },
    {
      "check": "exclusive_subject_reject",
      "id": 1294,
      "ok": true,
      "reason": "subject_not_in_local_exclusive_context"
    },
    {
      "check": "exclusive_subject_reject",
      "id": 1343,
      "ok": true,
      "reason": "subject_not_in_local_exclusive_context"
    },
    {
      "check": "exclusive_article_reject",
      "id": 47,
      "ok": true,
      "reason": "industry_trend_multi_company_article"
    }
  ]
}
```
