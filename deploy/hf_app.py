"""Hugging Face Spaces entry point (free "Gradio" SDK Space).

Hugging Face runs `python app.py` and routes the public URL to port 7860. We do not use Gradio's UI:
this starts the normal RaktSetu FastAPI server, which serves the API and the pre-built React app.
deploy/huggingface.py copies this file to app.py in the Space, together with models trained for the
Space's library versions (deploy/space-models/, see deploy/requirements-space.txt).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS = ("forecaster.joblib", "surge_radar.joblib")


def ensure_models():
    """Use the shipped models; if they are missing, train them into a writable folder (about 1-2 minutes)."""
    shipped = ROOT / "artifacts"
    if all((shipped / f).exists() for f in MODELS):
        return
    target = shipped if os.access(shipped, os.W_OK) else Path("/tmp/raktsetu-models")
    target.mkdir(parents=True, exist_ok=True)
    os.environ["RAKTSETU_MODEL_DIR"] = str(target)
    if not all((target / f).exists() for f in MODELS):
        print(f"Model files missing: training them into {target} (about 1-2 minutes)...", flush=True)
        subprocess.run([sys.executable, "-m", "raktsetu", "train", "--no-eval"], cwd=ROOT, check=True)


if __name__ == "__main__":
    ensure_models()
    import uvicorn

    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", "7860")))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port)
