# Full Qwen Review Result

- review_job_id: 4
- status: running
- mode: apply
- date_from: 2025-01-01
- date_to: 2026-05-31
- crawl_job_id: all
- article_count: 79741
- product_candidate_count: 1091
- exclusive_candidate_count: 866
- qwen_processed_count: 0
- qwen_provider_called_count: 0
- qwen_remaining_count: 0

## Artifacts

- plan: `data\exports\full_qwen_review_plan_4.csv`
- conflicts: `data\exports\full_qwen_review_conflicts_4.csv`
- applied: `data\exports\full_qwen_review_applied_4.csv`

## Raw Summary

```json
{
  "full_review_job_id": 4,
  "mode": "apply",
  "review_scope": "all",
  "date_from": "2025-01-01",
  "date_to": "2026-05-31",
  "crawl_job_id": null,
  "target_counts": {
    "articles": 79741,
    "products": 1091,
    "exclusive_rights": 866
  },
  "qwen_exhaustive": false,
  "rule_review": {
    "products": {
      "consolidation_job_id": 23,
      "status": "completed",
      "trigger_type": "full_review",
      "mode": "rule_only_apply",
      "target_new_product_count": 1516,
      "observation_count": 10463,
      "provisional_product_count": 156,
      "block_count": 43,
      "auto_merge_count": 2,
      "llm_review_count": 0,
      "manual_review_count": 41,
      "llm_call_count": 0,
      "estimated_cost_usd": 0.0,
      "started_at": "2026-06-08T13:05:34.155539",
      "finished_at": "2026-06-08T13:05:56.090574",
      "created_at": "2026-06-08T13:05:34.157607",
      "error_message": null,
      "blocks": [
        {
          "block_id": 629,
          "block_key": "company:21|partner:unknown|type:HEALTH_COMPREHENSIVE,OTHER|month:2025-08|ids:980,1027,1031,1033,1035|component:1",
          "company_id": 21,
          "partner_company_name": null,
          "release_month_window": "2025-08~2025-08",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE",
            "OTHER"
          ],
          "candidate_product_ids": [
            980,
            1027,
            1031,
            1033,
            1035,
            1037,
            1038,
            1039,
            1041
          ],
          "observation_ids": [
            5227,
            5259,
            5530,
            5542,
            5548,
            5554,
            5558,
            5560,
            5562,
            5568,
            7146
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:21|partner:unknown|type:HEALTH_COMPREHENSIVE,OTHER|month:2025-08|ids:980,1027,1031,1033,1035\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 9, \"candidate_names\": [\"통합건강보험\", \"재해 건강보험\", \"재해보장 강화한 신상품 3종\", \"판매 채널별 통합건강보험\", \"고객 맞춤형 재해 통합 건강보험\", \"재해 건강 보장 신상품 3종\", \"재해보장 강화 맞춤설계 건강보험\", \"판매채널별 재해 건강보험\", \"재해 통합건강보험\"], \"candidate_product_ids\": [980, 1027, 1031, 1033, 1035, 1037, 1038, 1039, 1041], \"shared_high_info_tokens\": [\"nh농협생명\", \"재해\"], \"family_signatures\": [\"3종강화한재해\", \"3종재해\", \"맞춤설계재해\", \"맞춤재해통합\", \"재해통합\", \"판매채널별재해\", \"판매채널별통합\"], \"family_tokens\": [\"3종\", \"강화맞춤설계\", \"강화한\", \"맞춤\", \"맞춤설계\", \"재해\", \"재해통합\", \"채널별\", \"통합\", \"판매\", \"판매채널별\", \"판매채널별재해\", \"판매채널별통합\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 980, \"right\": 1027, \"name_similarity\": 0.6667, \"context_similarity\": 0.3366}, {\"left\": 980, \"right\": 1031, \"name_similarity\": 0.1111, \"context_similarity\": 0.1816}, {\"left\": 980, \"right\": 1033, \"name_similarity\": 0.82, \"context_similarity\": 0.3742}, {\"left\": 980, \"right\": 1035, \"name_similarity\": 0.82, \"context_similarity\": 0.3742}, {\"left\": 980, \"right\": 1037, \"name_similarity\": 0.3529, \"context_similarity\": 0.258}, {\"left\": 980, \"right\": 1038, \"name_similarity\": 0.4, \"context_similarity\": 0.2641}, {\"left\": 980, \"right\": 1039, \"name_similarity\": 0.4706, \"context_similarity\": 0.2933}, {\"left\": 980, \"right\": 1041, \"name_similarity\": 0.82, \"context_similarity\": 0.3716}, {\"left\": 1027, \"right\": 1031, \"name_similarity\": 0.3333, \"context_similarity\": 0.3321}, {\"left\": 1027, \"right\": 1033, \"name_similarity\": 0.4706, \"context_similarity\": 0.4715}, {\"left\": 1027, \"right\": 1035, \"name_similarity\": 0.6316, \"context_similarity\": 0.5013}, {\"left\": 1027, \"right\": 1037, \"name_similarity\": 0.6667, \"context_similarity\": 0.4477}, {\"left\": 1027, \"right\": 1038, \"name_similarity\": 0.6, \"context_similarity\": 0.4543}, {\"left\": 1027, \"right\": 1039, \"name_similarity\": 0.82, \"context_similarity\": 0.4311}, {\"left\": 1027, \"right\": 1041, \"name_similarity\": 0.8571, \"context_similarity\": 0.5225}, {\"left\": 1031, \"right\": 1033, \"name_similarity\": 0.087, \"context_similarity\": 0.2158}, {\"left\": 1031, \"right\": 1035, \"name_similarity\": 0.24, \"context_similarity\": 0.2444}, {\"left\": 1031, \"right\": 1037, \"name_similarity\": 0.7826, \"context_similarity\": 0.5304}, {\"left\": 1031, \"right\": 1038, \"name_similarity\": 0.4615, \"context_similarity\": 0.3196}, {\"left\": 1031, \"right\": 1039, \"name_similarity\": 0.2609, \"context_similarity\": 0.2425}]}, \"parent_summary\": {\"candidate_count\": 9, \"candidate_product_ids\": [1041, 1039, 1038, 1037, 1035, 1033, 1031, 1027, 980], \"family_signatures\": [\"3종강화한재해\", \"3종재해\", \"맞춤설계재해\", \"맞춤재해통합\", \"재해통합\", \"판매채널별재해\", \"판매채널별통합\"]}}",
          "status": "review"
        },
        {
          "block_id": 630,
          "block_key": "company:38|partner:카카오페이|type:CHILD_ADULT_CHILD,HEALTH_COMPREHENSIVE,OTHER|month:2025-06|ids:44,186,385,680,793|component:1",
          "company_id": 38,
          "partner_company_name": "카카오페이",
          "release_month_window": "2025-06~2026-04",
          "product_type_codes": [
            "CHILD_ADULT_CHILD",
            "HEALTH_COMPREHENSIVE",
            "OTHER"
          ],
          "candidate_product_ids": [
            44,
            186,
            385,
            680,
            793,
            953,
            1174,
            1587,
            1588
          ],
          "observation_ids": [
            266,
            843,
            929,
            1015,
            1993,
            2003,
            2771,
            3744,
            4536,
            4541,
            5165,
            6041,
            7875,
            7877
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:38|partner:카카오페이|type:CHILD_ADULT_CHILD,HEALTH_COMPREHENSIVE,OTHER|month:2024-05|ids:44,169,186,187,206\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 9, \"candidate_names\": [\"생애주기형 장기보험\", \"성인 대상 건강보험\", \"건강보험\", \"성인대상 첫 건강보험\", \"성인 건강보험\", \"장기보험\", \"성인 대상 장기보험\", \"영유아 초중학생 대상 건강보험\", \"성인 대상 건강보험 상품\"], \"candidate_product_ids\": [44, 186, 385, 680, 793, 953, 1174, 1587, 1588], \"shared_high_info_tokens\": [\"카카오페이손해\"], \"family_signatures\": [\"생애주기\", \"영유아초중학생\"], \"family_tokens\": [\"생애주기\", \"성인\", \"영유아\", \"영유아초중학생\", \"장기\", \"초중학생\"], \"partner_candidates\": [\"카카오페이\", \"카카페이\"], \"context_scores\": [{\"left\": 44, \"right\": 186, \"name_similarity\": 0.2353, \"context_similarity\": 0.2842}, {\"left\": 44, \"right\": 385, \"name_similarity\": 0.3077, \"context_similarity\": 0.3694}, {\"left\": 44, \"right\": 680, \"name_similarity\": 0.2222, \"context_similarity\": 0.1345}, {\"left\": 44, \"right\": 793, \"name_similarity\": 0.2667, \"context_similarity\": 0.267}, {\"left\": 44, \"right\": 953, \"name_similarity\": 0.82, \"context_similarity\": 0.4205}, {\"left\": 44, \"right\": 1174, \"name_similarity\": 0.4706, \"context_similarity\": 0.3369}, {\"left\": 44, \"right\": 1587, \"name_similarity\": 0.2727, \"context_similarity\": 0.4068}, {\"left\": 44, \"right\": 1588, \"name_similarity\": 0.2105, \"context_similarity\": 0.3926}, {\"left\": 186, \"right\": 385, \"name_similarity\": 0.82, \"context_similarity\": 0.4767}, {\"left\": 186, \"right\": 680, \"name_similarity\": 0.9412, \"context_similarity\": 0.398}, {\"left\": 186, \"right\": 793, \"name_similarity\": 1.0, \"context_similarity\": 0.6028}, {\"left\": 186, \"right\": 953, \"name_similarity\": 0.3333, \"context_similarity\": 0.3818}, {\"left\": 186, \"right\": 1174, \"name_similarity\": 0.75, \"context_similarity\": 0.4761}, {\"left\": 186, \"right\": 1587, \"name_similarity\": 0.5714, \"context_similarity\": 0.4006}, {\"left\": 186, \"right\": 1588, \"name_similarity\": 0.82, \"context_similarity\": 0.4706}, {\"left\": 385, \"right\": 680, \"name_similarity\": 0.82, \"context_similarity\": 0.3358}, {\"left\": 385, \"right\": 793, \"name_similarity\": 0.82, \"context_similarity\": 0.4429}, {\"left\": 385, \"right\": 953, \"name_similarity\": 0.5, \"context_similarity\": 0.3341}, {\"left\": 385, \"right\": 1174, \"name_similarity\": 0.3333, \"context_similarity\": 0.2902}, {\"left\": 385, \"right\": 1587, \"name_similarity\": 0.82, \"context_similarity\": 0.4303}]}, \"parent_summary\": {\"candidate_count\": 25, \"candidate_product_ids\": [2216, 1980, 1979, 1588, 1587, 1360, 1359, 1358, 1174, 1111, 953, 830, 794, 793, 700, 684, 680, 669, 668, 385, 206, 187, 186, 169, 44], \"family_signatures\": [\"2024년영유아\", \"간편함담은\", \"모바일에최적화된\", \"생애주기\", \"수족구진단비영유아\", \"영유아초중학생\", \"장기일반\", \"초중학생\"]}}",
          "status": "review"
        },
        {
          "block_id": 631,
          "block_key": "company:28|partner:unknown|type:HEALTH_COMPREHENSIVE,SIMPLIFIED_IMPAIRED|month:2025-05|ids:759,760,761,770,808|component:1",
          "company_id": 28,
          "partner_company_name": null,
          "release_month_window": "2025-05~2025-07",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE",
            "SIMPLIFIED_IMPAIRED"
          ],
          "candidate_product_ids": [
            759,
            760,
            761,
            770,
            808,
            809,
            929,
            930
          ],
          "observation_ids": [
            4373,
            4375,
            4379,
            4409,
            4599,
            4601,
            4609,
            5085,
            5087,
            5089
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:unknown|type:HEALTH_COMPREHENSIVE,SIMPLIFIED_IMPAIRED,SPECIFIC_DISEASE|month:2025-05|ids:759,760,761,770,808\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 8, \"candidate_names\": [\"건보 간편보험\", \"암 뇌 심장질환 치료비특약 건강 간편보험\", \"간편보험\", \"건강 간편보험\", \"간편보험 고고 새로고침\", \"고고 새로고침\", \"유병자 간편보험 고고 새로고침\", \"간편보험 고고\"], \"candidate_product_ids\": [759, 760, 761, 770, 808, 809, 929, 930], \"shared_high_info_tokens\": [\"간편\", \"삼성화재\"], \"family_signatures\": [\"간편새로고침\", \"건보간편\", \"고고새로고침\", \"새로고침유병자\", \"암심장질환치료비특약\"], \"family_tokens\": [\"간편\", \"건보\", \"건보간편\", \"고고\", \"고고새로고침\", \"새로고침\", \"심장질환\", \"암\", \"유병자\", \"유병자간편\", \"치료비특약\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 759, \"right\": 760, \"name_similarity\": 0.4348, \"context_similarity\": 0.4357}, {\"left\": 759, \"right\": 761, \"name_similarity\": 0.82, \"context_similarity\": 0.5154}, {\"left\": 759, \"right\": 770, \"name_similarity\": 0.8333, \"context_similarity\": 0.4936}, {\"left\": 759, \"right\": 808, \"name_similarity\": 0.5, \"context_similarity\": 0.2942}, {\"left\": 759, \"right\": 809, \"name_similarity\": 0.0, \"context_similarity\": 0.2053}, {\"left\": 759, \"right\": 929, \"name_similarity\": 0.4211, \"context_similarity\": 0.2813}, {\"left\": 759, \"right\": 930, \"name_similarity\": 0.6667, \"context_similarity\": 0.3567}, {\"left\": 760, \"right\": 761, \"name_similarity\": 0.82, \"context_similarity\": 0.4788}, {\"left\": 760, \"right\": 770, \"name_similarity\": 0.82, \"context_similarity\": 0.4931}, {\"left\": 760, \"right\": 808, \"name_similarity\": 0.2963, \"context_similarity\": 0.2295}, {\"left\": 760, \"right\": 809, \"name_similarity\": 0.0, \"context_similarity\": 0.1761}, {\"left\": 760, \"right\": 929, \"name_similarity\": 0.2667, \"context_similarity\": 0.2244}, {\"left\": 760, \"right\": 930, \"name_similarity\": 0.3478, \"context_similarity\": 0.2463}, {\"left\": 761, \"right\": 770, \"name_similarity\": 0.82, \"context_similarity\": 0.4521}, {\"left\": 761, \"right\": 808, \"name_similarity\": 0.82, \"context_similarity\": 0.4252}, {\"left\": 761, \"right\": 809, \"name_similarity\": 0.0, \"context_similarity\": 0.2851}, {\"left\": 761, \"right\": 929, \"name_similarity\": 0.82, \"context_similarity\": 0.4138}, {\"left\": 761, \"right\": 930, \"name_similarity\": 0.82, \"context_similarity\": 0.4101}, {\"left\": 770, \"right\": 808, \"name_similarity\": 0.5, \"context_similarity\": 0.2827}, {\"left\": 770, \"right\": 809, \"name_similarity\": 0.0, \"context_similarity\": 0.1858}]}, \"parent_summary\": {\"candidate_count\": 11, \"candidate_product_ids\": [1072, 930, 929, 812, 810, 809, 808, 770, 761, 760, 759], \"family_signatures\": [\"90세까지가입가능한유병자\", \"간편새로고침\", \"건보간편\", \"고고새로고침\", \"당뇨병없는만성질환자에합리적\", \"새로고침유병자\", \"암심장질환치료비특약\"]}}",
          "status": "review"
        },
        {
          "block_id": 632,
          "block_key": "company:30|partner:unknown|type:OTHER,PROPERTY_EXPENSE|month:2025-09|ids:1172,1173,1250,1296,1557|component:1",
          "company_id": 30,
          "partner_company_name": null,
          "release_month_window": "2025-09~2025-11",
          "product_type_codes": [
            "OTHER",
            "PROPERTY_EXPENSE"
          ],
          "candidate_product_ids": [
            1172,
            1173,
            1250,
            1296,
            1557,
            1558,
            1568
          ],
          "observation_ids": [
            5697,
            5699,
            6037,
            6039,
            6340,
            6574,
            7476,
            7739,
            7741,
            7788,
            8115
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:30|partner:unknown|type:OTHER,PROPERTY_EXPENSE|month:2025-09|ids:1172,1173,1250,1296,1557\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 7, \"candidate_names\": [\"민간에서도 지수형보험\", \"전통시장 날씨보험\", \"지수형 날씨보험\", \"폭우로 전통시장 문 닫아도보험\", \"지수형보험\", \"날씨보험\", \"기후 지수형보험\"], \"candidate_product_ids\": [1172, 1173, 1250, 1296, 1557, 1558, 1568], \"shared_high_info_tokens\": [\"kb손해\"], \"family_signatures\": [\"기후지수\", \"민간에서도지수\", \"전통시장\", \"전통시장닫아도폭우로\"], \"family_tokens\": [\"기후\", \"기후지수\", \"날씨\", \"닫아도\", \"민간에서도\", \"민간에서도지수\", \"전통시장\", \"지수\", \"폭우로\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1172, \"right\": 1173, \"name_similarity\": 0.2222, \"context_similarity\": 0.2751}, {\"left\": 1172, \"right\": 1250, \"name_similarity\": 0.5882, \"context_similarity\": 0.3204}, {\"left\": 1172, \"right\": 1296, \"name_similarity\": 0.2609, \"context_similarity\": 0.2221}, {\"left\": 1172, \"right\": 1557, \"name_similarity\": 0.82, \"context_similarity\": 0.3867}, {\"left\": 1172, \"right\": 1558, \"name_similarity\": 0.2857, \"context_similarity\": 0.2298}, {\"left\": 1172, \"right\": 1568, \"name_similarity\": 0.5882, \"context_similarity\": 0.3204}, {\"left\": 1173, \"right\": 1250, \"name_similarity\": 0.5333, \"context_similarity\": 0.3438}, {\"left\": 1173, \"right\": 1296, \"name_similarity\": 0.5714, \"context_similarity\": 0.3138}, {\"left\": 1173, \"right\": 1557, \"name_similarity\": 0.3077, \"context_similarity\": 0.3669}, {\"left\": 1173, \"right\": 1558, \"name_similarity\": 0.82, \"context_similarity\": 0.3777}, {\"left\": 1173, \"right\": 1568, \"name_similarity\": 0.2667, \"context_similarity\": 0.2815}, {\"left\": 1250, \"right\": 1296, \"name_similarity\": 0.2, \"context_similarity\": 0.2178}, {\"left\": 1250, \"right\": 1557, \"name_similarity\": 0.8333, \"context_similarity\": 0.4171}, {\"left\": 1250, \"right\": 1558, \"name_similarity\": 0.82, \"context_similarity\": 0.3868}, {\"left\": 1250, \"right\": 1568, \"name_similarity\": 0.7143, \"context_similarity\": 0.3886}, {\"left\": 1296, \"right\": 1557, \"name_similarity\": 0.2222, \"context_similarity\": 0.2379}, {\"left\": 1296, \"right\": 1558, \"name_similarity\": 0.2353, \"context_similarity\": 0.2175}, {\"left\": 1296, \"right\": 1568, \"name_similarity\": 0.2, \"context_similarity\": 0.2148}, {\"left\": 1557, \"right\": 1558, \"name_similarity\": 0.4444, \"context_similarity\": 0.2969}, {\"left\": 1557, \"right\": 1568, \"name_similarity\": 0.82, \"context_similarity\": 0.3819}]}, \"parent_summary\": {\"candidate_count\": 7, \"candidate_product_ids\": [1568, 1558, 1557, 1296, 1250, 1173, 1172], \"family_signatures\": [\"기후지수\", \"민간에서도지수\", \"전통시장\", \"전통시장닫아도폭우로\"]}}",
          "status": "review"
        },
        {
          "block_id": 633,
          "block_key": "company:31|partner:설채현 수의사, 이기우 배우|type:PET|month:2025-04|ids:45,697,728,841,843|component:1",
          "company_id": 31,
          "partner_company_name": "설채현 수의사, 이기우 배우",
          "release_month_window": "2025-04~2025-10",
          "product_type_codes": [
            "PET"
          ],
          "candidate_product_ids": [
            45,
            697,
            728,
            841,
            843,
            848,
            935
          ],
          "observation_ids": [
            281,
            433,
            437,
            439,
            444,
            3836,
            4148,
            4152,
            4160,
            4164,
            4191,
            4205,
            4230,
            4283,
            4717,
            4741,
            4745,
            4749,
            4751,
            4753,
            4755,
            4757,
            4759,
            4761,
            4765,
            5111,
            6523
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:31|partner:설채현 수의사, 이기우 배우|type:PET|month:2025-01|ids:45,46,697,728,841\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 7, \"candidate_names\": [\"세이브펫 SavePet 플랜 다이렉트 반려견보험\", \"설채현 이기우와 기부 펫보험\", \"펫블리 반려견보험\", \"119 은퇴견 후원 펫보험\", \"설채현 이기우의 세이브펫플랜 다이렉트 펫블리 반려견보험\", \"은퇴견 후원 펫보험\", \"설채현 이기우의 세이브펫플랜펫보험\"], \"candidate_product_ids\": [45, 697, 728, 841, 843, 848, 935], \"shared_high_info_tokens\": [\"db손해\", \"pet\"], \"family_signatures\": [\"반려견설채현이기우의펫\", \"반려견펫\", \"설채현이기우와펫\", \"설채현이기우의펫\", \"은퇴견펫\"], \"family_tokens\": [\"savepet\", \"반려견\", \"설채현\", \"은퇴견\", \"이기우와\", \"이기우의\", \"펫\", \"후원하는\"], \"partner_candidates\": [\"설채현 수의사, 이기우 배우\"], \"context_scores\": [{\"left\": 45, \"right\": 697, \"name_similarity\": 0.2353, \"context_similarity\": 0.2201}, {\"left\": 45, \"right\": 728, \"name_similarity\": 0.4, \"context_similarity\": 0.2061}, {\"left\": 45, \"right\": 841, \"name_similarity\": 0.1818, \"context_similarity\": 0.2164}, {\"left\": 45, \"right\": 843, \"name_similarity\": 0.6383, \"context_similarity\": 0.3473}, {\"left\": 45, \"right\": 848, \"name_similarity\": 0.2, \"context_similarity\": 0.2366}, {\"left\": 45, \"right\": 935, \"name_similarity\": 0.4211, \"context_similarity\": 0.268}, {\"left\": 697, \"right\": 728, \"name_similarity\": 0.3, \"context_similarity\": 0.234}, {\"left\": 697, \"right\": 841, \"name_similarity\": 0.2609, \"context_similarity\": 0.2716}, {\"left\": 697, \"right\": 843, \"name_similarity\": 0.4865, \"context_similarity\": 0.3315}, {\"left\": 697, \"right\": 848, \"name_similarity\": 0.3, \"context_similarity\": 0.2781}, {\"left\": 697, \"right\": 935, \"name_similarity\": 0.6429, \"context_similarity\": 0.4801}, {\"left\": 728, \"right\": 841, \"name_similarity\": 0.3158, \"context_similarity\": 0.2337}, {\"left\": 728, \"right\": 843, \"name_similarity\": 0.82, \"context_similarity\": 0.378}, {\"left\": 728, \"right\": 848, \"name_similarity\": 0.375, \"context_similarity\": 0.2558}, {\"left\": 728, \"right\": 935, \"name_similarity\": 0.25, \"context_similarity\": 0.2296}, {\"left\": 841, \"right\": 843, \"name_similarity\": 0.1667, \"context_similarity\": 0.2578}, {\"left\": 841, \"right\": 848, \"name_similarity\": 0.82, \"context_similarity\": 0.4923}, {\"left\": 841, \"right\": 935, \"name_similarity\": 0.2222, \"context_similarity\": 0.2322}, {\"left\": 843, \"right\": 848, \"name_similarity\": 0.1818, \"context_similarity\": 0.3413}, {\"left\": 843, \"right\": 935, \"name_similarity\": 0.7805, \"context_similarity\": 0.3962}]}, \"parent_summary\": {\"candidate_count\": 14, \"candidate_product_ids\": [2205, 1868, 1597, 1289, 1282, 935, 848, 843, 842, 841, 728, 697, 46, 45], \"family_signatures\": [\"2개항목펫\", \"가입만기부하는펫\", \"국가봉사동물은퇴견입양펫\", \"반려견설채현이기우의펫\", \"반려견펫\", \"사회공헌펫\", \"설채현이기우와펫\", \"설채현이기우의펫\", \"은퇴견펫\"]}}",
          "status": "review"
        },
        {
          "block_id": 634,
          "block_key": "company:23|partner:카카오페이|type:PET|month:2025-01|ids:1705,1706,1710,1713,1719|component:1",
          "company_id": 23,
          "partner_company_name": "카카오페이",
          "release_month_window": "2025-01~2025-01",
          "product_type_codes": [
            "PET"
          ],
          "candidate_product_ids": [
            1705,
            1706,
            1710,
            1713,
            1719
          ],
          "observation_ids": [
            2260,
            4707,
            4715,
            4735,
            4780,
            8402,
            8406,
            8408,
            8410,
            8412,
            8414,
            8416,
            8420,
            8422,
            8424,
            8426,
            8428,
            8442,
            8443,
            8444,
            8890
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:23|partner:카카오페이|type:PET|month:2025-01|ids:1705,1706,1710,1713,1714\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 5, \"candidate_names\": [\"유병력 간편심사 펫보험\", \"유병력 보장 펫보험\", \"업계 최초 유병력 보장 간편심사 펫보험\", \"업계 첫 유병력 보장 간편심사 펫보험\", \"치료 이력 있어도 가입하는 간편심사 펫보험\"], \"candidate_product_ids\": [1705, 1706, 1710, 1713, 1719], \"shared_high_info_tokens\": [\"pet\", \"기존에는\", \"메리츠화재\", \"유병력\", \"이력이\", \"이번\", \"있는\", \"치료\"], \"family_signatures\": [\"가입하는간편심사있어도펫\", \"간편심사유병력펫\", \"업계첫유병력펫\", \"업계최초유병력펫\", \"유병력펫\"], \"family_tokens\": [\"가입하는\", \"간편심사\", \"업계첫유병력\", \"업계최초유병력\", \"유병력\", \"있어도\", \"펫\"], \"partner_candidates\": [\"카카오페이\"], \"context_scores\": [{\"left\": 1705, \"right\": 1706, \"name_similarity\": 0.6667, \"context_similarity\": 0.3714}, {\"left\": 1705, \"right\": 1710, \"name_similarity\": 0.7692, \"context_similarity\": 0.4255}, {\"left\": 1705, \"right\": 1713, \"name_similarity\": 0.8, \"context_similarity\": 0.4382}, {\"left\": 1705, \"right\": 1719, \"name_similarity\": 0.5714, \"context_similarity\": 0.3233}, {\"left\": 1706, \"right\": 1710, \"name_similarity\": 0.6667, \"context_similarity\": 0.5267}, {\"left\": 1706, \"right\": 1713, \"name_similarity\": 0.6957, \"context_similarity\": 0.5323}, {\"left\": 1706, \"right\": 1719, \"name_similarity\": 0.3077, \"context_similarity\": 0.2919}, {\"left\": 1710, \"right\": 1713, \"name_similarity\": 0.9032, \"context_similarity\": 0.7889}, {\"left\": 1710, \"right\": 1719, \"name_similarity\": 0.4706, \"context_similarity\": 0.3179}, {\"left\": 1713, \"right\": 1719, \"name_similarity\": 0.4848, \"context_similarity\": 0.3179}]}, \"parent_summary\": {\"candidate_count\": 6, \"candidate_product_ids\": [1719, 1714, 1713, 1710, 1706, 1705], \"family_signatures\": [\"가입하는간편심사있어도펫\", \"간편심사유병력펫\", \"업계첫유병력펫\", \"업계최초유병력펫\", \"유병력도펫\", \"유병력펫\"]}}",
          "status": "review"
        },
        {
          "block_id": 635,
          "block_key": "company:29|partner:unknown|type:HEALTH_COMPREHENSIVE,SIMPLIFIED_IMPAIRED|month:2025-01|ids:1752,1753,1754,1755,1756|component:1",
          "company_id": 29,
          "partner_company_name": null,
          "release_month_window": "2025-01~2025-01",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE",
            "SIMPLIFIED_IMPAIRED"
          ],
          "candidate_product_ids": [
            1752,
            1753,
            1754,
            1755,
            1756
          ],
          "observation_ids": [
            8567,
            8569,
            8571,
            8574,
            8578
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:29|partner:제4인터넷전문은행|type:HEALTH_COMPREHENSIVE,SIMPLIFIED_IMPAIRED|month:2025-01|ids:1081,1752,1753,1754,1755\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 5, \"candidate_names\": [\"건강한 유병자\", \"유병자 고객 맞춤형 상품\", \"유병자 고객보험료 낮춘 건강보험\", \"유병자 고객 맞춤형보험료\", \"건강한 유병자에 맞춤형 가격 건강보험\"], \"candidate_product_ids\": [1752, 1753, 1754, 1755, 1756], \"shared_high_info_tokens\": [\"exclusive\", \"period\", \"underwriting\", \"건강한\", \"분리해\", \"수술의\", \"유병자가\", \"이번\", \"입원과\", \"있지만\", \"질병\", \"치료\", \"현대해상\"], \"family_signatures\": [\"한유병자\", \"한유병자에맞춤\"], \"family_tokens\": [\"유병자\", \"유병자에\", \"한유병자\", \"한유병자에맞춤\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1752, \"right\": 1753, \"name_similarity\": 0.375, \"context_similarity\": 0.3818}, {\"left\": 1752, \"right\": 1754, \"name_similarity\": 0.3, \"context_similarity\": 0.4181}, {\"left\": 1752, \"right\": 1755, \"name_similarity\": 0.3529, \"context_similarity\": 0.3782}, {\"left\": 1752, \"right\": 1756, \"name_similarity\": 0.82, \"context_similarity\": 0.4978}, {\"left\": 1753, \"right\": 1754, \"name_similarity\": 0.4167, \"context_similarity\": 0.4865}, {\"left\": 1753, \"right\": 1755, \"name_similarity\": 0.7619, \"context_similarity\": 0.7112}, {\"left\": 1753, \"right\": 1756, \"name_similarity\": 0.4615, \"context_similarity\": 0.5368}, {\"left\": 1754, \"right\": 1755, \"name_similarity\": 0.64, \"context_similarity\": 0.5525}, {\"left\": 1754, \"right\": 1756, \"name_similarity\": 0.4667, \"context_similarity\": 0.5133}, {\"left\": 1755, \"right\": 1756, \"name_similarity\": 0.5926, \"context_similarity\": 0.6207}]}, \"parent_summary\": {\"candidate_count\": 7, \"candidate_product_ids\": [1758, 1756, 1755, 1754, 1753, 1752, 1081], \"family_signatures\": [\"내삶엔3n맞춤간편\", \"내삶엔맞춤간편겅강\", \"한유병자\", \"한유병자에맞춤\"]}}",
          "status": "review"
        },
        {
          "block_id": 636,
          "block_key": "company:29|partner:LG|type:HEALTH_COMPREHENSIVE,OTHER|month:2025-08|ids:1075,1078,1079,1556|component:1",
          "company_id": 29,
          "partner_company_name": "LG",
          "release_month_window": "2025-08~2025-11",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE",
            "OTHER"
          ],
          "candidate_product_ids": [
            1075,
            1078,
            1079,
            1556
          ],
          "observation_ids": [
            5677,
            5681,
            5683,
            5687,
            5689,
            5693,
            7721,
            7723,
            7727,
            7729,
            7731,
            7733,
            7735,
            7737
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:29|partner:LG|type:HEALTH_COMPREHENSIVE,OTHER|month:2025-08|ids:1075,1078,1079,1080,1551\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 4, \"candidate_names\": [\"시니어 통합 패키지\", \"가전 구독 시니어 통합 패키지\", \"통신보험\", \"LG Easy TV 시니어 패키지\"], \"candidate_product_ids\": [1075, 1078, 1079, 1556], \"shared_high_info_tokens\": [\"exclusive\", \"feature\", \"kt\", \"kt는\", \"가전\", \"건강\", \"구독\", \"서비스를\", \"시니어\", \"이번\", \"통합\", \"패키지\", \"현대해상\"], \"family_signatures\": [\"lgeasytv시니어패키지\", \"가전시니어패키지\", \"시니어패키지\"], \"family_tokens\": [\"easy\", \"lg\", \"lgeasytv시니어패키지\", \"tv\", \"가전\", \"가전구독시니어통합패키지\", \"시니어\", \"시니어통합패키지\", \"통신\", \"패키지\"], \"partner_candidates\": [\"LG\"], \"context_scores\": [{\"left\": 1075, \"right\": 1078, \"name_similarity\": 0.82, \"context_similarity\": 0.5169}, {\"left\": 1075, \"right\": 1079, \"name_similarity\": 0.1667, \"context_similarity\": 0.3799}, {\"left\": 1075, \"right\": 1556, \"name_similarity\": 0.5455, \"context_similarity\": 0.3406}, {\"left\": 1078, \"right\": 1079, \"name_similarity\": 0.125, \"context_similarity\": 0.3847}, {\"left\": 1078, \"right\": 1556, \"name_similarity\": 0.4615, \"context_similarity\": 0.317}, {\"left\": 1079, \"right\": 1556, \"name_similarity\": 0.0, \"context_similarity\": 0.2087}]}, \"parent_summary\": {\"candidate_count\": 7, \"candidate_product_ids\": [1556, 1554, 1551, 1080, 1079, 1078, 1075], \"family_signatures\": [\"lgeasytv시니어패키지\", \"lg이지tv가전구독\", \"tv어르신패키지\", \"가전시니어패키지\", \"서비스시니어\", \"시니어패키지\"]}}",
          "status": "review"
        },
        {
          "block_id": 637,
          "block_key": "company:29|partner:국민카드|type:HEALTH_COMPREHENSIVE|month:2026-04|ids:234,243,273,370|component:1",
          "company_id": 29,
          "partner_company_name": "국민카드",
          "release_month_window": "2026-04~2026-04",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE"
          ],
          "candidate_product_ids": [
            234,
            243,
            273,
            370
          ],
          "observation_ids": [
            1188,
            1201,
            1241,
            1243,
            1253,
            1255,
            1410,
            1412,
            1417,
            1939,
            2371,
            2532,
            2761,
            3124
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:29|partner:국민카드|type:HEALTH_COMPREHENSIVE|month:2026-04|ids:234,243,273,370\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 4, \"candidate_names\": [\"굿앤굿2040종합보험\", \"인생의품격종합보험\", \"2030 라이프스타일 반영 종합보험\", \"종합보험\"], \"candidate_product_ids\": [234, 243, 273, 370], \"shared_high_info_tokens\": [\"종합\", \"현대해상\", \"현대해상은\"], \"family_signatures\": [\"굿앤굿2040종합\", \"라이프스타일\", \"인생의품격\"], \"family_tokens\": [\"2030라이프스타일반영\", \"굿앤굿2040종합\", \"라이프스타일\", \"인생의품격\"], \"partner_candidates\": [\"국민카드\", \"하나은행\"], \"context_scores\": [{\"left\": 234, \"right\": 243, \"name_similarity\": 0.4, \"context_similarity\": 0.3058}, {\"left\": 234, \"right\": 273, \"name_similarity\": 0.5185, \"context_similarity\": 0.3015}, {\"left\": 234, \"right\": 370, \"name_similarity\": 0.82, \"context_similarity\": 0.362}, {\"left\": 243, \"right\": 273, \"name_similarity\": 0.32, \"context_similarity\": 0.2352}, {\"left\": 243, \"right\": 370, \"name_similarity\": 0.82, \"context_similarity\": 0.3605}, {\"left\": 273, \"right\": 370, \"name_similarity\": 0.82, \"context_similarity\": 0.3649}]}, \"parent_summary\": {\"candidate_count\": 4, \"candidate_product_ids\": [370, 273, 243, 234], \"family_signatures\": [\"굿앤굿2040종합\", \"라이프스타일\", \"인생의품격\"]}}",
          "status": "review"
        },
        {
          "block_id": 638,
          "block_key": "company:3|partner:unknown|type:CHILD_ADULT_CHILD|month:2025-06|ids:1367,1368,1369,1370|component:1",
          "company_id": 3,
          "partner_company_name": null,
          "release_month_window": "2025-06~2025-06",
          "product_type_codes": [
            "CHILD_ADULT_CHILD"
          ],
          "candidate_product_ids": [
            1367,
            1368,
            1369,
            1370
          ],
          "observation_ids": [
            4651,
            6786,
            6798,
            6800,
            6804,
            6806,
            6808
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:3|partner:unknown|type:CHILD_ADULT_CHILD|month:2025-06|ids:1363,1364,1365,1367,1368\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 4, \"candidate_names\": [\"재해부터 암까지 보장하는 새 어린이보험\", \"새 어린이보험\", \"재해부터 암까지 필요한 보장만 선택하는 새 어린이보험\", \"재해사고 암 선택 보장형 어린이보험\"], \"candidate_product_ids\": [1367, 1368, 1369, 1370], \"shared_high_info_tokens\": [\"abl생명\", \"암까지\", \"어린이\"], \"family_signatures\": [\"새어린이\", \"암선택하는어린이재해부터필요한\", \"암어린이재해사고\", \"암하는새어린이\"], \"family_tokens\": [\"만선택하는새어린이\", \"새어린이\", \"선택하는\", \"암\", \"어린이\", \"재해부터\", \"재해사고\", \"필요한\", \"하는새어린이\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1367, \"right\": 1368, \"name_similarity\": 0.82, \"context_similarity\": 0.5988}, {\"left\": 1367, \"right\": 1369, \"name_similarity\": 0.85, \"context_similarity\": 0.4025}, {\"left\": 1367, \"right\": 1370, \"name_similarity\": 0.625, \"context_similarity\": 0.4257}, {\"left\": 1368, \"right\": 1369, \"name_similarity\": 0.82, \"context_similarity\": 0.3734}, {\"left\": 1368, \"right\": 1370, \"name_similarity\": 0.4762, \"context_similarity\": 0.447}, {\"left\": 1369, \"right\": 1370, \"name_similarity\": 0.5263, \"context_similarity\": 0.3036}]}, \"parent_summary\": {\"candidate_count\": 7, \"candidate_product_ids\": [1370, 1369, 1368, 1367, 1365, 1364, 1363], \"family_signatures\": [\"새어린이\", \"암선택하는어린이재해부터필요한\", \"암어린이재해사고\", \"암하는새어린이\", \"우리아이\", \"우리아이the보장\", \"우리아이더\"]}}",
          "status": "review"
        },
        {
          "block_id": 639,
          "block_key": "company:23|partner:unknown|type:TRAVEL_LEISURE|month:2025-04|ids:745,2063,2189|component:1",
          "company_id": 23,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-06",
          "product_type_codes": [
            "TRAVEL_LEISURE"
          ],
          "candidate_product_ids": [
            745,
            2063,
            2189
          ],
          "observation_ids": [
            4327,
            9806,
            10271
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:23|partner:unknown|type:TRAVEL_LEISURE|month:2025-04|ids:744,745,2063,2189\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"여행 취소보험\", \"해외여행보험\", \"여행보험\"], \"candidate_product_ids\": [745, 2063, 2189], \"shared_high_info_tokens\": [\"leisure\", \"travel\", \"메리츠화재\"], \"family_signatures\": [\"여행취소\", \"해외여행\"], \"family_tokens\": [\"여행\", \"여행취소\", \"해외여행\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 745, \"right\": 2063, \"name_similarity\": 0.6667, \"context_similarity\": 0.3329}, {\"left\": 745, \"right\": 2189, \"name_similarity\": 0.8, \"context_similarity\": 0.3749}, {\"left\": 2063, \"right\": 2189, \"name_similarity\": 0.82, \"context_similarity\": 0.4488}]}, \"parent_summary\": {\"candidate_count\": 4, \"candidate_product_ids\": [2189, 2063, 745, 744], \"family_signatures\": [\"여행취소\", \"와항공권취소\", \"해외여행\"]}}",
          "status": "review"
        },
        {
          "block_id": 640,
          "block_key": "company:25|partner:unknown|type:AUTO|month:2025-04|ids:916,2080,2082|component:1",
          "company_id": 25,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-04",
          "product_type_codes": [
            "AUTO"
          ],
          "candidate_product_ids": [
            916,
            2080,
            2082
          ],
          "observation_ids": [
            4996,
            5034,
            5046,
            5283,
            9846,
            9848,
            9850,
            9852,
            9854,
            9856,
            9858,
            9862,
            9864,
            9866,
            9868,
            9870,
            9873
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:25|partner:unknown|type:AUTO|month:2025-04|ids:916,2080,2082\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"자동차 다이렉트보험\", \"앨리스 플랫폼에 자동차 다이렉트보험\", \"let:click 자동차보험 앨리스 자동차보험\"], \"candidate_product_ids\": [916, 2080, 2082], \"shared_high_info_tokens\": [\"9일\", \"auto\", \"channel\", \"기존\", \"단기\", \"데이터를\", \"롯데손해\", \"먼저\", \"바탕으로\", \"밝혔다\", \"새로\", \"선보인\", \"소액\", \"앨리스\", \"앨리스가\", \"이다\", \"자동차\", \"제안하는\", \"최적의\", \"탑재\", \"플랜을\", \"했다고\"], \"family_signatures\": [\"letclick자동차앨리스자동차\", \"렛클릭배달플랫폼자동차\", \"앨리스플랫폼에자동차\"], \"family_tokens\": [\"click\", \"let\", \"letclick자동차\", \"렛클릭\", \"배달플랫폼\", \"앨리스\", \"앨리스자동차\", \"앨리스플랫폼에자동차\", \"자동차\", \"플랫폼에\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 916, \"right\": 2080, \"name_similarity\": 0.82, \"context_similarity\": 0.4192}, {\"left\": 916, \"right\": 2082, \"name_similarity\": 0.3333, \"context_similarity\": 0.3544}, {\"left\": 2080, \"right\": 2082, \"name_similarity\": 0.4324, \"context_similarity\": 0.3703}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [2082, 2080, 916], \"family_signatures\": [\"letclick자동차앨리스자동차\", \"렛클릭배달플랫폼자동차\", \"앨리스플랫폼에자동차\"]}}",
          "status": "review"
        },
        {
          "block_id": 641,
          "block_key": "company:25|partner:unknown|type:AUTO|month:2025-07|ids:914,919,920|component:1",
          "company_id": 25,
          "partner_company_name": null,
          "release_month_window": "2025-07~2025-07",
          "product_type_codes": [
            "AUTO"
          ],
          "candidate_product_ids": [
            914,
            919,
            920
          ],
          "observation_ids": [
            5036,
            5048,
            5052,
            5054,
            5058,
            5060
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:25|partner:unknown|type:AUTO|month:2025-07|ids:914,919,920,922\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"이륜차 시간제보험\", \"고보장 시간제 이륜차보험\", \"이륜차 대물 최대 1억원 보장하는 시간제보험\"], \"candidate_product_ids\": [914, 919, 920], \"shared_high_info_tokens\": [\"11t09\", \"11일\", \"auto\", \"경험을\", \"고보장\", \"다년간\", \"롯데\", \"롯데손해\", \"바탕으로\", \"반복되는\", \"밝혔다\", \"배달파트너\", \"분석해\", \"사각지대를\", \"사고\", \"손보\", \"시간제\", \"운영\", \"유형과\", \"이륜차\", \"했다고\"], \"family_signatures\": [\"시간제이륜차\", \"이륜차대물최대1억원하는시간제\", \"이륜차시간제\"], \"family_tokens\": [\"1억원\", \"시간제\", \"시간제이륜차\", \"이륜차\", \"이륜차대물최대1억원\", \"이륜차시간제\", \"하는시간제\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 914, \"right\": 919, \"name_similarity\": 0.6667, \"context_similarity\": 0.3956}, {\"left\": 914, \"right\": 920, \"name_similarity\": 0.5926, \"context_similarity\": 0.375}, {\"left\": 919, \"right\": 920, \"name_similarity\": 0.4667, \"context_similarity\": 0.5384}]}, \"parent_summary\": {\"candidate_count\": 4, \"candidate_product_ids\": [922, 920, 919, 914], \"family_signatures\": [\"시간제배달\", \"시간제이륜차\", \"이륜차대물최대1억원하는시간제\", \"이륜차시간제\"]}}",
          "status": "review"
        },
        {
          "block_id": 642,
          "block_key": "company:28|partner:unknown|type:AUTO|month:2026-05|ids:512,514,661|component:1",
          "company_id": 28,
          "partner_company_name": null,
          "release_month_window": "2026-05~2026-05",
          "product_type_codes": [
            "AUTO"
          ],
          "candidate_product_ids": [
            512,
            514,
            661
          ],
          "observation_ids": [
            2599,
            2601,
            2603,
            2605,
            2608,
            2878,
            3426,
            3428,
            3432,
            3436,
            3438,
            3440,
            3650
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:unknown|type:AUTO|month:2026-05|ids:512,514,661\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"차량 5부제 할인\", \"5월 말 車 5부제 할인특약\", \"차량 5부제 참여 차량보험 료 할인 특약\"], \"candidate_product_ids\": [512, 514, 661], \"shared_high_info_tokens\": [\"5부제\", \"auto\", \"marketing\", \"삼성화재\", \"차량\", \"할인\"], \"family_signatures\": [\"5부제할인특약\", \"차량5부제참여차량할인특약\", \"차량5부제할인\"], \"family_tokens\": [\"5부제\", \"5월말5부제할인특약\", \"차량\", \"차량5부제참여차량\", \"차량5부제할인\", \"할인특약\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 512, \"right\": 514, \"name_similarity\": 0.5882, \"context_similarity\": 0.3522}, {\"left\": 512, \"right\": 661, \"name_similarity\": 0.6087, \"context_similarity\": 0.3393}, {\"left\": 514, \"right\": 661, \"name_similarity\": 0.5385, \"context_similarity\": 0.3134}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [661, 514, 512], \"family_signatures\": [\"5부제할인특약\", \"차량5부제참여차량할인특약\", \"차량5부제할인\"]}}",
          "status": "review"
        },
        {
          "block_id": 643,
          "block_key": "company:31|partner:unknown|type:OTHER|month:2025-12|ids:1637,1638,1640|component:1",
          "company_id": 31,
          "partner_company_name": null,
          "release_month_window": "2025-12~2025-12",
          "product_type_codes": [
            "OTHER"
          ],
          "candidate_product_ids": [
            1637,
            1638,
            1640
          ],
          "observation_ids": [
            8119,
            8121,
            8125
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:31|partner:unknown|type:OTHER|month:2025-12|ids:1637,1638,1640\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"AI 통역 서비스\", \"다국어 통역 AI 에이전트 서비스\", \"다국어 통역 AI 해피콜 서비스\"], \"candidate_product_ids\": [1637, 1638, 1640], \"shared_high_info_tokens\": [\"ai\", \"db\", \"db손해\", \"exclusive\", \"feature\", \"other\", \"금융권\", \"다국어\", \"모니터링\", \"서비스를\", \"손보\", \"에이전트\", \"완전판매\", \"외국인\", \"통역\"], \"family_signatures\": [\"ai통역서비스\", \"다국어통역ai에이전트서비스\", \"다국어통역ai해피콜서비스\"], \"family_tokens\": [\"ai\", \"ai통역서비스\", \"다국어\", \"다국어통역ai에이전트서비스\", \"다국어통역ai해피콜서비스\", \"서비스\", \"에이전트\", \"해피콜\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1637, \"right\": 1638, \"name_similarity\": 0.5, \"context_similarity\": 0.54}, {\"left\": 1637, \"right\": 1640, \"name_similarity\": 0.5, \"context_similarity\": 0.4972}, {\"left\": 1638, \"right\": 1640, \"name_similarity\": 0.7407, \"context_similarity\": 0.533}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [1640, 1638, 1637], \"family_signatures\": [\"ai통역서비스\", \"다국어통역ai에이전트서비스\", \"다국어통역ai해피콜서비스\"]}}",
          "status": "review"
        },
        {
          "block_id": 644,
          "block_key": "company:37|partner:unknown|type:TRAVEL_LEISURE|month:2025-04|ids:2109,2112,2114|component:1",
          "company_id": 37,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-04",
          "product_type_codes": [
            "TRAVEL_LEISURE"
          ],
          "candidate_product_ids": [
            2109,
            2112,
            2114
          ],
          "observation_ids": [
            9979,
            9983,
            9985,
            9989,
            9991,
            9995,
            9997
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:37|partner:unknown|type:TRAVEL_LEISURE|month:2025-04|ids:2109,2112,2114,2115\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"지수형보험\", \"출국 항공기 지연 결항 보상 지수형 특약\", \"출국 항공기 지연 결항 보상 특약\"], \"candidate_product_ids\": [2109, 2112, 2114], \"shared_high_info_tokens\": [\"10만원\", \"24일\", \"leisure\", \"travel\", \"결항\", \"공항에서\", \"국내\", \"밝혔다\", \"보상\", \"새롭게\", \"손보\", \"지수형\", \"지연\", \"최대\", \"출국\", \"출발하는\", \"캐롯\", \"캐롯손해\", \"특약\", \"특약은\", \"항공기\", \"해외여행\"], \"family_signatures\": [\"출국항공기\", \"출국항공기지연결항보상지수\", \"출국항공기지연결항보상특약\"], \"family_tokens\": [\"지수\", \"출국\", \"출국항공기지연결항보상지수\", \"출국항공기지연결항보상특약\", \"항공기\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 2109, \"right\": 2112, \"name_similarity\": 0.2857, \"context_similarity\": 0.3821}, {\"left\": 2109, \"right\": 2114, \"name_similarity\": 0.2222, \"context_similarity\": 0.3648}, {\"left\": 2112, \"right\": 2114, \"name_similarity\": 0.8966, \"context_similarity\": 0.6436}]}, \"parent_summary\": {\"candidate_count\": 4, \"candidate_product_ids\": [2115, 2114, 2112, 2109], \"family_signatures\": [\"출국항공기\", \"출국항공기지연결항보상지수\", \"출국항공기지연결항보상특약\", \"해외여행항공기지연시정액\"]}}",
          "status": "review"
        },
        {
          "block_id": 645,
          "block_key": "company:38|partner:카카오페이|type:ACCIDENT_DRIVER|month:2025-09|ids:146,1151,1253|component:1",
          "company_id": 38,
          "partner_company_name": "카카오페이",
          "release_month_window": "2025-09~2026-01",
          "product_type_codes": [
            "ACCIDENT_DRIVER"
          ],
          "candidate_product_ids": [
            146,
            1151,
            1253
          ],
          "observation_ids": [
            741,
            839,
            933,
            1288,
            1292,
            1296,
            1970,
            1985,
            2767,
            4636,
            5167,
            5934,
            6350,
            9177,
            9438,
            9440,
            9442,
            9548
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:38|partner:카카오페이|type:ACCIDENT_DRIVER|month:2025-09|ids:146,1151,1253\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"운전자보험\", \"보너스 저금통\", \"운전자보험 보너스 저금통 서비스\"], \"candidate_product_ids\": [146, 1151, 1253], \"shared_high_info_tokens\": [\"17일\", \"accident\", \"driver\", \"exclusive\", \"feature\", \"매월\", \"밝혔다\", \"보너스\", \"서비스를\", \"운전자\", \"있는\", \"저금통\", \"적립\", \"적립할\", \"카카오페이손해\", \"해도\"], \"family_signatures\": [\"보너스저금통\", \"보너스저금통서비스운전자\"], \"family_tokens\": [\"보너스\", \"보너스저금통\", \"보너스저금통서비스\", \"서비스\", \"운전자\", \"저금통\"], \"partner_candidates\": [\"카카오페이\"], \"context_scores\": [{\"left\": 146, \"right\": 1151, \"name_similarity\": 0.1818, \"context_similarity\": 0.2392}, {\"left\": 146, \"right\": 1253, \"name_similarity\": 0.82, \"context_similarity\": 0.402}, {\"left\": 1151, \"right\": 1253, \"name_similarity\": 0.82, \"context_similarity\": 0.6606}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [1253, 1151, 146], \"family_signatures\": [\"보너스저금통\", \"보너스저금통서비스운전자\"]}}",
          "status": "review"
        },
        {
          "block_id": 646,
          "block_key": "company:43|partner:처브그룹|type:OTHER|month:2025-06|ids:1417,1419,1421|component:1",
          "company_id": 43,
          "partner_company_name": "처브그룹",
          "release_month_window": "2025-06~2025-06",
          "product_type_codes": [
            "OTHER"
          ],
          "candidate_product_ids": [
            1417,
            1419,
            1421
          ],
          "observation_ids": [
            6992,
            6996,
            7000
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:43|partner:처브그룹|type:OTHER|month:2025-06|ids:1417,1419,1421\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"제약 바이오 헬스케어 산업 복합 리스크 보장보험\", \"바이오기업 특화보험\", \"제약 바이오 기업 특화보험\"], \"candidate_product_ids\": [1417, 1419, 1421], \"shared_high_info_tokens\": [\"other\", \"과학\", \"라이나\", \"라이나손해\", \"바이오\", \"생명\", \"손보\"], \"family_signatures\": [\"바이오기업특화\", \"제약바이오기업특화\", \"제약바이오헬스케어산업복합리스크\"], \"family_tokens\": [\"리스크\", \"바이오\", \"바이오기업\", \"바이오기업특화\", \"제약\", \"제약바이오기업특화\", \"제약바이오헬스케어산업복합리스크\", \"헬스케어\"], \"partner_candidates\": [\"처브그룹\"], \"context_scores\": [{\"left\": 1417, \"right\": 1419, \"name_similarity\": 0.4138, \"context_similarity\": 0.3259}, {\"left\": 1417, \"right\": 1421, \"name_similarity\": 0.5161, \"context_similarity\": 0.555}, {\"left\": 1419, \"right\": 1421, \"name_similarity\": 0.82, \"context_similarity\": 0.4138}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [1421, 1419, 1417], \"family_signatures\": [\"바이오기업특화\", \"제약바이오기업특화\", \"제약바이오헬스케어산업복합리스크\"]}}",
          "status": "review"
        },
        {
          "block_id": 647,
          "block_key": "company:9|partner:더블플러스|type:ANNUITY_SAVINGS|month:2025-06|ids:211,966,1393|component:1",
          "company_id": 9,
          "partner_company_name": "더블플러스",
          "release_month_window": "2025-06~2025-06",
          "product_type_codes": [
            "ANNUITY_SAVINGS"
          ],
          "candidate_product_ids": [
            211,
            966,
            1393
          ],
          "observation_ids": [
            1043,
            5217,
            6921,
            6931,
            6933
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:9|partner:im스마트|type:ANNUITY_SAVINGS|month:2025-06|ids:99,207,211,340,341\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 3, \"candidate_names\": [\"고객 연령별 니즈를 세분화한 맞춤형 연금보험 4종\", \"맞춤형 연금보험 4종\", \"맞춤형 연금보험\"], \"candidate_product_ids\": [211, 966, 1393], \"shared_high_info_tokens\": [\"4종\", \"4종을\", \"exclusive\", \"im라이프\", \"im라이프생명\", \"니즈를\", \"맞춤형\", \"새롭게\", \"세분화한\", \"연금\", \"연령별\"], \"family_signatures\": [\"연금4종\", \"연금4종연령별니즈를세분화한맞춤\", \"연금생애주기\"], \"family_tokens\": [\"4종\", \"니즈를\", \"생애주기\", \"세분화한\", \"연금\", \"연령별\", \"연령별니즈를세분화한맞춤\"], \"partner_candidates\": [\"더블플러스\"], \"context_scores\": [{\"left\": 211, \"right\": 966, \"name_similarity\": 0.82, \"context_similarity\": 0.455}, {\"left\": 211, \"right\": 1393, \"name_similarity\": 0.82, \"context_similarity\": 0.4277}, {\"left\": 966, \"right\": 1393, \"name_similarity\": 0.82, \"context_similarity\": 0.4176}]}, \"parent_summary\": {\"candidate_count\": 11, \"candidate_product_ids\": [1397, 1396, 1393, 966, 379, 342, 341, 340, 211, 207, 99], \"family_signatures\": [\"연금4종\", \"연금4종연령별니즈를세분화한맞춤\", \"연금im마스터pro변액\", \"연금im세이프pro\", \"연금im스마트pro변액\", \"연금im스타트pro\", \"연금im스타트마스터트래블pro\", \"연금im트래블pro변액\", \"연금더블플러스\", \"연금생애주기\"]}}",
          "status": "review"
        },
        {
          "block_id": 648,
          "block_key": "company:10|partner:unknown|type:ANNUITY_SAVINGS,VARIABLE_UL|month:2025-04|ids:867,1995|component:1",
          "company_id": 10,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-04",
          "product_type_codes": [
            "ANNUITY_SAVINGS",
            "VARIABLE_UL"
          ],
          "candidate_product_ids": [
            867,
            1995
          ],
          "observation_ids": [
            4916,
            4918,
            9586
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:10|partner:unknown|type:ANNUITY_SAVINGS,VARIABLE_UL|month:2025-04|ids:867,1995\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"미래를 부탁해, 미래를 응원해\", \"미래를 부탁해 변액 연금보험\"], \"candidate_product_ids\": [867, 1995], \"shared_high_info_tokens\": [\"1분기\", \"4월\", \"acquired\", \"exclusive\", \"가능한\", \"가입이\", \"따라\", \"맞춤형\", \"미래를\", \"미래에셋생명\", \"미래에셋생명은\", \"변액\", \"부탁해\", \"상품을\", \"연금\", \"연령에\", \"응원해\", \"자의\", \"지난\"], \"family_signatures\": [\"미래를부탁해응원해\", \"연금미래를부탁해\"], \"family_tokens\": [\"미래를\", \"미래를부탁해미래를응원해\", \"부탁해\", \"연금\", \"응원해\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 867, \"right\": 1995, \"name_similarity\": 0.5, \"context_similarity\": 0.4101}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1995, 867], \"family_signatures\": [\"미래를부탁해응원해\", \"연금미래를부탁해\"]}}",
          "status": "review"
        },
        {
          "block_id": 649,
          "block_key": "company:1|partner:unknown|type:DEATH_WHOLELIFE|month:2025-10|ids:339,1301|component:1",
          "company_id": 1,
          "partner_company_name": null,
          "release_month_window": "2025-10~2026-01",
          "product_type_codes": [
            "DEATH_WHOLELIFE"
          ],
          "candidate_product_ids": [
            339,
            1301
          ],
          "observation_ids": [
            607,
            1774,
            6559,
            6564,
            6578,
            6581,
            6591,
            6691,
            6693,
            7484,
            7489,
            7497,
            7500,
            7981
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:1|partner:unknown|type:DEATH_WHOLELIFE|month:2025-10|ids:339,1301\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"사망보험 금 유동화\", \"사망보험 금 유동화가 가능한 종신보험 상품\"], \"candidate_product_ids\": [339, 1301], \"shared_high_info_tokens\": [\"30t14\", \"30일\", \"가능한\", \"가입해\", \"고객센터를\", \"고객센터의\", \"금융위원장\", \"나섰다\", \"맞춰\", \"방문해\", \"보며\", \"사망\", \"시청\", \"유동화\", \"유동화가\", \"이날\", \"이억원\", \"일에\", \"점검\", \"종신\", \"직접\", \"한화생명\", \"현장직원을\"], \"family_signatures\": [\"금유동화\", \"금유동화가가능한종신\"], \"family_tokens\": [\"가능한\", \"금유동화\", \"금유동화가가능한종신\", \"연금\", \"유동화\", \"유동화가\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 339, \"right\": 1301, \"name_similarity\": 0.82, \"context_similarity\": 0.3776}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1301, 339], \"family_signatures\": [\"금유동화\", \"금유동화가가능한종신\"]}}",
          "status": "review"
        },
        {
          "block_id": 650,
          "block_key": "company:1|partner:unknown|type:OTHER|month:2025-09|ids:1178,1606|component:1",
          "company_id": 1,
          "partner_company_name": null,
          "release_month_window": "2025-09~2025-09",
          "product_type_codes": [
            "OTHER"
          ],
          "candidate_product_ids": [
            1178,
            1606
          ],
          "observation_ids": [
            369,
            605,
            6058,
            6061,
            6065,
            6067,
            8001,
            8003,
            8005
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:1|partner:unknown|type:OTHER|month:2025-09|ids:1178,1606\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"세대 아우르는 맞춤형 자산관리 위한보험 금청구권 신탁\", \"비대면보험 금청구권 신탁\"], \"candidate_product_ids\": [1178, 1606], \"shared_high_info_tokens\": [\"other\", \"금을\", \"금청구권\", \"금청구권신탁\", \"더해진다\", \"동안\", \"등으로\", \"또한\", \"맞춤형\", \"분할\", \"사망\", \"세대\", \"신탁\", \"예금\", \"운용돼\", \"이자도\", \"잔액은\", \"정기\", \"지급되는\", \"지급액에\", \"최종\", \"한화생명\"], \"family_signatures\": [\"금청구권신탁비대면\", \"금청구권신탁세대아우르는맞춤자산관리\"], \"family_tokens\": [\"금청구권\", \"금청구권신탁\", \"비대면\", \"세대\", \"세대아우르는맞춤\", \"아우르는\", \"자산관리\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1178, \"right\": 1606, \"name_similarity\": 0.5294, \"context_similarity\": 0.3221}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1606, 1178], \"family_signatures\": [\"금청구권신탁비대면\", \"금청구권신탁세대아우르는맞춤자산관리\"]}}",
          "status": "review"
        },
        {
          "block_id": 651,
          "block_key": "company:1|partner:열린뉴스통신|type:CANCER|month:2025-09|ids:1124,1128|component:1",
          "company_id": 1,
          "partner_company_name": "열린뉴스통신",
          "release_month_window": "2025-09~2025-09",
          "product_type_codes": [
            "CANCER"
          ],
          "candidate_product_ids": [
            1124,
            1128
          ],
          "observation_ids": [
            457,
            5841,
            5846,
            5857,
            5859,
            5861,
            5863,
            5865,
            5867,
            6107,
            7492
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:1|partner:열린뉴스통신|type:CANCER|month:2025-09|ids:1124,1128\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"니드 Need AI 암보험\", \"AI 기술 활용한 암보험\"], \"candidate_product_ids\": [1124, 1128], \"shared_high_info_tokens\": [\"02t10\", \"2일\", \"ai\", \"cancer\", \"exclusive\", \"걸쳐\", \"고객에게\", \"과정에\", \"글로벌\", \"기술\", \"기업\", \"니드와\", \"맞춤형\", \"인공지능\", \"제공하는\", \"진단\", \"치료\", \"케어\", \"한화생명\", \"한화생명은\", \"한화생명이\", \"헬스케어\", \"협력해\", \"활용한\"], \"family_signatures\": [\"암aineed\", \"암ai활용한\"], \"family_tokens\": [\"ai\", \"need\", \"암\", \"인공지능\", \"활용한\"], \"partner_candidates\": [\"열린뉴스통신\"], \"context_scores\": [{\"left\": 1124, \"right\": 1128, \"name_similarity\": 0.4762, \"context_similarity\": 0.2875}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1128, 1124], \"family_signatures\": [\"암aineed\", \"암ai활용한\"]}}",
          "status": "review"
        },
        {
          "block_id": 652,
          "block_key": "company:21|partner:unknown|type:ACCIDENT_DRIVER|month:2026-05|ids:530,606|component:1",
          "company_id": 21,
          "partner_company_name": null,
          "release_month_window": "2026-05~2026-05",
          "product_type_codes": [
            "ACCIDENT_DRIVER"
          ],
          "candidate_product_ids": [
            530,
            606
          ],
          "observation_ids": [
            2694,
            3097
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:21|partner:unknown|type:ACCIDENT_DRIVER|month:2026-05|ids:530,606\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"운동쏘옥 NHe부상케어보험\", \"운동쏘옥\"], \"candidate_product_ids\": [530, 606], \"shared_high_info_tokens\": [\"accident\", \"driver\", \"nh농협생명\", \"농협생명\", \"부상\", \"운동\", \"운동쏘옥\"], \"family_signatures\": [\"운동쏘옥\", \"운동쏘옥nhe부상케어\"], \"family_tokens\": [\"nhe부상케어\", \"운동쏘옥\", \"운동쏘옥nhe부상케어\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 530, \"right\": 606, \"name_similarity\": 0.82, \"context_similarity\": 0.4114}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [606, 530], \"family_signatures\": [\"운동쏘옥\", \"운동쏘옥nhe부상케어\"]}}",
          "status": "auto_merged"
        },
        {
          "block_id": 653,
          "block_key": "company:21|partner:unknown|type:DEMENTIA_CARE|month:2025-04|ids:2050,2051|component:1",
          "company_id": 21,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-04",
          "product_type_codes": [
            "DEMENTIA_CARE"
          ],
          "candidate_product_ids": [
            2050,
            2051
          ],
          "observation_ids": [
            5194,
            9679,
            9776,
            9778,
            9780,
            9788
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:21|partner:unknown|type:DEMENTIA_CARE|month:2025-04|ids:2050,2051\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"NH 간병보험\", \"요양을안심해 NH 간병보험\"], \"candidate_product_ids\": [2050, 2051], \"shared_high_info_tokens\": [\"1호\", \"care\", \"dementia\", \"nh\", \"nh농협생명\", \"quot\", \"간병\", \"농협\", \"농협생명\", \"먼저\", \"으로\", \"출시된\", \"행사\"], \"family_signatures\": [\"요양을안심해\"], \"family_tokens\": [\"간병\", \"동주공제\", \"요양을안심해\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 2050, \"right\": 2051, \"name_similarity\": 0.82, \"context_similarity\": 0.3647}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [2051, 2050], \"family_signatures\": [\"요양을안심해\"]}}",
          "status": "review"
        },
        {
          "block_id": 654,
          "block_key": "company:21|partner:unknown|type:MEDICAL_INDEMNITY|month:2025-06|ids:681,682|component:1",
          "company_id": 21,
          "partner_company_name": null,
          "release_month_window": "2025-06~2025-06",
          "product_type_codes": [
            "MEDICAL_INDEMNITY"
          ],
          "candidate_product_ids": [
            681,
            682
          ],
          "observation_ids": [
            3746,
            3748,
            3750,
            3752
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:21|partner:unknown|type:MEDICAL_INDEMNITY|month:2025-06|ids:681,682\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"개정 실손보험\", \"실손보험\"], \"candidate_product_ids\": [681, 682], \"shared_high_info_tokens\": [\"candidates\", \"indemnity\", \"medical\", \"naver\", \"nh농협생명\", \"quot\", \"source\", \"summary\", \"같이\", \"개정\", \"경남총국\", \"경남총국장은\", \"고객만족으로\", \"교육을\", \"권역별\", \"농축협\", \"상품을\", \"생명\", \"쉬운\", \"실손\", \"실손의료\", \"앞으로도\", \"이어지므로\", \"임직원\", \"임직원의\", \"전문성\", \"접근성이\", \"정대홍\", \"조합원과\", \"지속적인\"], \"family_signatures\": [\"개정실손\", \"실손의료\"], \"family_tokens\": [\"개정\", \"개정실손\", \"실손\", \"실손의료\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 681, \"right\": 682, \"name_similarity\": 0.82, \"context_similarity\": 0.587}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [682, 681], \"family_signatures\": [\"개정실손\", \"실손의료\"]}}",
          "status": "review"
        },
        {
          "block_id": 655,
          "block_key": "company:25|partner:unknown|type:OTHER|month:2025-07|ids:817,912|component:1",
          "company_id": 25,
          "partner_company_name": null,
          "release_month_window": "2025-07~2025-07",
          "product_type_codes": [
            "OTHER"
          ],
          "candidate_product_ids": [
            817,
            912
          ],
          "observation_ids": [
            4641,
            5032,
            5038,
            5040,
            5042
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:25|partner:unknown|type:OTHER|month:2025-07|ids:817,912\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"서핑보험\", \"let:safe 서핑보험\"], \"candidate_product_ids\": [817, 912], \"shared_high_info_tokens\": [\"1000원\", \"19세부터\", \"1천만원\", \"1회당\", \"21t13\", \"21t16\", \"21일\", \"59세까지\", \"acquired\", \"alice\", \"exclusive\", \"feature\", \"let\", \"other\", \"safe\", \"각종\", \"겨울\", \"계절별\", \"누구나\", \"대표\", \"레저\", \"롯데\", \"롯데손해\", \"만19세부터\", \"맞아\", \"미니\", \"밝혔다\", \"상품은\", \"상해\", \"생활밀착형\"], \"family_signatures\": [\"letsafe서핑\"], \"family_tokens\": [\"let\", \"letsafe서핑\", \"safe\", \"서핑\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 817, \"right\": 912, \"name_similarity\": 0.82, \"context_similarity\": 0.4819}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [912, 817], \"family_signatures\": [\"letsafe서핑\"]}}",
          "status": "review"
        },
        {
          "block_id": 656,
          "block_key": "company:25|partner:인터페이|type:OTHER|month:2025-08|ids:981,985|component:1",
          "company_id": 25,
          "partner_company_name": "인터페이",
          "release_month_window": "2025-08~2025-08",
          "product_type_codes": [
            "OTHER"
          ],
          "candidate_product_ids": [
            981,
            985
          ],
          "observation_ids": [
            5261,
            5271,
            5278
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:25|partner:인터페이|type:OTHER|month:2025-08|ids:981,985\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"장기 보장성보험\", \"나아가 장기 보장성보험\"], \"candidate_product_ids\": [981, 985], \"shared_high_info_tokens\": [\"04t10\", \"2주년\", \"36만건\", \"metric\", \"other\", \"sales\", \"구상이다\", \"누적\", \"다양한\", \"돌파\", \"롯데손보\", \"롯데손해\", \"리스크를\", \"보장성\", \"보장하는\", \"상품을\", \"앨리스\", \"일상의\", \"장기\", \"종합\", \"지속\", \"진화하겠다는\", \"폭넓게\", \"플랫폼으로\", \"혁신적인\"], \"family_signatures\": [\"나아가장기\"], \"family_tokens\": [\"나아가\", \"나아가장기\", \"장기\"], \"partner_candidates\": [\"인터페이\"], \"context_scores\": [{\"left\": 981, \"right\": 985, \"name_similarity\": 0.82, \"context_similarity\": 0.5213}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [985, 981], \"family_signatures\": [\"나아가장기\"]}}",
          "status": "review"
        },
        {
          "block_id": 657,
          "block_key": "company:27|partner:unknown|type:MEDICAL_INDEMNITY|month:2025-07|ids:924,926|component:1",
          "company_id": 27,
          "partner_company_name": null,
          "release_month_window": "2025-07~2025-07",
          "product_type_codes": [
            "MEDICAL_INDEMNITY"
          ],
          "candidate_product_ids": [
            924,
            926
          ],
          "observation_ids": [
            5071,
            5075
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:27|partner:unknown|type:MEDICAL_INDEMNITY|month:2025-07|ids:924,926\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"비급여 10억 리셋 월렛\", \"비급여 10억 통장 제3보험\"], \"candidate_product_ids\": [924, 926], \"shared_high_info_tokens\": [\"10억\", \"exclusive\", \"indemnity\", \"medical\", \"right\", \"tf를\", \"관계자는\", \"대해\", \"리셋\", \"배타적\", \"비급여\", \"사용권\", \"상품개발\", \"월렛\", \"흥국화재\"], \"family_signatures\": [\"비급여10억리셋월렛\", \"비급여10억통장제3\"], \"family_tokens\": [\"10억\", \"비급여\", \"비급여10억리셋월렛\", \"비급여10억통장제3\", \"제3\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 924, \"right\": 926, \"name_similarity\": 0.5455, \"context_similarity\": 0.4053}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [926, 924], \"family_signatures\": [\"비급여10억리셋월렛\", \"비급여10억통장제3\"]}}",
          "status": "review"
        },
        {
          "block_id": 658,
          "block_key": "company:28|partner:unknown|type:CANCER|month:2025-04|ids:1978,2089|component:1",
          "company_id": 28,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-04",
          "product_type_codes": [
            "CANCER"
          ],
          "candidate_product_ids": [
            1978,
            2089
          ],
          "observation_ids": [
            9477,
            9486,
            9488,
            9492,
            9497,
            9511,
            9513,
            9515,
            9517,
            9519,
            9521,
            9523,
            9525,
            9527,
            9529,
            9532,
            9534,
            9536,
            9538,
            9540,
            9542,
            9544,
            9546,
            9885,
            9887,
            9889,
            9894
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:unknown|type:CANCER|month:2025-04|ids:1978,2089\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"다시 일상으로 암보험\", \"암 치료 이후 삶 보장하는 암보험\"], \"candidate_product_ids\": [1978, 2089], \"shared_high_info_tokens\": [\"03t15\", \"24개월\", \"500만원과\", \"cancer\", \"개발됐다\", \"다시\", \"따라\", \"맞춰\", \"발전으로\", \"삼성화재\", \"상품은\", \"생존율이\", \"생활지원금\", \"의학기술\", \"이후\", \"일상으로\", \"주는\", \"진단비\", \"최대\", \"치료\", \"함께\"], \"family_signatures\": [\"다시일상으로\", \"암일상으로\"], \"family_tokens\": [\"다시\", \"다시일상으로\", \"생활지원금\", \"암\", \"일상으로\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1978, \"right\": 2089, \"name_similarity\": 0.2727, \"context_similarity\": 0.2502}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [2089, 1978], \"family_signatures\": [\"다시일상으로\", \"암일상으로\"]}}",
          "status": "review"
        },
        {
          "block_id": 659,
          "block_key": "company:28|partner:unknown|type:HEALTH_COMPREHENSIVE,SPECIFIC_DISEASE|month:2025-09|ids:1106,1583|component:1",
          "company_id": 28,
          "partner_company_name": null,
          "release_month_window": "2025-09~2025-12",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE",
            "SPECIFIC_DISEASE"
          ],
          "candidate_product_ids": [
            1106,
            1583
          ],
          "observation_ids": [
            5778,
            7863
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:unknown|type:HEALTH_COMPREHENSIVE,SPECIFIC_DISEASE|month:2025-09|ids:1106,1583\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"장기보험\", \"초미니 장기보험\"], \"candidate_product_ids\": [1106, 1583], \"shared_high_info_tokens\": [\"exclusive\", \"삼성화재\", \"장기\"], \"family_signatures\": [\"초미니장기\"], \"family_tokens\": [\"장기\", \"초미니\", \"초미니장기\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1106, \"right\": 1583, \"name_similarity\": 0.82, \"context_similarity\": 0.3704}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1583, 1106], \"family_signatures\": [\"초미니장기\"]}}",
          "status": "review"
        },
        {
          "block_id": 660,
          "block_key": "company:28|partner:unknown|type:TRAVEL_LEISURE|month:2025-01|ids:1881,1883|component:1",
          "company_id": 28,
          "partner_company_name": null,
          "release_month_window": "2025-01~2025-02",
          "product_type_codes": [
            "TRAVEL_LEISURE"
          ],
          "candidate_product_ids": [
            1881,
            1883
          ],
          "observation_ids": [
            9072,
            9076
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:네이버페이|type:TRAVEL_LEISURE|month:2024-02|ids:455,928,1856,1880,1881\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"첫 지수형보험\", \"국내 첫 지수형보험\"], \"candidate_product_ids\": [1881, 1883], \"shared_high_info_tokens\": [\"07t13\", \"2시간\", \"channel\", \"leisure\", \"travel\", \"결항\", \"국내\", \"국제선\", \"대한\", \"또는\", \"보상\", \"보험금을\", \"삼성화재\", \"이번\", \"이상\", \"지수형\", \"지연\", \"항공기\", \"해외여행\"], \"family_signatures\": [\"국내첫지수\"], \"family_tokens\": [\"국내\", \"국내첫지수\", \"지수\", \"첫지수\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1881, \"right\": 1883, \"name_similarity\": 0.82, \"context_similarity\": 0.4574}]}, \"parent_summary\": {\"candidate_count\": 7, \"candidate_product_ids\": [1883, 1882, 1881, 1880, 1856, 928, 455], \"family_signatures\": [\"국내첫지수\", \"지수항공기지연특약\", \"출국항공기지연결항보상지수\", \"출국항공기지연결항특약\", \"항공기지연결항보상지수\", \"항공기지연시간비례\"]}}",
          "status": "review"
        },
        {
          "block_id": 661,
          "block_key": "company:28|partner:삼성화재|type:OTHER,SERVICE|month:2025-09|ids:1230,1537|component:1",
          "company_id": 28,
          "partner_company_name": "삼성화재",
          "release_month_window": "2025-09~2025-11",
          "product_type_codes": [
            "OTHER",
            "SERVICE"
          ],
          "candidate_product_ids": [
            1230,
            1537
          ],
          "observation_ids": [
            6272,
            7649
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:28|partner:삼성화재|type:OTHER,SERVICE|month:2025-09|ids:1230,1537,1538\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"외국인 근로자보험 조회 서비스\", \"외국인 맞춤 서비스\"], \"candidate_product_ids\": [1230, 1537], \"shared_high_info_tokens\": [\"exclusive\", \"feature\", \"삼성화재\", \"서비스는\", \"서비스를\", \"외국인\", \"이번\"], \"family_signatures\": [\"외국인근로자조회서비스\", \"외국인맞춤서비스\"], \"family_tokens\": [\"근로자\", \"서비스\", \"외국인\", \"외국인근로자\", \"외국인맞춤서비스\", \"조회서비스\"], \"partner_candidates\": [\"삼성화재\"], \"context_scores\": [{\"left\": 1230, \"right\": 1537, \"name_similarity\": 0.5714, \"context_similarity\": 0.3555}]}, \"parent_summary\": {\"candidate_count\": 3, \"candidate_product_ids\": [1538, 1537, 1230], \"family_signatures\": [\"서비스외국어청구\", \"외국인근로자조회서비스\", \"외국인맞춤서비스\"]}}",
          "status": "review"
        },
        {
          "block_id": 662,
          "block_key": "company:31|partner:unknown|type:DEMENTIA_CARE|month:2025-12|ids:403,1580|component:1",
          "company_id": 31,
          "partner_company_name": null,
          "release_month_window": "2025-12~2026-03",
          "product_type_codes": [
            "DEMENTIA_CARE"
          ],
          "candidate_product_ids": [
            403,
            1580
          ],
          "observation_ids": [
            2099,
            7843
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:31|partner:unknown|type:DEMENTIA_CARE|month:2025-12|ids:403,1580\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"간병보험\", \"참좋은더보장간병보험\"], \"candidate_product_ids\": [403, 1580], \"shared_high_info_tokens\": [\"care\", \"db손해\", \"dementia\", \"선점\", \"시장\", \"장기\"], \"family_signatures\": [\"참좋은더\"], \"family_tokens\": [\"간병\", \"참좋은더\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 403, \"right\": 1580, \"name_similarity\": 0.82, \"context_similarity\": 0.395}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1580, 403], \"family_signatures\": [\"참좋은더\"]}}",
          "status": "review"
        },
        {
          "block_id": 663,
          "block_key": "company:31|partner:카카오헬스케어|type:OTHER,SPECIFIC_DISEASE|month:2025-10|ids:1445,1447|component:1",
          "company_id": 31,
          "partner_company_name": "카카오헬스케어",
          "release_month_window": "2025-10~2025-10",
          "product_type_codes": [
            "OTHER",
            "SPECIFIC_DISEASE"
          ],
          "candidate_product_ids": [
            1445,
            1447
          ],
          "observation_ids": [
            7100,
            7104,
            7108,
            7110,
            7114
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:31|partner:카카오헬스케어|type:OTHER,SPECIFIC_DISEASE|month:2025-10|ids:1445,1447\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"만성질환 디지털 헬스케어 현물급부 서비스\", \"만성질환 관리 서비스\"], \"candidate_product_ids\": [1445, 1447], \"shared_high_info_tokens\": [\"17t09\", \"db\", \"db손해\", \"exclusive\", \"feature\", \"만성질환\", \"박성식\", \"부사장\", \"사진\", \"전략실\", \"카카오헬스케어\"], \"family_signatures\": [\"만성질환디지털헬스케어현물급부서비스\", \"만성질환서비스\"], \"family_tokens\": [\"디지털\", \"만성질환\", \"만성질환관리서비스\", \"만성질환디지털헬스케어현물급부서비스\", \"서비스\", \"헬스케어\", \"현물급부\"], \"partner_candidates\": [\"카카오헬스케어\"], \"context_scores\": [{\"left\": 1445, \"right\": 1447, \"name_similarity\": 0.5185, \"context_similarity\": 0.332}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1447, 1445], \"family_signatures\": [\"만성질환디지털헬스케어현물급부서비스\", \"만성질환서비스\"]}}",
          "status": "review"
        },
        {
          "block_id": 664,
          "block_key": "company:35|partner:sol트래블카드|type:TRAVEL_LEISURE|month:2025-08|ids:1089,1093|component:1",
          "company_id": 35,
          "partner_company_name": "sol트래블카드",
          "release_month_window": "2025-08~2025-08",
          "product_type_codes": [
            "TRAVEL_LEISURE"
          ],
          "candidate_product_ids": [
            1089,
            1093
          ],
          "observation_ids": [
            5724,
            5732
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:35|partner:sol트래블카드|type:TRAVEL_LEISURE|month:2025-08|ids:1089,1093\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"해외여행보험\", \"처음해외여행보험\"], \"candidate_product_ids\": [1089, 1093], \"shared_high_info_tokens\": [\"4종\", \"leisure\", \"travel\", \"손보\", \"슈퍼sol\", \"신한\", \"신한ez\", \"신한ez손해\", \"처음크루\"], \"family_signatures\": [\"처음해외여행\", \"해외여행\"], \"family_tokens\": [\"처음해외여행\", \"해외여행\"], \"partner_candidates\": [\"sol트래블카드\"], \"context_scores\": [{\"left\": 1089, \"right\": 1093, \"name_similarity\": 0.82, \"context_similarity\": 0.4629}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1093, 1089], \"family_signatures\": [\"처음해외여행\", \"해외여행\"]}}",
          "status": "review"
        },
        {
          "block_id": 665,
          "block_key": "company:37|partner:unknown|type:PET|month:2025-01|ids:1774,1777|component:1",
          "company_id": 37,
          "partner_company_name": null,
          "release_month_window": "2025-01~2025-01",
          "product_type_codes": [
            "PET"
          ],
          "candidate_product_ids": [
            1774,
            1777
          ],
          "observation_ids": [
            8661,
            8663,
            8665,
            8667,
            8669,
            8671,
            8673,
            8675,
            8677
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:37|partner:unknown|type:PET|month:2025-01|ids:1774,1777\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"텔레파시 telepodsee\", \"반려견 건강관리 서비스\"], \"candidate_product_ids\": [1774, 1777], \"shared_high_info_tokens\": [\"23t09\", \"23일\", \"exclusive\", \"feature\", \"iot\", \"pet\", \"telepod\", \"telepodsee\", \"같이\", \"개발한\", \"건강관리\", \"것과\", \"관리\", \"국내\", \"기기\", \"기기를\", \"기반\", \"기반으로\", \"기반의\", \"기자\", \"김재용\", \"데이터\", \"데이터를\", \"디지털\", \"라이센스뉴스\", \"맞춤형\", \"반려견\", \"반려견의\", \"밝혔다\", \"사물인터넷\"], \"family_signatures\": [\"반려견서비스\", \"텔레파시telepodsee\"], \"family_tokens\": [\"telepodsee\", \"관리서비스\", \"반려견\", \"서비스\", \"텔레파시\", \"텔레파시telepodsee\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1774, \"right\": 1777, \"name_similarity\": 0.0, \"context_similarity\": 0.3031}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1777, 1774], \"family_signatures\": [\"반려견서비스\", \"텔레파시telepodsee\"]}}",
          "status": "review"
        },
        {
          "block_id": 666,
          "block_key": "company:38|partner:카카오페이|type:CHILD_ADULT_CHILD,SPECIFIC_DISEASE|month:2024-05|ids:169,830|component:2",
          "company_id": 38,
          "partner_company_name": "카카오페이",
          "release_month_window": "2024-05~2024-07",
          "product_type_codes": [
            "CHILD_ADULT_CHILD",
            "SPECIFIC_DISEASE"
          ],
          "candidate_product_ids": [
            169,
            830
          ],
          "observation_ids": [
            841,
            931,
            953,
            1987,
            2084,
            2091,
            2769,
            4638,
            4681,
            4683,
            4685,
            4687,
            4689,
            4691,
            4693,
            4695,
            5169,
            5171
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:38|partner:카카오페이|type:CHILD_ADULT_CHILD,HEALTH_COMPREHENSIVE,OTHER|month:2024-05|ids:44,169,186,187,206\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"영유아보험\", \"영유아보험 수족구 진단비\"], \"candidate_product_ids\": [169, 830], \"shared_high_info_tokens\": [\"15t09\", \"15t10\", \"15t11\", \"15t14\", \"15t17\", \"15일\", \"1년\", \"1억\", \"1억원\", \"24시간\", \"quot\", \"가능하다\", \"가능하며\", \"가입과\", \"가입자\", \"간편하게\", \"과도\", \"금이\", \"기존의\", \"누적\", \"대표\", \"돌려받은\", \"따르면\", \"만에\", \"보장이\", \"손보\", \"수족구\", \"실손\", \"어린이\", \"업계에\"], \"family_signatures\": [\"수족구진단비영유아\"], \"family_tokens\": [\"수족구\", \"수족구진단비\", \"영유아\", \"진단비\"], \"partner_candidates\": [\"카카오페이\"], \"context_scores\": [{\"left\": 169, \"right\": 830, \"name_similarity\": 0.82, \"context_similarity\": 0.5371}]}, \"parent_summary\": {\"candidate_count\": 25, \"candidate_product_ids\": [2216, 1980, 1979, 1588, 1587, 1360, 1359, 1358, 1174, 1111, 953, 830, 794, 793, 700, 684, 680, 669, 668, 385, 206, 187, 186, 169, 44], \"family_signatures\": [\"2024년영유아\", \"간편함담은\", \"모바일에최적화된\", \"생애주기\", \"수족구진단비영유아\", \"영유아초중학생\", \"장기일반\", \"초중학생\"]}}",
          "status": "auto_merged"
        },
        {
          "block_id": 667,
          "block_key": "company:38|partner:카카오페이|type:TRAVEL_LEISURE|month:2023-01|ids:497,1175|component:1",
          "company_id": 38,
          "partner_company_name": "카카오페이",
          "release_month_window": "2023-01~2023-06",
          "product_type_codes": [
            "TRAVEL_LEISURE"
          ],
          "candidate_product_ids": [
            497,
            1175
          ],
          "observation_ids": [
            2513,
            4833,
            4860,
            5357,
            5869,
            6051,
            6053,
            6055
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:38|partner:카카오페이|type:TRAVEL_LEISURE|month:2023-01|ids:145,497,857,1175,1262\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"여행자보험\", \"이중 2023년 6월 출시 한 해외 여행자보험\"], \"candidate_product_ids\": [497, 1175], \"shared_high_info_tokens\": [\"2023년\", \"6월\", \"acquired\", \"exclusive\", \"leisure\", \"travel\", \"경우\", \"업계\", \"여행자\", \"카카오페이손보\", \"카카오페이손해\", \"해외\"], \"family_signatures\": [\"2023년여행자이중\", \"해외여행자\"], \"family_tokens\": [\"2023년\", \"여행자\", \"이중\", \"이중2023년6월출시한해외여행자\", \"해외여행자\"], \"partner_candidates\": [\"카카오페이\"], \"context_scores\": [{\"left\": 497, \"right\": 1175, \"name_similarity\": 0.82, \"context_similarity\": 0.4069}]}, \"parent_summary\": {\"candidate_count\": 6, \"candidate_product_ids\": [1450, 1262, 1175, 857, 497, 145], \"family_signatures\": [\"2023년여행자이중\", \"실제로해외여행\", \"실제여행자\", \"일례로해외여행\", \"해외여행\", \"해외여행자\"]}}",
          "status": "review"
        },
        {
          "block_id": 668,
          "block_key": "company:3|partner:unknown|type:DENTAL|month:2025-10|ids:1278,1280|component:1",
          "company_id": 3,
          "partner_company_name": null,
          "release_month_window": "2025-10~2025-10",
          "product_type_codes": [
            "DENTAL"
          ],
          "candidate_product_ids": [
            1278,
            1280
          ],
          "observation_ids": [
            6488,
            6494
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:3|partner:unknown|type:DENTAL|month:2025-10|ids:1278,1280\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"무 우리WON하는 치아보험 갱신형\", \"치아보험\"], \"candidate_product_ids\": [1278, 1280], \"shared_high_info_tokens\": [\"5대\", \"abl생명\", \"dental\", \"개정\", \"보장하는\", \"상품은\", \"치아\"], \"family_signatures\": [\"우리won\"], \"family_tokens\": [\"won\", \"우리won\", \"치아\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1278, \"right\": 1280, \"name_similarity\": 0.82, \"context_similarity\": 0.419}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1280, 1278], \"family_signatures\": [\"우리won\"]}}",
          "status": "review"
        },
        {
          "block_id": 669,
          "block_key": "company:4|partner:unknown|type:CANCER,SIMPLIFIED_IMPAIRED|month:2025-01|ids:1513,1687|component:1",
          "company_id": 4,
          "partner_company_name": null,
          "release_month_window": "2025-01~2025-01",
          "product_type_codes": [
            "CANCER",
            "SIMPLIFIED_IMPAIRED"
          ],
          "candidate_product_ids": [
            1513,
            1687
          ],
          "observation_ids": [
            7516,
            8183,
            8187,
            8189,
            8340
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:4|partner:unknown|type:CANCER,SIMPLIFIED_IMPAIRED|month:2025-01|ids:1513,1687\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"더블보장보험\", \"간편 더블보장보험\"], \"candidate_product_ids\": [1513, 1687], \"shared_high_info_tokens\": [\"15세부터\", \"23t09\", \"23t10\", \"3가지\", \"75세까지이며\", \"quot\", \"가능하다\", \"가입나이는\", \"가입이\", \"가입할\", \"간병\", \"간편\", \"간편고지\", \"강화\", \"강화한\", \"경우\", \"고혈압이\", \"관계자는\", \"금은\", \"나이는\", \"당뇨\", \"대폭\", \"더블\", \"더블보장\", \"두배로\", \"료는\", \"발생\", \"뿐만\", \"사망\", \"사망보장\"], \"family_signatures\": [\"간편더블\"], \"family_tokens\": [\"간편\", \"간편더블\", \"더블\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 1513, \"right\": 1687, \"name_similarity\": 0.82, \"context_similarity\": 0.4669}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [1687, 1513], \"family_signatures\": [\"간편더블\"]}}",
          "status": "review"
        },
        {
          "block_id": 670,
          "block_key": "company:4|partner:unknown|type:DEMENTIA_CARE|month:2025-04|ids:673,2018|component:1",
          "company_id": 4,
          "partner_company_name": null,
          "release_month_window": "2025-04~2025-06",
          "product_type_codes": [
            "DEMENTIA_CARE"
          ],
          "candidate_product_ids": [
            673,
            2018
          ],
          "observation_ids": [
            3720,
            9646
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:4|partner:unknown|type:DEMENTIA_CARE|month:2025-04|ids:673,2018\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"요양보험\", \"함께가는 요양보험\"], \"candidate_product_ids\": [673, 2018], \"shared_high_info_tokens\": [\"care\", \"dementia\", \"exclusive\", \"삼성생명\", \"요양\", \"홍원학\"], \"family_signatures\": [\"함께가는요양\"], \"family_tokens\": [\"요양\", \"함께가는\", \"함께가는요양\"], \"partner_candidates\": [], \"context_scores\": [{\"left\": 673, \"right\": 2018, \"name_similarity\": 0.82, \"context_similarity\": 0.3958}]}, \"parent_summary\": {\"candidate_count\": 2, \"candidate_product_ids\": [2018, 673], \"family_signatures\": [\"함께가는요양\"]}}",
          "status": "review"
        },
        {
          "block_id": 671,
          "block_key": "company:4|partner:네이버페이|type:HEALTH_COMPREHENSIVE|month:2025-05|ids:824,2163|component:1",
          "company_id": 4,
          "partner_company_name": "네이버페이",
          "release_month_window": "2025-05~2025-05",
          "product_type_codes": [
            "HEALTH_COMPREHENSIVE"
          ],
          "candidate_product_ids": [
            824,
            2163
          ],
          "observation_ids": [
            4667,
            10185,
            10191
          ],
          "block_reason": "{\"reason\": \"duplicate_component_block\", \"parent_block_key\": \"company:4|partner:네이버페이|type:HEALTH_COMPREHENSIVE|month:2025-03|ids:824,1401,1906,2163\", \"component\": {\"reason\": \"context_block\", \"candidate_count\": 2, \"candidate_names\": [\"뇌심 건강보험\", \"신 간편 뇌심 건강보험\"], \"candidate_product_ids\": [824, 2163], \"shared_high_info_tokens\": [\"가입할\", \"간편\", \"건강\", \"뇌심\", \"삼성\", \"삼성생명\", \"선봬\", \"유병자도\", \"인터넷\", \"있는\", \"최대\"], \"family_signatures\": [\"신간편뇌심\"], \"family_tokens\": [\"간편\", \"뇌심\", \"신간편뇌심\"], \"partner_candidates\": [\"네이버페이\"], \"context_scores\": [{\"left\": 824, \"right\": 2163, \"name_similarity\": 0.82, \"context_similarity\": 0.375}]}, \"parent_summary\": {\"candidate_count\": 4, \"candidate_product_ids\": [2163, 1906, 1401, 824], \"family_signatures\": [\"신간편뇌심\"]}}",
          "status": "review"
        }
      ],
      "versioned_display_update_count": 0
    },
    "exclusive_rights": {
      "block_count": 31,
      "auto_merge_count": 15,
      "review_count": 23,
      "mode": "rule_only_apply",
      "crawl_job_id": null,
      "date_from": "2025-01-01",
      "date_to": "2026-05-31"
    },
    "reviewed_count": 74
  },
  "qwen": {}
}
```
