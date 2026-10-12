# Deploying RaktSetu

The app is one Python web server: FastAPI serves the API and the built React app. No secrets are needed.
The demo flows are precomputed in `artifacts/cache/`, so even a small server answers them instantly.

## Hugging Face Spaces (free, recommended)

Hugging Face **Docker** Spaces are paid, but **Gradio** Spaces on *CPU basic* (2 vCPU, 16 GB) are free.
A Gradio Space just runs `python app.py`, so `deploy/hf_app.py` uses it to start our FastAPI server. We don't use Gradio's UI.
The Space installs `deploy/requirements-space.txt` (works on Python 3.10 and 3.11) and ships the models in `deploy/space-models/`,
trained with those library versions. If you retrain, refresh them with `RAKTSETU_MODEL_DIR=deploy/space-models python -m raktsetu train --no-eval`
inside a Python 3.10 or 3.11 environment that has `deploy/requirements-space.txt` installed.

1. Sign up at https://huggingface.co/join and verify your email.
2. Create a token at https://huggingface.co/settings/tokens: *Create new token*, type **Write**, create, and copy it (starts with `hf_`).
3. From the repository root, after committing your changes:
   ```bash
   source .venv/bin/activate
   pip install huggingface_hub           # already in requirements-dev.txt
   python deploy/huggingface.py          # paste the token when asked (typing is hidden)
   ```
   The script builds the web app, packages the **last commit** plus the build, creates the Space `<you>/raktsetu` if needed (Gradio SDK, free CPU), and uploads.
4. Open `https://huggingface.co/spaces/<you>/raktsetu`. It shows *Building* for 3–6 minutes, then *Running*. The app is at `https://<you>-raktsetu.hf.space`.
5. Add the link to the README: `python scripts/personalize.py --hf <you>`, then commit and push.

To redeploy: commit, then run step 3 again. If you changed the engine, run `python -m raktsetu precompute --fresh` first.
To test the exact upload locally: `python deploy/huggingface.py --dry-run`, then `cd <printed folder> && python app.py` and open http://localhost:7860.
Free Spaces sleep after ~48 h without visitors. Open the link a few minutes before judging so it's awake.

## Render (alternative, uses the Dockerfile)

New → Web Service → connect the GitHub repo → it detects the `Dockerfile` → instance type *Free* → Deploy.
The free plan has very little CPU: precomputed demo flows are instant, but custom simulations can take minutes.

## Any Docker host

```bash
docker build -t raktsetu .
docker run -p 8000:8000 raktsetu      # http://localhost:8000
```

## Troubleshooting

- **Build log starts with `FROM python:3.10.13` and installs `torch`, then fails on `numpy==2.4.6`:** the Space is on **ZeroGPU** hardware, which forces Python 3.10. Run `python deploy/huggingface.py` again (it switches the Space to *CPU basic*), or go to Space → **Settings** → **Space hardware** → **CPU basic (free)** → *Confirm*.
- **Page says "Runtime error":** open the **Logs** tab → *Container*. The last lines name the problem.
- **First load is slow:** a sleeping Space takes about 1 minute to wake up.
