# Full Qwen Review Result

- review_job_id: 6
- status: completed
- mode: apply
- date_from: all
- date_to: all
- crawl_job_id: 4
- article_count: 3390
- product_candidate_count: 51
- exclusive_candidate_count: 5
- qwen_processed_count: 1
- qwen_provider_called_count: 1
- qwen_remaining_count: 0

## Artifacts

- plan: `data\exports\full_qwen_review_plan_6.csv`
- conflicts: `data\exports\full_qwen_review_conflicts_6.csv`
- applied: `data\exports\full_qwen_review_applied_6.csv`

## Raw Summary

```json
{
  "full_review_job_id": 6,
  "mode": "apply",
  "review_scope": "all",
  "date_from": null,
  "date_to": null,
  "crawl_job_id": 4,
  "target_counts": {
    "articles": 3390,
    "products": 51,
    "exclusive_rights": 5
  },
  "qwen_exhaustive": false,
  "rule_review": {},
  "qwen": {
    "status": "completed",
    "apply": true,
    "crawl_job_id": 4,
    "date_from": null,
    "date_to": null,
    "exhaustive": false,
    "products": {
      "scanned": 1,
      "processed": 1,
      "provider_called": 1,
      "accepted": 1,
      "reviewed": 0,
      "rejected": 0,
      "discarded_by_rule": 0,
      "skipped_not_risky": 0,
      "failed": 0,
      "remaining_estimate": 0,
      "errors": []
    },
    "exclusive_rights": {
      "scanned": 0,
      "processed": 0,
      "provider_called": 0,
      "accepted": 0,
      "reviewed": 0,
      "rejected": 0,
      "discarded_by_rule": 0,
      "skipped_not_risky": 0,
      "failed": 0,
      "remaining_estimate": 0,
      "errors": []
    }
  },
  "status": "completed",
  "finished_at": "2026-06-09T15:09:52.415243"
}
```
