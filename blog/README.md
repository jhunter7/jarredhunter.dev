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

## Writing voice

These posts are lab notes for engineers, not SEO content. Cursor picks up `.cursor/rules/blog-voice.mdc` when editing files here.

**Sound like you**

- Write in first person for your own experiments.
- Prefer short, direct sentences. One idea per paragraph when you can.
- A little personality is fine (`me included`, dry asides). Corporate polish is not.

**Don't write like a model**

Cut or rewrite anything that feels generated:

| Skip | Write instead |
|------|----------------|
| "In this post we will explore…" | State the question in line 1 |
| "This is not a benchmark. It is a walkthrough." | "This isn't a benchmark — it's a lab write-up." |
| "In plain terms…" / "That is exactly why…" | Just say the thing |
| Explaining every flag in a copied command block | Call out only the flags that matter to the claim |
| Ending every section by restating the thesis | End when the point is made |

**Technical honesty**

- Say upfront what the experiment can and cannot prove.
- Show prompts, scorer rules, and hashes — don't ask readers to trust "machine-scored."
- Baseline before training. If the test set fails, report it; don't tweak and pretend it's the same test.
- Arithmetic must match the scoreboard (if you say 7/8, show how you got 7).

**Keep artifacts sacred**

- Command blocks and run output stay verbatim.
- Edit the prose *around* evidence, not the evidence itself.
- If a hash appears in narrative text, it must match the hash in the log block.

**Quick self-check before publish**

1. Read aloud — generic sentences could belong to any ML blog → rewrite.
2. Search for: "delve", "landscape", "robust", "comprehensive", "leverage", "crucial".
3. Count how many times you restate the conclusion in one section — more than once is probably too many.

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
