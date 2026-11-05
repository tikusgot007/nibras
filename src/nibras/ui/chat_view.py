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
        self.browser = QTextBrowser()
        self.browser.setReadOnly(True)
        self.browser.setOpenExternalLinks(False)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
        self.browser.setHtml(render_markdown(self._text))
        height = int(self.browser.document().size().height()) + 12
        self.browser.setFixedHeight(max(height, 40))


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
