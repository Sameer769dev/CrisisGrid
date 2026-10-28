"""CrisisGrid — Production Modal.com Serverless ASGI & Parallel Verifier Deployment.

Why Modal for CrisisGrid (AGENTS.md §2 strictly enforced):
- 100% of AI model inference STILL runs exclusively on the official Meta Model API
  (`https://api.meta.ai/v1`) authenticated via `MODEL_API_KEY`.
- Modal is used strictly as a high-performance, zero-cold-start CPU serverless
  runtime (`min_containers=1`, 4 vCPUs, 4 GB RAM, 600s request timeout) so judges
  never hit Render free-tier cold starts (50-90s) or gateway timeouts during the
  5-model autonomous pipeline (`sam-3.1` x9 -> `muse-voice-transcribe-1.0` ->
  `muse-spark-1.3` -> deterministic Python verifier -> `muse-wonder-1.0` -> `muse-image-1.0`).

Quick Deploy (uses $100 Modal credit; ~$0.15/day for 1 always-warm CPU container):
    pip install modal
    modal setup
    modal secret create crisisgrid-secrets MODEL_API_KEY=<your_meta_model_api_key>
    modal deploy backend/modal_app.py
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MODAL_CONFIG: dict[str, Any] = {
    "app_name": "crisisgrid-api",
    "secret_name": "crisisgrid-secrets",
    "cpu_cores": 4.0,
    "memory_mb": 4096,
    "min_containers": 1,
    "scaledown_window_seconds": 300,
    "timeout_seconds": 600,
    "gpu": None,  # Strict AGENTS.md §2 compliance: zero third-party GPU inference
    "ai_inference_provider": "https://api.meta.ai/v1",
}


def detect_compute_runtime() -> str:
    """Detect whether the backend is executing inside Modal, Render, or local Python."""
    if os.environ.get("MODAL_ENVIRONMENT") or os.environ.get("MODAL_TASK_ID") or os.environ.get("CRISISGRID_RUNTIME") == "modal":
        return "modal_serverless_cpu"
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        return "render_web_service"
    return "local_python"


try:
    import modal  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - allows importing MODAL_CONFIG without modal installed
    modal = None  # type: ignore[assignment]

if modal is not None:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    BACKEND_DIR = Path(__file__).resolve().parent

    image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
        .env({"CRISISGRID_RUNTIME": "modal", "PYTHONPATH": "/root"})
        .add_local_dir(str(BACKEND_DIR), remote_path="/root/backend")
    )

    app = modal.App(MODAL_CONFIG["app_name"], image=image)

    @app.function(
        cpu=MODAL_CONFIG["cpu_cores"],
        memory=MODAL_CONFIG["memory_mb"],
        min_containers=MODAL_CONFIG["min_containers"],
        scaledown_window=MODAL_CONFIG["scaledown_window_seconds"],
        timeout=MODAL_CONFIG["timeout_seconds"],
        secrets=[modal.Secret.from_name(MODAL_CONFIG["secret_name"])],
    )
    @modal.asgi_app()
    def crisisgrid_asgi():
        """Always-warm FastAPI ASGI entrypoint on Modal (0ms cold start for judges)."""
        from backend.main import app as fastapi_app

        return fastapi_app

    @app.function(
        cpu=2.0,
        memory=2048,
        timeout=300,
    )
    def verify_sector_geometry_worker(sector_payload: dict[str, Any]) -> dict[str, Any]:
        """Pure-Python deterministic geometry verifier worker for parallel sector fan-out.

        Zero AI model calls inside this worker: evaluates RLE masks, bbox IoU,
        safe-surface support, and landing-zone clearance in isolated Modal CPU containers.
        """
        from backend.services.verifiable_corridor_engine import verify_candidates

        scan_result = sector_payload.get("scan_result") or {}
        corridors = sector_payload.get("candidate_evacuation_corridors")
        landing_zones = sector_payload.get("candidate_landing_zones")
        verification = verify_candidates(
            scan_result,
            corridors=corridors,
            landing_zones=landing_zones,
        )
        return {
            "sector_id": sector_payload.get("sector_id") or "sector",
            "name": sector_payload.get("name") or "Sector",
            "runtime": "modal_serverless_cpu",
            "model_calls": 0,
            "verification": verification,
        }
