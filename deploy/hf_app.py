"""Hugging Face Spaces entry point (free "Gradio" SDK Space).

Hugging Face runs `python app.py` and routes the public URL to port 7860. We do not use Gradio's UI:
this starts the normal RaktSetu FastAPI server, which serves the API and the pre-built React app.
deploy/huggingface.py copies this file to app.py in the Space.
"""
import os
import subprocess
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    if not all((ROOT / "artifacts" / f).exists() for f in ("forecaster.joblib", "surge_radar.joblib")):
        print("Model files missing: training them now (about 1-2 minutes)...", flush=True)
        subprocess.run([sys.executable, "-m", "raktsetu", "train"], cwd=ROOT, check=True)
    port = int(os.environ.get("GRADIO_SERVER_PORT", os.environ.get("PORT", "7860")))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port)
