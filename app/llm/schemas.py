from __future__ import annotations

from app.extractors.extraction_schema import ExtractionResult, VerificationResult


def extraction_json_schema() -> dict:
    return ExtractionResult.model_json_schema()


def verification_json_schema() -> dict:
    return VerificationResult.model_json_schema()
