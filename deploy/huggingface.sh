#!/usr/bin/env bash
# Deploy RaktSetu to a free Hugging Face Docker Space.
#   1. Create the Space first: https://huggingface.co/new-space  (SDK: Docker, template: Blank, hardware: CPU basic, public)
#   2. Create a token with WRITE access: https://huggingface.co/settings/tokens
#   3. Run:  deploy/huggingface.sh <hf-username> [space-name]
#      When git asks for a password, paste the token.
# It pushes the last COMMITTED version (git archive HEAD), adds the Space header to the README,
# and leaves out *.joblib (Hugging Face rejects binary files; the Docker build retrains them).
set -euo pipefail
HF_USER="${1:?usage: deploy/huggingface.sh <hf-username> [space-name]}"
SPACE="${2:-raktsetu}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git -C "$ROOT" archive HEAD | tar -x -C "$TMP"
cd "$TMP"
rm -f artifacts/*.joblib
{
  printf -- '---\ntitle: RaktSetu\nemoji: 🩸\ncolorFrom: red\ncolorTo: indigo\nsdk: docker\napp_port: 8000\npinned: false\nlicense: mit\nshort_description: Predictive blood and platelet sharing for Jaipur blood banks\n---\n\n'
  cat README.md
} > README.hf && mv README.hf README.md

git init -q -b main
git add -A
git commit -qm "Deploy RaktSetu $(git -C "$ROOT" rev-parse --short HEAD)"
git push --force "https://huggingface.co/spaces/$HF_USER/$SPACE" main

SUB="$(echo "$HF_USER-$SPACE" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-\n' '-')"
echo
echo "Pushed. Watch the build (3-6 min): https://huggingface.co/spaces/$HF_USER/$SPACE"
echo "Your live app:                     https://$SUB.hf.space"
