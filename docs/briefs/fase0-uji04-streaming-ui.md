# Brief Tugas — Fase 0, Uji #4: Streaming Respons Panjang di UI

**Proyek:** Nibras (asisten AI portabel yang berjalan dari USB di Windows)
**Untuk:** agen coding
**Referensi desain:** `docs/decisions.md` (D-11, D-16, D-50)
**Tingkat:** prototipe uji (spike). Ini **bukan** kode aplikasi.
**Dijalankan di:** PC Windows fisik (sesi Claude Code lokal operator), bukan sesi cloud — butuh PySide6/Qt dengan event loop GUI nyata.

---

## 1. Tujuan

D-11 menetapkan Agent Core berjalan di thread asyncio terpisah, berkomunikasi ke UI lewat Qt signals. D-16 dan D-50 menetapkan tiap pesan chat adalah widget kartu `QTextBrowser` tersendiri yang me-render Markdown. Uji ini memverifikasi bahwa pola ini tidak membuat UI macet ("freeze"/tidak responsif) saat menerima respons streaming sepanjang sekitar 5.000 token, termasuk kasus terburuk (code block panjang, tabel lebar, teks campuran Latin dan non-Latin).

Pertanyaan yang dijawab:
1. Apakah UI tetap responsif (bisa di-scroll, tombol bisa diklik) selama streaming 5.000 token berlangsung?
2. Berapa frekuensi update UI yang aman (tiap token? tiap N ms? tiap kalimat?) tanpa membuat main thread Qt kelebihan beban?
3. Apakah re-render Markdown lengkap pada tiap chunk (bukan hanya append) menjadi bottleneck pada pesan yang sudah panjang?
4. Bagaimana perilaku `QTextBrowser` dengan tabel lebar, code block panjang (>200 baris), dan teks non-Latin (CJK, Arab)?

## 2. Ruang Lingkup

**Termasuk:** program probe UI minimal (satu jendela, satu kartu pesan streaming), generator teks uji (bukan LLM sungguhan — simulasi token demi token dari teks statis), pengukur responsivitas, panduan prosedur.

**Tidak termasuk:** Agent Core sungguhan, provider LLM sungguhan (lihat bagian 5 — streaming disimulasikan lokal), Memory Inbox, fitur lain di luar satu kartu chat yang menerima stream.

## 3. Keputusan Desain yang WAJIB Diikuti

| Aturan | Nilai |
|---|---|
| Rendering teks chat | `QTextBrowser`, Markdown → HTML dengan `markdown-it-py`, syntax highlighting dengan `Pygments` (D-16) |
| Struktur pesan | Satu `QTextBrowser` per kartu pesan, bukan satu `QTextBrowser` untuk seluruh riwayat chat (D-50) |
| Threading | Sumber stream (simulasi LLM) berjalan di thread/task terpisah dari UI thread, kirim data ke UI lewat Qt signal (meniru D-11), **bukan** langsung memanggil widget dari thread lain |

## 4. Larangan (Jangan Dilakukan)

- ❌ Jangan memanggil method widget Qt langsung dari thread non-UI (wajib lewat signal/slot).
- ❌ Jangan memakai provider LLM sungguhan (biaya, dan hasil harus reproducible) — gunakan simulator token lokal (bagian 5).
- ❌ Jangan "mengakali" responsivitas dengan menunda keseluruhan render sampai stream selesai — tujuan uji ini justru progressive rendering.
- ❌ Jangan mengarang angka freeze/responsivitas. Ukur dengan event loop timer nyata (bagian 6).

## 5. Spesifikasi Simulator Stream

Buat `token_stream_sim.py`: generator yang menghasilkan teks dari file sumber statis (siapkan 3 file sumber di `fixtures/`, lihat bagian 6), dipecah per token (gunakan tokenizer sederhana, misalnya split spasi + tanda baca, tidak perlu BPE sungguhan), dan di-"stream" dengan jeda antar-token yang dapat diatur (default meniru kecepatan LLM nyata, misalnya 20–40 token/detik) lewat `QTimer` atau `asyncio` + Qt signal.

