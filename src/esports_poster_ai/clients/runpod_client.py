"""
RunPod Serverless client for the fine-tuned background model.

Implements the `BackgroundGenerator` seam (`stages/background_select.py`): given a
`KeyartPrompt`, it submits a job to the serverless endpoint, polls until done, and
returns the generated PNG as bytes. No persistent pod — per-second billing.

Endpoint contract (see the worker `handler.py`):
    POST /run    {"input": {prompt, negative_prompt, width, height, steps, guidance, seed}}
                 -> {"id": <job_id>}
    GET  /status/{id}  -> {"status": ..., "output": {"image_base64": ...}}

Uses httpx (already a dependency via the OpenAI SDK). Reads
`settings.runpod_api_key` / `settings.runpod_endpoint_id`.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Optional

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.prompt.keyart import KeyartPrompt

logger = logging.getLogger(__name__)

_API_BASE = "https://api.runpod.ai/v2"
_TERMINAL_OK = "COMPLETED"
_TERMINAL_BAD = {"FAILED", "CANCELLED", "TIMED_OUT"}

# Transient HTTP failures (connection drops, timeouts, 429/5xx) are retried with
# backoff so a brief network blip during a long fill self-heals instead of
# skipping an image. Terminal 4xx (bad request/auth) is NOT retried.
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _is_retryable_http(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


_http_retry = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, max=20),
    retry=retry_if_exception(_is_retryable_http),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


class RunpodBackgroundGenerator:
    """Generate one background via the RunPod Serverless endpoint (bytes out)."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        steps: int = 30,
        guidance: float = 4.0,
        poll_interval_s: float = 3.0,
        timeout_s: float = 480.0,
    ) -> None:
        self.settings = settings or get_settings()
        self.steps = steps
        self.guidance = guidance
        self.poll_interval_s = poll_interval_s
        self.timeout_s = timeout_s  # generous — first call cold-starts (~2-3 min)

    # ------------------------------------------------------------------ creds
    def _require_creds(self) -> None:
        if not self.settings.runpod_api_key or not self.settings.runpod_endpoint_id:
            raise RuntimeError(
                "AI-generated background requires RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID "
                "in the environment / .env."
            )

    def _base(self) -> str:
        return f"{_API_BASE}/{self.settings.runpod_endpoint_id}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.settings.runpod_api_key}"}

    # --------------------------------------------------------------- async API
    # `submit` + `poll` let a caller pipeline many jobs (keep RunPod's queue full
    # so the serverless worker never scales to zero between images). `generate`
    # is the blocking convenience built on top for single-image callers.
    @_http_retry
    def _post_run(self, payload: dict) -> dict:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{self._base()}/run", headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()

    @_http_retry
    def _get_status(self, job_id: str) -> dict:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{self._base()}/status/{job_id}", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def submit_raw(
        self,
        *,
        prompt_text: str,
        negative_prompt: str = "",
        width: int,
        height: int,
        seed: int,
    ) -> str:
        """
        Enqueue one job from raw fields (no `KeyartPrompt`) and return its job id.

        Used by the durable refill, whose prompts are persisted as plain records. A
        generous RunPod-side `policy.ttl` keeps the job QUEUED while it waits for a
        free GPU (during a shortage) instead of RunPod dropping it — so the patient
        drain can keep polling the same job rather than churning submissions.
        """
        self._require_creds()
        payload = {
            "input": {
                "prompt": prompt_text,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "steps": self.steps,
                "guidance": self.guidance,
                "seed": seed,
            },
            "policy": {"ttl": self.settings.bg_bank_job_ttl_ms},
        }
        job_id = self._post_run(payload).get("id")
        if not job_id:
            raise RuntimeError("RunPod /run returned no job id")
        logger.info("runpod.submitted", extra={"job_id": job_id, "seed": seed})
        return job_id

    def submit(self, prompt: KeyartPrompt, *, seed: int) -> str:
        """Enqueue one job on the endpoint and return its RunPod job id (no wait)."""
        return self.submit_raw(
            prompt_text=prompt.prompt,
            negative_prompt=prompt.negative_prompt,
            width=prompt.width,
            height=prompt.height,
            seed=seed,
        )

    def cancel(self, job_id: str) -> None:
        """Best-effort cancel of a submitted job (used when retrying a stuck one)."""
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._base()}/cancel/{job_id}", headers=self._headers())
                resp.raise_for_status()
            logger.info("runpod.cancelled", extra={"job_id": job_id})
        except Exception as e:  # noqa: BLE001 — cancel is best-effort
            logger.warning("runpod.cancel_failed", extra={"job_id": job_id, "error": str(e)})

    def poll(self, job_id: str) -> tuple[str, Optional[bytes]]:
        """
        One status check for a submitted job.

        Returns `(status, image_bytes)` — `image_bytes` is the decoded PNG when the
        job is COMPLETED, else None (still queued/running). Raises on a terminal
        failure (FAILED/CANCELLED/TIMED_OUT or a worker error). Transient HTTP
        errors are retried internally before propagating.
        """
        self._require_creds()
        data = self._get_status(job_id)
        status = data.get("status")

        if status == _TERMINAL_OK:
            out = data.get("output") or {}
            if isinstance(out, dict) and out.get("error"):
                raise RuntimeError(f"RunPod worker error: {out['error']}")
            b64 = out.get("image_base64") if isinstance(out, dict) else None
            if not b64:
                raise RuntimeError(f"RunPod output missing image_base64: {str(out)[:300]}")
            logger.info("runpod.completed", extra={"job_id": job_id})
            return status, base64.b64decode(b64)

        if status in _TERMINAL_BAD:
            raise RuntimeError(f"RunPod job {status}: {str(data)[:400]}")

        return status, None

    def generate(self, prompt: KeyartPrompt, *, seed: int) -> bytes:
        """Submit one job and block until it completes (single-image convenience)."""
        job_id = self.submit(prompt, seed=seed)
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            _, data = self.poll(job_id)
            if data is not None:
                return data
            time.sleep(self.poll_interval_s)
        raise TimeoutError(f"RunPod job {job_id} did not complete within {self.timeout_s:.0f}s")


__all__ = ["RunpodBackgroundGenerator"]
