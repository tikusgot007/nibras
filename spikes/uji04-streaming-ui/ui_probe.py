"""Uji #4 UI probe: one QMainWindow, one streaming QTextBrowser message card.

Real Qt event loop, real window (not offscreen). Measures:
  * 16 ms QTimer tick intervals (main-thread responsiveness histogram)
  * click -> visible response delta (QMouseEvents are POSTED to the event queue,
    so the delta includes any backlog on the main thread, like a human click)
  * per-render duration

Automation (no human operator): a QTimer scrolls the card up/down and another
posts clicks at random moments. Reports state this is automated, not manual.
"""
import argparse
import json
import os
import platform
import random
import sys
import time

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, TextLexer
from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTextBrowser, QVBoxLayout, QWidget

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_stream_sim import TokenStreamSimulator  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TICK_MS = 16
FORMATTER = HtmlFormatter(noclasses=True, nowrap=False, style="default")


def _highlight(code, lang, attrs):
    try:
        lexer = get_lexer_by_name(lang) if lang else TextLexer()
    except Exception:
        lexer = TextLexer()
    return highlight(code, lexer, FORMATTER)


MD = MarkdownIt("commonmark", {"highlight": _highlight}).enable("table")

CSS = ("<style>table{border-collapse:collapse}td,th{border:1px solid #888;padding:2px 4px}"
       "pre{background:#f4f4f4}</style>")


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1))))
    return sorted_vals[k]


def histogram(vals, edges):
    counts = [0] * (len(edges) + 1)
    for v in vals:
        i = 0
        while i < len(edges) and v >= edges[i]:
            i += 1
        counts[i] += 1
    labels = [f"<{edges[0]}"] + [f"{edges[i]}-{edges[i + 1]}" for i in range(len(edges) - 1)] + [f">={edges[-1]}"]
    return dict(zip(labels, counts))