## 6. Spesifikasi Probe UI

Program `ui_probe.py`: satu `QMainWindow`, berisi satu kartu pesan (`QTextBrowser`) yang menerima stream dari bagian 5, plus:
- **Timer responsivitas:** `QTimer` dengan interval 16 ms (~60 fps) yang menghitung keterlambatan tiap tick dibanding interval seharusnya. Jeda yang jauh dari 16 ms menandakan main thread sempat blocked. Catat histogram jeda ini selama seluruh durasi stream.
- **Tombol uji interaktif:** satu tombol yang, kalau diklik operator selama streaming berlangsung, mencatat timestamp klik vs timestamp respons (perubahan warna tombol). Delta ini adalah ukuran "macet" yang dirasakan manusia.
- Mode re-render: dukung dua mode yang bisa dibandingkan — (a) re-render HTML penuh tiap chunk diterima, (b) append teks mentah lalu re-render Markdown hanya setiap N chunk atau tiap jeda tertentu. Catat perbedaan performanya.

**Fixture sumber** (`fixtures/`), tiga skenario:
1. `plain.md` — teks naratif biasa (~5.000 token), campuran paragraf dan beberapa heading.
2. `code_heavy.md` — berisi beberapa code block panjang (>200 baris tiap satu), total ~5.000 token.
3. `wide_mixed.md` — berisi tabel Markdown lebar (banyak kolom) dan teks campuran Latin, CJK, dan Arab, total ~5.000 token.

## 7. Prosedur Uji (oleh operator manusia)

Untuk tiap fixture di bagian 6, dan untuk kedua mode re-render:
1. Jalankan `ui_probe.py` dengan fixture tersebut.
2. Mulai stream, lalu selama berlangsung: scroll kartu pesan naik-turun, klik tombol uji beberapa kali di waktu acak.
3. Catat histogram jeda timer, delta klik-respons, dan kesan subjektif operator (macet terasa/tidak).
4. Ulangi tiap kombinasi 3 kali.

## 8. Kriteria Lulus

| Kriteria | Target | Sifat |
|---|---|---|
| UI tidak macet (kriteria Fase 0, `decisions.md` bagian 10) | p95 jeda timer responsivitas < 100 ms, delta klik-respons < 150 ms, di semua fixture dan mode | **Wajib** |
| Mode re-render mana yang lebih aman | Dilaporkan sebagai rekomendasi, bukan syarat lulus | Informasi |

Jika kriteria wajib gagal pada mode re-render tertentu tapi lulus pada mode lain, laporkan keduanya — jangan hanya melaporkan mode yang lulus.

## 9. Deliverable

```
spikes/uji04-streaming-ui/
├── token_stream_sim.py
├── ui_probe.py
├── fixtures/
│   ├── plain.md
│   ├── code_heavy.md
│   └── wide_mixed.md
└── README.md
results/
└── uji04-streaming-ui.md
```

Isi `results/uji04-streaming-ui.md`:
1. **Lingkungan:** OS, CPU, RAM, versi PySide6/Qt.
2. **Tabel hasil** per fixture × mode: p95/p99 jeda timer, delta klik-respons, kesan subjektif.
3. **Rekomendasi** frekuensi update dan mode re-render untuk implementasi produksi.
4. **Catatan khusus** `wide_mixed.md` (tabel lebar, non-Latin) dan `code_heavy.md` (syntax highlighting panjang).

## 10. Definisi Selesai

- Semua kombinasi fixture × mode di bagian 7 benar-benar dijalankan dengan event loop Qt nyata (bukan headless/mock).
- Laporan berisi data nyata dari pengukuran timer, bukan perkiraan.
- Kode dikerjakan di branch `fase0/uji04`, lalu dibuka pull request ke `main`.
