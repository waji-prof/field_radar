"""Summary hook — the one place to plug in AI later.

Today ("none"): the dashboard shows the original headline plus a short
description extracted from the source (an abstract, a feed snippet).
This costs nothing.

Later, set `summarizer` in config.toml and implement the provider below.
It is called only for NEW items, once each, and the result is stored in
the database, so you never pay twice for the same item:

  "ollama" — free and open source; runs a model on your own PC
             (https://ollama.com). Needs a reasonably powerful computer.
  "claude" — paid Anthropic API. Ask before turning this on.
"""

from .textutil import shorten


def extract(item):
    """Free fallback: a clean, short excerpt of the source's own text."""
    return shorten(item.get("summary") or "", 340)


def summarize(item, settings):
    """Return an AI summary string, or None to use the free excerpt."""
    provider = (settings.get("summarizer") or "none").lower()
    if provider == "none":
        return None
    # Not implemented yet on purpose — no costs without your say-so.
    # Implement e.g. summarize_with_ollama(item) here, return its text.
    return None
