from __future__ import annotations

from aegis.web.render import render_markdown


def test_render_basic_markdown() -> None:
    html = render_markdown("# Title\n\nHello **world**.")
    assert "<h1>" in html
    assert "Title" in html
    assert "<strong>world</strong>" in html


def test_render_escapes_raw_html_by_default() -> None:
    html = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_supports_fenced_code() -> None:
    html = render_markdown("```python\nprint('hi')\n```")
    assert "<pre>" in html
    assert "print" in html


def test_render_linkifies_bare_url() -> None:
    html = render_markdown("visit https://example.com for info")
    assert '<a href="https://example.com">' in html
