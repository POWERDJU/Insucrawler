from __future__ import annotations


def choose_supported_value(extractor_value, verifier_verdict: str, suggested_value=None):
    if verifier_verdict in {"incorrect", "unsupported"}:
        return suggested_value
    return extractor_value
