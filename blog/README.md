# Blog posts

Add `.md` files here when you're ready. Example: `my-first-post.md`

```yaml
---
title: Post title
date: 2026-06-01
summary: One line for the blog index
---

Your Markdown here.
```

Build locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/build_blog.py
```

Docker builds run the same script automatically. Until you add a post, `/blog/` shows an empty index.

### Images (screenshots, GIFs)

Save files under `blog/media/<post-slug>/` and reference from the post:

```markdown
![Caption](../media/my-post-slug/screenshot.png)
```

Rebuild copies media into `src/blog/media/` for local preview and Docker deploy.
