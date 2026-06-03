#!/usr/bin/env bash
# Rebuild blog HTML from blog/posts/*.md
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r scripts/requirements.txt
fi

.venv/bin/python scripts/build_blog.py
echo ""
echo "Preview:  cd src && python3 -m http.server 5500"
echo "Blog:     http://localhost:5500/blog/"
echo "Post:     http://localhost:5500/blog/i-built-an-ai-agent-then-i-tried-to-break-it/"
