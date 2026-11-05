"""Markdown -> HTML for the chat view (D-16, D-57).

Markdown is converted with ``markdown-it-py``; code blocks are
highlighted with Pygments (inline styles, which QTextBrowser supports).
Rendering is batched: callers re-render at most every 10 tokens plus a
final render, never per token.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from pygments import highlight as _pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

_FORMATTER = HtmlFormatter(style="monokai", noclasses=True)


def _highlight(code: str, lang: str, _attrs: str) -> str:
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        lexer = guess_lexer(code) if code.strip() else None
    if lexer is None:
        return f"<pre><code>{code}</code></pre>"
    return _pyg_highlight(code, lexer, _FORMATTER)


_MD = MarkdownIt("commonmark", {"highlight": _highlight}).enable("table")


def render_markdown(text: str) -> str:
    """Render Markdown to an HTML fragment for QTextBrowser."""
    return _MD.render(text or "")
