"""Deploy RaktSetu to a free Hugging Face Space.

Hugging Face Docker Spaces are paid, but "Gradio" SDK Spaces on CPU basic (2 vCPU, 16 GB) are free.
A Gradio Space simply runs `python app.py`, so we use it to run our own FastAPI server.

    pip install huggingface_hub
    python deploy/huggingface.py                 # asks for a WRITE token (typing is hidden)
    python deploy/huggingface.py --dry-run       # only build the upload folder locally, to inspect or test

What gets uploaded: the last COMMITTED version of the repo (git archive HEAD), the freshly built web app
(web/dist, which is not in git), deploy/hf_app.py as app.py, and the README with the Space header.
"""
from __future__ import annotations

import argparse
import getpass
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRADIO_VERSION = "6.30.0"  # resolved together with requirements.txt on Python 3.11 (tested)

HEADER = f"""---
title: RaktSetu
emoji: 🩸
colorFrom: red
colorTo: indigo
sdk: gradio
sdk_version: {GRADIO_VERSION}
python_version: "3.11"
app_file: app.py
pinned: false
license: mit
short_description: Predictive blood and platelet sharing for Jaipur blood banks
---

"""


def run(cmd, cwd=None):
    print("  $", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def build_web():
    web = ROOT / "web"
    if not (web / "node_modules").exists():
        run(["npm", "install"], cwd=web)
    run(["npm", "run", "build"], cwd=web)


def stage(dst: Path) -> str:
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if dirty:
        print("  note: you have uncommitted changes; only the last commit is deployed (plus the web build).")
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "HEAD"], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dst, filter="data")
    shutil.copytree(ROOT / "web" / "dist", dst / "web" / "dist", dirs_exist_ok=True)
    shutil.copy(ROOT / "deploy" / "hf_app.py", dst / "app.py")
    readme = dst / "README.md"
    readme.write_text(HEADER + readme.read_text())
    return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", default="raktsetu", help="Space name (default: raktsetu)")
    ap.add_argument("--user", help="Hugging Face username or org (default: the token's owner)")
    ap.add_argument("--dry-run", action="store_true", help="build the upload folder and stop")
    a = ap.parse_args()

    print("1/3 Building the web app")
    build_web()
    print("2/3 Preparing the upload folder")
    dst = Path(tempfile.mkdtemp(prefix="raktsetu-space-"))
    sha = stage(dst)
    print(f"  staged commit {sha} in {dst}")
    if a.dry_run:
        print(f"Dry run: test it with  cd {dst} && python app.py   (then open http://localhost:7860)")
        return

    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("Install the uploader first:  pip install huggingface_hub   (or: uv pip install huggingface_hub)")
    token = os.environ.get("HF_TOKEN") or getpass.getpass("3/3 Paste your Hugging Face WRITE token (typing is hidden): ").strip()
    api = HfApi(token=token)
    me = api.whoami()["name"]
    repo_id = f"{a.user or me}/{a.space}"
    print(f"  logged in as {me}; deploying to {repo_id}")
    api.create_repo(repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
    api.upload_folder(folder_path=str(dst), repo_id=repo_id, repo_type="space",
                      commit_message=f"Deploy RaktSetu {sha}", delete_patterns=["*"])
    shutil.rmtree(dst, ignore_errors=True)
    sub = repo_id.lower().replace("/", "-").replace("_", "-").replace(".", "-")
    print()
    print(f"Uploaded. Watch it build (3-6 min): https://huggingface.co/spaces/{repo_id}")
    print(f"Your live app:                    https://{sub}.hf.space")


if __name__ == "__main__":
    main()