class Probe(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowTitle("Uji04 probe")
        self.resize(900, 640)
        w = QWidget()
        lay = QVBoxLayout(w)
        self.card = QTextBrowser()
        self.card.setOpenLinks(False)
        self.button = QPushButton("klik uji")
        lay.addWidget(self.card)
        lay.addWidget(self.button)
        self.setCentralWidget(w)

        self.buffer = ""
        self.chunks = 0
        self.render_ms = []
        self.intervals = []
        self.click_deltas = []
        self._pending_clicks = []
        self._last_tick = None
        self._toggle = False
        self.rnd = random.Random(args.seed)
        self.t_stream_start = None
        self.t_stream_end = None

        self.button.clicked.connect(self.on_clicked)

        self.tick = QTimer(self)
        self.tick.setTimerType(Qt.PreciseTimer)
        self.tick.setInterval(TICK_MS)
        self.tick.timeout.connect(self.on_tick)

        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(250)
        self.scroll_timer.timeout.connect(self.auto_scroll)

        self.click_timer = QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.auto_click)

        if args.idle:
            self.sim = None
        else:
            text = open(os.path.join(HERE, "fixtures", args.fixture + ".md"), encoding="utf-8").read()
            self.sim = TokenStreamSimulator(text, rate=args.rate)
            self.sim.token.connect(self.on_token)   # queued: emitted from worker thread
            self.sim.finished.connect(self.on_finished)

    # ---- measurement -------------------------------------------------
    def on_tick(self):
        now = time.perf_counter()
        if self._last_tick is not None:
            self.intervals.append((now - self._last_tick) * 1000.0)
        self._last_tick = now

    def on_clicked(self):
        self._toggle = not self._toggle
        self.button.setStyleSheet("background:#2e9e44" if self._toggle else "background:#c0392b")
        self.button.repaint()  # synchronous paint = visible response
        t1 = time.perf_counter()
        if self._pending_clicks:
            t0 = self._pending_clicks.pop(0)
            self.click_deltas.append((t1 - t0) * 1000.0)

    def auto_click(self):
        pos = QPointF(self.button.width() / 2, self.button.height() / 2)
        dev = QPointingDevice.primaryPointingDevice()
        press = QMouseEvent(QEvent.MouseButtonPress, pos, self.button.mapToGlobal(pos), Qt.LeftButton,
                            Qt.LeftButton, Qt.NoModifier, dev)
        release = QMouseEvent(QEvent.MouseButtonRelease, pos, self.button.mapToGlobal(pos), Qt.LeftButton,
                              Qt.NoButton, Qt.NoModifier, dev)
        self._pending_clicks.append(time.perf_counter())
        QCoreApplication.postEvent(self.button, press)
        QCoreApplication.postEvent(self.button, release)
        self.click_timer.start(self.rnd.randint(700, 2200))

    def auto_scroll(self):
        sb = self.card.verticalScrollBar()
        sb.setValue(int(self.rnd.random() * max(1, sb.maximum())))

    # ---- rendering ---------------------------------------------------
    def render(self):
        t0 = time.perf_counter()
        sb = self.card.verticalScrollBar()
        keep = sb.value()
        self.card.setHtml(CSS + MD.render(self.buffer))
        sb.setValue(min(keep, sb.maximum()))
        self.render_ms.append((time.perf_counter() - t0) * 1000.0)

    def on_token(self, tok):
        if self.t_stream_start is None:
            self.t_stream_start = time.perf_counter()
        self.buffer += tok
        self.chunks += 1
        if self.args.mode == "full" or self.chunks % self.args.batch_n == 0:
            self.render()

    def on_finished(self):
        self.render()  # final render (both modes)
        self.t_stream_end = time.perf_counter()
        QTimer.singleShot(1500, self.finish)

    # ---- lifecycle ---------------------------------------------------
    def start(self):
        self.show()
        self.tick.start()
        self.scroll_timer.start()
        self.click_timer.start(900)
        if self.sim is None:
            QTimer.singleShot(int(self.args.idle_seconds * 1000), self.finish)
        else:
            QTimer.singleShot(500, self.sim.start)

    def finish(self):
        self.tick.stop()
        self.scroll_timer.stop()
        self.click_timer.stop()
        lag = sorted(max(0.0, v - TICK_MS) for v in self.intervals)
        ck = sorted(self.click_deltas)
        rd = sorted(self.render_ms)
        res = {
            "fixture": "idle" if self.args.idle else self.args.fixture,
            "mode": "idle" if self.args.idle else self.args.mode,
            "run": self.args.run,
            "rate_tok_per_s": self.args.rate,
            "batch_n": self.args.batch_n if self.args.mode == "batched" else None,
            "tokens": self.chunks,
            "stream_seconds": (self.t_stream_end - self.t_stream_start) if self.t_stream_end else None,
            "automation": "automatic (QTimer scroll every 250ms; posted QMouseEvent clicks at random 0.7-2.2s); not manual",
            "timer_samples": len(self.intervals),
            "timer_lag_ms": {"p50": pct(lag, 50), "p95": pct(lag, 95), "p99": pct(lag, 99), "max": lag[-1] if lag else None},
            "timer_lag_histogram_ms": histogram(lag, [1, 2, 5, 10, 20, 50, 100, 200, 500]),
            "click_count": len(ck),
            "click_delta_ms": {"p50": pct(ck, 50), "p95": pct(ck, 95), "max": ck[-1] if ck else None},
            "click_deltas_ms": [round(v, 2) for v in self.click_deltas],
            "render_count": len(rd),
            "render_ms": {"p50": pct(rd, 50), "p95": pct(rd, 95), "max": rd[-1] if rd else None, "total": sum(rd)},
            "env": {"python": platform.python_version(), "pyside6": QtCore.__version__ if hasattr(QtCore, "__version__") else None,
                    "qt": QtCore.qVersion(), "os": platform.platform()},
        }
        os.makedirs(os.path.dirname(os.path.abspath(self.args.out)), exist_ok=True)
        with open(self.args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        QApplication.quit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", choices=["plain", "code_heavy", "wide_mixed"], default="plain")
    ap.add_argument("--mode", choices=["full", "batched"], default="full")
    ap.add_argument("--batch-n", type=int, default=10)
    ap.add_argument("--rate", type=float, default=40.0, help="tokens per second")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--idle", action="store_true", help="baseline: no stream, only timer")
    ap.add_argument("--idle-seconds", type=float, default=10.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.seed is None:
        args.seed = args.run
    app = QApplication(sys.argv)
    p = Probe(args)
    p.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
