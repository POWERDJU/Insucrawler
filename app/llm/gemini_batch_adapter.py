from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


COMPLETED_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
    "BATCH_STATE_SUCCEEDED",
    "BATCH_STATE_FAILED",
    "BATCH_STATE_CANCELLED",
    "BATCH_STATE_EXPIRED",
}


@dataclass
class BatchSubmitResult:
    provider_batch_id: str
    provider_status: str
    provider_input_file_name: str | None = None
    raw_response: dict[str, Any] | None = None


@dataclass
class BatchStatusResult:
    provider_batch_id: str
    provider_status: str
    completed: bool
    output_file_name: str | None = None
    completed_count: int = 0
    failed_count: int = 0
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None


class GeminiBatchAdapter:
    """REST adapter for Gemini Batch API using File API JSONL input."""

    def __init__(self, api_key: str | None = None, timeout: int = 120) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com"

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini Batch API")

    def submit_jsonl(self, *, input_file_path: str | Path, model_name: str, display_name: str) -> BatchSubmitResult:
        self._ensure_configured()
        input_path = Path(input_file_path)
        file_name = self._upload_file(input_path, display_name=display_name)
        model = model_name.removeprefix("models/")
        response = httpx.post(
            f"{self.base_url}/v1beta/models/{model}:batchGenerateContent",
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json={
                "batch": {
                    "display_name": display_name,
                    "input_config": {"file_name": file_name},
                }
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        provider_batch_id = payload.get("name") or payload.get("metadata", {}).get("name")
        if not provider_batch_id:
            raise RuntimeError(f"Gemini Batch API did not return a batch name: {json.dumps(payload, ensure_ascii=False)[:500]}")
        status = self._extract_state(payload) or "JOB_STATE_PENDING"
        return BatchSubmitResult(provider_batch_id=provider_batch_id, provider_status=status, provider_input_file_name=file_name, raw_response=payload)

    def get_status(self, provider_batch_id: str) -> BatchStatusResult:
        self._ensure_configured()
        response = httpx.get(
            f"{self.base_url}/v1beta/{provider_batch_id}",
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        status = self._extract_state(payload) or "JOB_STATE_UNKNOWN"
        stats = payload.get("metadata", {}).get("batchStats") or payload.get("batchStats") or {}
        output_file = self._extract_output_file_name(payload)
        error = payload.get("error")
        return BatchStatusResult(
            provider_batch_id=provider_batch_id,
            provider_status=status,
            completed=status in COMPLETED_STATES,
            output_file_name=output_file,
            completed_count=int(stats.get("successfulRequestCount") or stats.get("successCount") or 0),
            failed_count=int(stats.get("failedRequestCount") or stats.get("failureCount") or 0),
            error_message=json.dumps(error, ensure_ascii=False) if error else None,
            raw_response=payload,
        )

    def download_results(self, *, output_file_name: str, output_file_path: str | Path) -> Path:
        self._ensure_configured()
        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(
            f"{self.base_url}/download/v1beta/{output_file_name}:download",
            params={"alt": "media"},
            headers={"x-goog-api-key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path

    def _upload_file(self, input_path: Path, *, display_name: str) -> str:
        content = input_path.read_bytes()
        start = httpx.post(
            f"{self.base_url}/upload/v1beta/files",
            headers={
                "x-goog-api-key": self.api_key,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(content)),
                "X-Goog-Upload-Header-Content-Type": "application/jsonl",
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": display_name}},
            timeout=self.timeout,
        )
        start.raise_for_status()
        upload_url = start.headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Gemini File API did not return x-goog-upload-url")
        upload = httpx.post(
            upload_url,
            headers={
                "Content-Length": str(len(content)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            content=content,
            timeout=self.timeout,
        )
        upload.raise_for_status()
        payload = upload.json()
        file_name = payload.get("file", {}).get("name")
        if not file_name:
            raise RuntimeError(f"Gemini File API did not return file.name: {json.dumps(payload, ensure_ascii=False)[:500]}")
        return file_name

    @staticmethod
    def _extract_state(payload: dict[str, Any]) -> str | None:
        state = payload.get("state")
        if isinstance(state, dict):
            return state.get("name")
        if isinstance(state, str):
            return state
        metadata_state = payload.get("metadata", {}).get("state")
        if isinstance(metadata_state, dict):
            return metadata_state.get("name")
        if isinstance(metadata_state, str):
            return metadata_state
        return None

    @staticmethod
    def _extract_output_file_name(payload: dict[str, Any]) -> str | None:
        response = payload.get("response") or {}
        dest = payload.get("dest") or {}
        return response.get("responsesFile") or response.get("responses_file") or dest.get("fileName") or dest.get("file_name")
