"""Chat view: one card widget per message (D-50), batched rendering (D-57).

Each message is a ``QFrame`` card containing a ``QTextBrowser`` with the
Markdown rendered inside it. While streaming, the assistant card is
re-rendered at most every 10 new tokens plus once at the end (D-57),
never per token.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.messages import estimate_tokens
from .markdown import render_markdown

RENDER_EVERY_TOKENS = 10


class AutoHeightBrowser(QTextBrowser):
    """QTextBrowser whose height always matches its laid-out document.

    The height can only be known after the document is wrapped to the real
    viewport width. Computing it right after ``setHtml`` (before the widget
    has its final width) gave cards that were far too short, so only a line
    or two of a long answer was visible. The height is therefore refitted
    after every ``setHtml`` and on every width change.
    """

    MIN_HEIGHT = 40

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(self.MIN_HEIGHT)

    def setHtml(self, html: str) -> None:  # noqa: N802 - Qt naming
        super().setHtml(html)
        self._fit_height()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)  # lets Qt wrap the document to the new width
        self._fit_height()

    def _fit_height(self) -> None:
        doc = self.document()
        if self.viewport().width() > 0:
            doc.setTextWidth(self.viewport().width())
        height = int(doc.size().height()) + 2 * self.frameWidth() + 8
        height = max(height, self.MIN_HEIGHT)
        if height != self.height():
            self.setFixedHeight(height)
            self.verticalScrollBar().setValue(0)


class MessageCard(QFrame):
    def __init__(self, role: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.role = role
        self.setObjectName(
            "messageCardUser" if role == "user" else "messageCard"
        )
        self._text = ""
        self._tokens_since_render = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        who = QLabel("Kamu" if role == "user" else "Nibras")
        who.setObjectName("muted")
        layout.addWidget(who)
        self.browser = AutoHeightBrowser()
        layout.addWidget(self.browser)
        self._status = QLabel("")
        self._status.setObjectName("muted")
        layout.addWidget(self._status)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self._render()

    def append_delta(self, delta: str) -> bool:
        """Append streamed text. Returns True when a re-render happened."""
        self._text += delta
        self._tokens_since_render += estimate_tokens(delta)
        if self._tokens_since_render >= RENDER_EVERY_TOKENS:
            self._tokens_since_render = 0
            self._render()
            return True
        return False

    def finish(self, status: str = "") -> None:
        self._render()
        if status:
            self._status.setText(status)

    def set_status(self, status: str) -> None:
        self._status.setText(status)

    def _render(self) -> None:
        self.browser.setHtml(render_markdown(self._text))  # also refits the height


class ChatView(QScrollArea):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setAlignment(Qt.AlignTop)
        self._layout.addStretch(1)
        self.setWidget(self._inner)
        self._cards: dict[str, MessageCard] = {}

    def clear(self) -> None:
        for card in list(self._cards.values()):
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def add_message(self, message_id: str, role: str, content: str) -> MessageCard:
        card = MessageCard(role)
        card.set_text(content)
        self._layout.insertWidget(self._layout.count() - 1, card)
        self._cards[message_id] = card
        self._scroll_to_bottom()
        return card

    def card(self, message_id: str) -> MessageCard | None:
        return self._cards.get(message_id)

    def _scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
