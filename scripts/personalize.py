"""Fill in your name, GitHub username and (after deploying) your live-demo link.

    python scripts/personalize.py --name "Your Name" --github your-github-username
    python scripts/personalize.py --hf your-huggingface-username      # after deploying
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["LICENSE", "README.md", "web/src/App.tsx", "docs/DEMO_SCRIPT.md"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--github")
    ap.add_argument("--hf", help="Hugging Face username (adds the live-demo link to the README)")
    ap.add_argument("--space", default="raktsetu")
    a = ap.parse_args()
    for f in FILES:
        p = ROOT / f
        if not p.exists():
            continue
        s = old = p.read_text()
        if a.name:
            s = s.replace("YOUR_NAME", a.name)
        if a.github:
            s = s.replace("YOUR_GITHUB", a.github)
        if a.hf and f == "README.md":
            sub = re.sub(r"[^a-z0-9-]", "-", f"{a.hf}-{a.space}".lower())
            link = (f"**Live demo:** https://{sub}.hf.space · "
                    f"[Hugging Face Space](https://huggingface.co/spaces/{a.hf}/{a.space})")
            s = re.sub(r"<!-- LIVE_DEMO -->|\*\*Live demo:\*\*.*", link, s, count=1)
        if s != old:
            p.write_text(s)
            print("updated", f)
    left = [f for f in FILES if (ROOT / f).exists() and re.search(r"YOUR_(NAME|GITHUB)", (ROOT / f).read_text())]
    if left:
        print("still has placeholders:", ", ".join(left))
    if a.github:
        print("Now rebuild the web app so the GitHub link updates:  cd web && npm run build")


if __name__ == "__main__":
    main()
