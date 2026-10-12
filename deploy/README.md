# Deploying RaktSetu

The app is one Docker container (FastAPI serves the API and the built React app on port 8000). No secrets are needed.

## Hugging Face Spaces (free, recommended)

Free CPU Spaces give 2 vCPU and 16 GB RAM, enough for live simulations. The demo flows are precomputed in `artifacts/cache/`, so they answer instantly.

1. Sign up at https://huggingface.co/join.
2. **New Space** at https://huggingface.co/new-space. Name `raktsetu`, licence MIT, **SDK: Docker**, template **Blank**, hardware **CPU basic (free)**, **Public**. Click *Create Space*.
3. **Token** at https://huggingface.co/settings/tokens. Click *Create new token*, type **Write**, and copy it.
4. From the repository root, after committing: `deploy/huggingface.sh <your-hf-username>`. Username = your HF username, password = the token.
5. Open `https://huggingface.co/spaces/<user>/raktsetu` and wait for the build (3–6 min, it shows *Running*). The app is at `https://<user>-raktsetu.hf.space`.
6. Add the link to the README: `python scripts/personalize.py --hf <your-hf-username>`, then commit and push to GitHub.

To redeploy after changes: commit, then run step 4 again. If you changed the engine, run `python -m raktsetu precompute` before committing.
Free Spaces sleep after ~48 h without visitors. Open the link a few minutes before judging so it is awake.

## Render (alternative)

New → Web Service → connect the GitHub repo → it detects the `Dockerfile` → Instance type *Free* → Deploy.
The free plan has very little CPU: precomputed demo flows are instant, but custom simulations can take minutes.

## Any Docker host

```bash
docker build -t raktsetu .
docker run -p 8000:8000 raktsetu      # http://localhost:8000
```
