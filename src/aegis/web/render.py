"""Render task body markdown to HTML for the dashboard.

`html=False` keeps raw HTML escaped — task bodies come from the user's
filesystem, but we still want defense in depth against accidental
script injection in commit messages or pasted PR bodies.
"""

from __future__ import annotations

from markdown_it import MarkdownIt

__all__ = ["render_markdown"]

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False}).enable("linkify")


def render_markdown(body: str) -> str:
    return _md.render(body)
