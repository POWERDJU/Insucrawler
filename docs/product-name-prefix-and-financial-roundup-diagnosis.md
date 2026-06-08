# Product Name Prefix and Financial Roundup Diagnosis

Input workbook: `C:\Users\User\Downloads\insurance_product_comparison (21).xlsx`

The uploaded workbook was used only as an error-case fixture and diagnostic reference. Its product names were not used to build the prefix dictionary, and no production rule hardcodes product ids, row numbers, or URLs.

## Product 609 Type

- Export product id: `609`
- Product name: `한편 시그니처 여성 건강보험`
- Company: `한화손해보험`
- Source URL: `http://www.kdfnews.com/news/articleView.html?idxno=177328`
- Diagnosis: `한편` is a Korean discourse connector at the start of a sentence, not part of the product name.
- Generalized rule: strip only leading discourse prefixes such as `한편`, `또한`, `아울러`, `다만`, `그러나`, and `물론` before product save. Preserve the original raw mention as an alias.
- Expected cleaned canonical: `시그니처 여성 건강보험` or normalized spacing equivalent.

## Product 632 Type

- Export product id: `632`
- Product name: `군 복무 중 발생할 수 있는 상해 및 질병 보장 서비스`
- Company: `한화손해보험`
- Source URL: `https://www.delighti.co.kr/news/articleView.html?idxno=116697`
- Representative title: `신한은행, '나라사랑카드' 3기 사업자 중 최초로 발급 30만좌 돌파`
- Diagnosis: the source is centered on a bank/card context, and the insurance coverage service appears as a side benefit rather than a clean single-insurer product launch.
- Generalized rule: when insurer news is listed alongside banks, cards, securities firms, financial holding companies, or non-insurance financial products in independent roundup sections, exclude the source article from product/exclusive-right extraction. Also exclude bank/card-primary articles where insurance coverage/service is only an ancillary benefit and the title is not an insurance product launch.

## Product 625 Type

- Current uploaded workbook: product id `625` was not present, which means it had already been removed from the exported default product list.
- Regression fixture remains: `IBK기업은행 KOSPI200 지수연동예금 출시 / 한화손보 스폰서데이 / 하나금융 문화체험 / NH농협은행 캠페인`.
- Diagnosis: `KOSPI200 지수연동예금` is a bank deposit product and must never be saved as an insurance product.
- Generalized rule: detect non-insurance financial products such as `예금`, `적금`, `지수연동예금`, `KOSPI200`, `ELD`, `대출`, `카드`, `펀드`, and `ETF`. If mixed with insurer snippets in a roundup article, exclude the source article.

## Applied General Rules

1. Uploaded product strings are regression fixtures, not a prefix dictionary.
2. Leading Korean discourse prefixes are removed deterministically before canonical product save.
3. Prefix removal is leading-only and repeats up to three times to handle sequences such as `한편 또한`.
4. If the remaining product name is generic, weak, or a bad fragment, no active product is created.
5. Raw prefixed mentions can be kept as aliases/observations.
6. Mixed financial-institution roundup articles and bank/card-primary side-benefit articles are blocked before realtime extraction, queue creation, batch JSONL creation, and batch import.
7. Raw articles are preserved for audit. Cleanup is source-article scoped, not a physical product/event deletion policy.

## Verification

Run:

```powershell
python scripts/run_product_name_and_article_eligibility_goal_check.py
```

The report is written to `docs/product-name-and-article-eligibility-goal-result.md`.
