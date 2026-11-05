"""Local token stream simulator for Uji #4 (no real LLM).

The source runs in its own QThread and talks to the UI ONLY through Qt
signals (mirrors D-11). Pacing uses absolute deadlines so it does not drift.
"""
import re
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

_TOKEN_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]"  # CJK / kana / hangul: one char per token
    r"|\w+[ \t]*"                                  # word + trailing blanks
    r"|[^\w\s][ \t]*"                              # one punctuation mark + trailing blanks
    r"|\s+",                                       # newlines / runs of whitespace
    re.UNICODE,
)


def tokenize(text: str):
    """Simple tokenizer (no BPE): words, punctuation, CJK chars, whitespace."""
    return _TOKEN_RE.findall(text)


class _Worker(QObject):
    token = Signal(str)
    finished = Signal()

    def __init__(self, tokens, rate):
        super().__init__()
        self._tokens = tokens
        self._interval = 1.0 / rate
        self._stop = False

    @Slot()
    def run(self):
        start = time.perf_counter()
        for i, tok in enumerate(self._tokens):
            if self._stop:
                break
            delay = start + i * self._interval - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            self.token.emit(tok)  # queued connection -> delivered in the UI thread
        self.finished.emit()

    def stop(self):
        self._stop = True


class TokenStreamSimulator(QObject):
    """Facade: start() launches the producer thread; consume `token` / `finished`."""
    token = Signal(str)
    finished = Signal()

    def __init__(self, text: str, rate: float = 40.0, parent=None):
        super().__init__(parent)
        self.tokens = tokenize(text)
        self._thread = QThread()
        self._worker = _Worker(self.tokens, rate)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.token.connect(self.token)
        self._worker.finished.connect(self._on_done)

    def start(self):
        self._thread.start()

    @Slot()
    def _on_done(self):
        self._thread.quit()
        self._thread.wait()
        self.finished.emit()
