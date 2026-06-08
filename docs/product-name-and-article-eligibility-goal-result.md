# Product Name and Article Eligibility Goal Result

GOAL status = PASS

Checks:
- Korean discourse prefixes are stripped before canonical product save.
- Original prefixed names remain as aliases.
- Generic names after prefix cleanup are rejected.
- Product 632-style mixed bank/insurer roundup articles are ineligible.
- Product 625-style KOSPI200 deposits are not saved as insurance products.
- Batch import skips outputs for ineligible articles.
- No realtime LLM provider is called.

Failures:
- None