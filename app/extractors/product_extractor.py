from __future__ import annotations

from app.extractors.extraction_schema import ExtractionResult, validate_extraction_payload


class ProductExtractor:
    def parse(self, payload: dict) -> ExtractionResult:
        return validate_extraction_payload(payload)
