"""Deterministic generator for the three ~5,000-token fixtures."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_stream_sim import tokenize  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = 5000


def ntok(s):
    return len(tokenize(s))


def build(blocks):
    out, n = [], 0
    for b in blocks:
        t = ntok(b)
        if n + t > TARGET + 100:
            break
        out.append(b)
        n += t
        if n >= TARGET:
            break
    return "".join(out), n


SUBJ = ["The assistant", "A portable workspace", "The launcher", "Each message card", "The local index",
        "A careful reader", "The scheduler", "The user", "Every connector", "The memory layer"]
VERB = ["collects", "summarizes", "validates", "renders", "stores", "compares", "retrieves", "updates"]
OBJ = ["the latest notes", "a short report", "several documents", "the pending tasks", "a long answer",
       "recent conversations", "the configuration", "a list of options"]
TAIL = ["before the next step begins.", "without blocking the interface.", "while keeping the data on the drive.",
        "and explains the result in plain words.", "so that nothing is lost on a crash.", "as soon as it is ready."]


def plain():
    rnd = random.Random(1)
    blocks = ["# Laporan Perjalanan Panjang\n\n"]
    i = 0
    while True:
        i += 1
        blocks.append(f"## Bagian {i}\n\n")
        for _ in range(3):
            sents = [f"{rnd.choice(SUBJ)} {rnd.choice(VERB)} {rnd.choice(OBJ)} {rnd.choice(TAIL)}" for _ in range(rnd.randint(4, 7))]
            blocks.append(" ".join(sents) + "\n\n")
        if i % 3 == 0:
            blocks.append("- " + "\n- ".join(f"{rnd.choice(SUBJ)} {rnd.choice(VERB)} {rnd.choice(OBJ)}." for _ in range(4)) + "\n\n")
        if len(blocks) > 400:
            break
    return build(blocks)


def code_block(lang, seed, lines=205):
    rnd = random.Random(seed)
    body = []
    for k in range(lines):
        r = k % 5
        if lang == "python":
            body.append(f"def fn_{k}(x):" if r == 0 else (f"v{k} = {rnd.randint(1, 99)}" if r < 3 else f"v{k} = f(a)"))
        else:
            body.append(f"function fn_{k}(x) {{" if r == 0 else (f"let v{k} = {rnd.randint(1, 99)};" if r < 3 else f"let v{k} = g(b);"))
    return f"```{lang}\n" + "\n".join(body) + "\n```\n\n"


def code_heavy():
    blocks = ["# Kumpulan Contoh Kode\n\n", "Berikut empat contoh panjang.\n\n"]
    for i, lang in enumerate(["python", "javascript", "python"]):
        blocks.append(f"## Contoh {i + 1}\n\n")
        rnd = random.Random(i)
        blocks.append(" ".join(f"{rnd.choice(SUBJ)} {rnd.choice(VERB)} {rnd.choice(OBJ)} {rnd.choice(TAIL)}" for _ in range(24)) + "\n\n")
        blocks.append(code_block(lang, i + 10, lines=205))
    return build(blocks)


CJK = ["今天的天气非常好，我们决定去公园散步，然后在湖边喝茶。", "这个系统可以在没有网络的情况下运行，所有的数据都保存在本地的存储设备上。",
       "日本語のテキストも正しく表示される必要があります。長い文章でも問題なく動作することを確認します。", "한국어 문장도 함께 표시되어야 하며 줄 바꿈이 올바르게 동작해야 합니다."]
ARB = ["هذا نص تجريبي طويل باللغة العربية لاختبار عرض الحروف المتصلة واتجاه الكتابة من اليمين إلى اليسار.",
       "يجب أن يعمل التطبيق بدون اتصال بالإنترنت وأن تبقى جميع البيانات على وحدة التخزين المحمولة.",
       "نختبر هنا قدرة الواجهة على عرض فقرات طويلة مختلطة مع كلمات لاتينية مثل Nibras و Qt و Markdown."]


def table(cols, rows, seed):
    rnd = random.Random(seed)
    hdr = [f"Kolom{c + 1}" for c in range(cols)]
    s = "| " + " | ".join(hdr) + " |\n|" + "|".join(["---"] * cols) + "|\n"
    for r in range(rows):
        s += "| " + " | ".join(rnd.choice(["alpha", "数据", "بيانات", str(rnd.randint(100, 9999)), "long-value-text", "データ"]) for _ in range(cols)) + " |\n"
    return s + "\n"


def wide_mixed():
    rnd = random.Random(3)
    blocks = ["# Dokumen Campuran Latin, CJK, dan Arab\n\n"]
    i = 0
    while len(blocks) < 300:
        i += 1
        blocks.append(f"## Bagian {i}\n\n")
        blocks.append(table(14, 6, i))
        blocks.append(" ".join(rnd.choice(CJK) for _ in range(3)) + "\n\n")
        blocks.append(" ".join(rnd.choice(ARB) for _ in range(3)) + "\n\n")
        blocks.append(f"Mixed paragraph {i}: Nibras mengirim 你好 dan مرحبا dalam satu kalimat sambil menjaga layout tetap rapi.\n\n")
    return build(blocks)


if __name__ == "__main__":
    for name, fn in [("plain", plain), ("code_heavy", code_heavy), ("wide_mixed", wide_mixed)]:
        text, n = fn()
        with open(os.path.join(HERE, "fixtures", f"{name}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(name, "tokens:", n, "chars:", len(text), "lines:", text.count("\n"))
