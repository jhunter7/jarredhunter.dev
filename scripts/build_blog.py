#!/usr/bin/env python3
"""Compile blog/posts/*.md into src/blog/ static HTML."""

from __future__ import annotations

import html
import re
import shutil
from datetime import datetime
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "blog" / "posts"
MEDIA_DIR = ROOT / "blog" / "media"
OUT_DIR = ROOT / "src" / "blog"

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

MD_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.nl2br",
    "markdown.extensions.sane_lists",
]


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw

    match = FRONT_MATTER_RE.match(raw)
    if match:
        meta = yaml.safe_load(match.group(1)) or {}
        body = raw[match.end() :]

    # Some editors escape backticks (\`\`\`) which breaks fenced code blocks.
    body = body.replace("\\`\\`\\`", "```").replace("\\`", "`")

    slug = path.stem
    title = str(meta.get("title") or slug.replace("-", " ").title())
    summary = str(meta.get("summary") or "")
    date_raw = meta.get("date")
    if isinstance(date_raw, datetime):
        date_obj = date_raw.date()
    elif date_raw:
        date_obj = datetime.strptime(str(date_raw)[:10], "%Y-%m-%d").date()
    else:
        date_obj = datetime.fromtimestamp(path.stat().st_mtime).date()

    html_body = markdown.markdown(
        body.strip(),
        extensions=MD_EXTENSIONS,
        output_format="html5",
    )

    return {
        "slug": slug,
        "title": title,
        "summary": summary,
        "date": date_obj,
        "date_display": date_obj.strftime("%Y-%m-%d"),
        "html_body": html_body,
    }


def nav_html(prefix: str, active: str) -> str:
    links = [
        ("home", f"{prefix}index.html", "home"),
        ("blog", f"{prefix}blog/", "blog"),
        ("focus", f"{prefix}index.html#focus", "focus"),
        ("skills", f"{prefix}index.html#technologies", "skills"),
        ("experience", f"{prefix}index.html#work-experience", "experience"),
        ("builds", f"{prefix}index.html#projects", "builds"),
        ("contact", f"{prefix}index.html#contact", "contact"),
    ]
    items = []
    for key, href, label in links:
        if key == active:
            items.append(f'<li><a href="{href}" aria-current="page">{label}</a></li>')
        else:
            items.append(f'<li><a href="{href}">{label}</a></li>')
    return "\n        ".join(items)


def page_shell(
    *,
    title: str,
    description: str,
    prefix: str,
    active_nav: str,
    main_content: str,
) -> str:
    esc_title = html.escape(title)
    esc_desc = html.escape(description)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc_title} — Jarred Hunter</title>
  <meta name="description" content="{esc_desc}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=Geist:wght@300;400;500;600&family=JetBrains+Mono:ital,wght@0,400;0,500;0,700;1,400&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{prefix}css/style.css" />
  <script defer src="https://cloud.umami.is/script.js" data-website-id="7b5f57f9-e7fa-4ba4-9820-37300ce57bfb" data-host-url="https://cloud.umami.is" data-domains="jarredhunter.dev,www.jarredhunter.dev"></script>
</head>
<body class="blog-page">
  <nav>
    <div class="nav-inner">
      <a href="{prefix}index.html" class="logo">jarredhunter.dev</a>
      <ul class="nav-links">
        {nav_html(prefix, active_nav)}
      </ul>
      <div class="nav-right">
        <button class="theme-toggle" id="theme-toggle" aria-label="Toggle theme">
          <svg class="icon-moon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg class="icon-sun" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        </button>
        <a href="https://cal.com/jhunter7/" class="nav-cta" target="_blank" rel="noopener">./request-chat</a>
      </div>
    </div>
  </nav>

  <main class="blog-main">
    <div class="container">
{main_content}
    </div>
  </main>

  <div class="container">
    <footer>
      <div class="footer-left">© 2026 <span>Jarred Hunter</span></div>
      <div class="footer-right">AI SECURITY · ZERO-TRUST · PLATFORM ENGINEERING</div>
    </footer>
  </div>

  <script src="{prefix}js/main.js"></script>
</body>
</html>
"""


def render_index(posts: list[dict]) -> str:
  cards = []
  for post in posts:
    title = html.escape(post["title"])
    summary = html.escape(post["summary"]) if post["summary"] else ""
    slug = html.escape(post["slug"])
    date = html.escape(post["date_display"])
    summary_html = f'<p class="blog-card-summary">{summary}</p>' if summary else ""
    cards.append(
      f"""      <article class="blog-card">
        <div class="blog-card-date">{date}</div>
        <h2 class="blog-card-title"><a href="{slug}/">{title}</a></h2>
        {summary_html}
        <a href="{slug}/" class="blog-card-link">./read-post</a>
      </article>"""
    )

  cards_block = "\n".join(cards) if cards else '      <p class="blog-empty">No posts yet. Add a <code>.md</code> file under <code>blog/posts/</code>.</p>'

  main = f"""      <p class="section-tag">// blog</p>
      <h1 class="section-heading">Notes from the Sandbox...</h1>
      <p class="blog-index-lede">Notes on AI security, platform engineering, and zero-trust built from Markdown at deploy time.</p>
      <div class="blog-list">
{cards_block}
      </div>"""

  return page_shell(
    title="Blog",
    description="Jarred Hunter — blog on AI security, platform engineering, and zero-trust.",
    prefix="../",
    active_nav="blog",
    main_content=main,
  )


def render_post(post: dict) -> str:
  title = html.escape(post["title"])
  date = html.escape(post["date_display"])
  main = f"""      <p class="blog-back"><a href="../">← ./blog</a></p>
      <article class="blog-article">
        <h1 class="blog-post-title">{title}</h1>
        <p class="blog-post-date">{date}</p>
        <div class="blog-content">
{post["html_body"]}
        </div>
      </article>"""

  desc = post["summary"] or post["title"]
  return page_shell(
    title=post["title"],
    description=desc,
    prefix="../../",
    active_nav="blog",
    main_content=main,
  )


def main() -> None:
  if not POSTS_DIR.is_dir():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

  if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)
  OUT_DIR.mkdir(parents=True)

  posts = []
  for path in sorted(POSTS_DIR.glob("*.md")):
    posts.append(parse_post(path))

  posts.sort(key=lambda p: p["date"], reverse=True)

  (OUT_DIR / "index.html").write_text(render_index(posts), encoding="utf-8")

  for post in posts:
    post_dir = OUT_DIR / post["slug"]
    post_dir.mkdir(parents=True, exist_ok=True)
    (post_dir / "index.html").write_text(render_post(post), encoding="utf-8")

  out_media = OUT_DIR / "media"
  if out_media.exists():
    shutil.rmtree(out_media)
  if MEDIA_DIR.is_dir():
    shutil.copytree(MEDIA_DIR, out_media)

  print(f"Built {len(posts)} post(s) → {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
  main()
