"""Build dataset/queries_v2.json (natural queries, Uji #6b Tahap 1).

One-off generator kept for provenance, mirroring build_dataset.py's style.
Data is written by hand below (not derived from Uji #6 failure results, per
brief section 3). Standard library only.

Validates:
- every relevant_id exists in corpus.json
- for the four cross-lingual types (id-id, en-en, id-en, en-id), every
  relevant entry's `lang` matches the type's expected query/answer language
  (this is the "clean type" convention used by v1's build_dataset.py).
  informal/typo carry no such constraint, matching v1.
- counts match the required distribution (id-id 40, en-en 30, id-en 30,
  en-id 30, informal 40, typo 30).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# (type, query, relevant_ids) -- relevant_ids: list[str]
DATA = [
    # ---------------- id-id (40): query ID, answer entries lang=="id" ----------------
    ("id-id", "Dimas minum kopinya kayak gimana?", ["g01a"]),
    ("id-id", "Istri Dimas suka minum kopi apa?", ["g01b"]),
    ("id-id", "Dimas berhenti ngopi jam berapa?", ["g01c"]),
    ("id-id", "Aira sekolah di mana?", ["g03a"]),
    ("id-id", "Siapa yang nganterin Aira ke sekolah?", ["g03b"]),
    ("id-id", "Les piano Aira jadwalnya kapan?", ["g03c"]),
    ("id-id", "Mobil Brio diservis di bengkel mana?", ["g04c"]),
    ("id-id", "Dimas pakai tema apa di editornya?", ["g05c"]),
    ("id-id", "Frontend internal pakai framework apa?", ["g06c"]),
    ("id-id", "Deploy toko ke server produksi hari apa?", ["g07b"]),
    ("id-id", "Standup tim jam berapa?", ["g08a"]),
    ("id-id", "Review mingguan sama klien kapan?", ["g08b"]),
    ("id-id", "Dimas alergi makanan apa?", ["g09a"]),
    ("id-id", "Sari nggak boleh makan apa karena alergi?", ["g09b"]),
    ("id-id", "Sari biasanya tidur jam berapa?", ["g10b"]),
    ("id-id", "HP lama Dimas sekarang dipakai siapa?", ["g11b"]),
    ("id-id", "Laptop Aira itu laptop apa?", ["g12b"]),
    ("id-id", "Foto keluarga di-backup kapan?", ["g13a"]),
    ("id-id", "Database produksi di-backup jam berapa?", ["g13c"]),
    ("id-id", "Dimas dengerin musik apa waktu coding?", ["g14a"]),
    ("id-id", "Dulu pernah jalan-jalan sama keluarga ke kota apa?", ["g15a"]),
    ("id-id", "Dimas mancing di mana?", ["g16b"]),
    ("id-id", "Gaji Dimas masuk tanggal berapa?", ["g17a"]),
    ("id-id", "Klien kedua Dimas namanya apa?", ["g18b"]),
    ("id-id", "Batas waktu setor pajak tahunan sampai kapan?", ["g19a"]),
    ("id-id", "Dokumentasi proyek ditulis bahasa apa?", ["g20b"]),
    ("id-id", "Rebase boleh nggak di branch bersama?", ["g21c"]),
    ("id-id", "Database buat development pakai apa?", ["g22b"]),
    ("id-id", "Domain dibeli di mana?", ["g23b"]),
    ("id-id", "Makanan favorit Dimas apa?", ["g24a"]),
    ("id-id", "Dokter keluarga Dimas siapa?", ["g27a"]),
    ("id-id", "Rumah Dimas ada di mana?", ["g28a"]),
    ("id-id", "Sari lagi baca novel apa?", ["g30b"]),
    ("id-id", "Password boleh disimpan di catatan teks nggak?", ["g35b"]),
    ("id-id", "Dimas pakai sepatu nomor berapa?", ["g38a"]),
    ("id-id", "Ulang tahun Dimas tanggal berapa?", ["g39a"]),
    ("id-id", "Dimas salat Jumat di mana?", ["g43a"]),
    ("id-id", "Pas hujan gede begini Dimas ngerjain tugas kantor di mana?", ["g44b"]),
    ("id-id", "Dimas mau belajar apa tahun ini?", ["g51a"]),
    ("id-id", "Dimas kuliah di mana?", ["s083"]),

    # ---------------- en-en (30): query EN, answer entries lang=="en" ----------------
    ("en-en", "What breed is the user's cat?", ["g02a"]),
    ("en-en", "What car does the user drive?", ["g04a"]),
    ("en-en", "What car does Sari drive?", ["g04b"]),
    ("en-en", "Which code editor does the user use?", ["g05a"]),
    ("en-en", "What editor is used for quick server edits?", ["g05b"]),
    ("en-en", "What is the main backend language?", ["g06a"]),
    ("en-en", "What triggers a new deploy of the billing service?", ["g07c"]),
    ("en-en", "When are meetings avoided for deep work?", ["g08c"]),
    ("en-en", "What does Aira drink since she is lactose intolerant?", ["g09c"]),
    ("en-en", "What time does the user usually wake up?", ["g10a"]),
    ("en-en", "What phone does the user have?", ["g11a"]),
    ("en-en", "What laptop is used for work?", ["g12a"]),
    ("en-en", "What graphics card does the home desktop have?", ["g12c"]),
    ("en-en", "Where is the project code mirrored?", ["g13b"]),
    ("en-en", "Where does the user play badminton?", ["g16a"]),
    ("en-en", "What is the monthly savings target?", ["g17b"]),
    ("en-en", "What project is being built for the main client?", ["g18a"]),
    ("en-en", "What tax rate does the freelancer pay?", ["g19b"]),
    ("en-en", "How does the user prefer answers formatted?", ["g20a"]),
    ("en-en", "How many approvals does a pull request need?", ["g21b"]),
    ("en-en", "What database runs in production?", ["g22a"]),
    ("en-en", "Which VPS provider is used?", ["g23a"]),
    ("en-en", "How are SSL certificates renewed?", ["g23c"]),
    ("en-en", "What is Aira's favorite snack?", ["g24c"]),
    ("en-en", "Where does the family have dinner once a month?", ["g25b"]),
    ("en-en", "What supplement does Sari take every morning?", ["g26b"]),
    ("en-en", "How often are dentist checkups scheduled?", ["g27b"]),
    ("en-en", "What brand are the smart lights?", ["g29a"]),
    ("en-en", "What book is currently being read?", ["g30a"]),
    ("en-en", "What language is the user learning on Duolingo?", ["g32a", "s216"]),

    # ---------------- id-en (30): query ID, answer entries lang=="en" ----------------
    ("id-en", "Apa ras kucing milik pengguna?", ["g02a"]),
    ("id-en", "Mobil apa yang dipakai pengguna?", ["g04a"]),
    ("id-en", "Mobil apa yang dikendarai Sari?", ["g04b"]),
    ("id-en", "Editor kode apa yang dipakai pengguna?", ["g05a"]),
    ("id-en", "Untuk edit cepat di server, pengguna pakai apa?", ["g05b"]),
    ("id-en", "Bahasa backend utama apa?", ["g06a"]),
    ("id-en", "Kapan staging billing service deploy otomatis?", ["g07c"]),
    ("id-en", "Jam berapa saja hindari meeting untuk fokus kerja?", ["g08c"]),
    ("id-en", "Aira minum apa karena nggak toleran laktosa?", ["g09c"]),
    ("id-en", "Pengguna biasanya bangun jam berapa?", ["g10a"]),
    ("id-en", "HP pengguna apa?", ["g11a"]),
    ("id-en", "Laptop kerja pengguna apa?", ["g12a"]),
    ("id-en", "GPU di desktop rumah apa?", ["g12c"]),
    ("id-en", "Kode proyek di-mirror di mana?", ["g13b"]),
    ("id-en", "Pengguna main bulutangkis di mana?", ["g16a"]),
    ("id-en", "Berapa persen target nabung bulanan?", ["g17b"]),
    ("id-en", "Proyek apa yang dikerjakan untuk klien utama?", ["g18a"]),
    ("id-en", "Berapa pajak final yang dibayar freelancer?", ["g19b"]),
    ("id-en", "Pengguna suka jawaban dalam format apa?", ["g20a"]),
    ("id-en", "Berapa approval minimal buat merge PR?", ["g21b"]),
    ("id-en", "Database produksi pakai apa?", ["g22a"]),
    ("id-en", "Penyedia VPS yang dipakai apa?", ["g23a"]),
    ("id-en", "Gimana cara sertifikat SSL diperpanjang?", ["g23c"]),
    ("id-en", "Camilan favorit Aira apa?", ["g24c"]),
    ("id-en", "Makan malam keluarga sebulan sekali di mana?", ["g25b"]),
    ("id-en", "Suplemen apa yang diminum Sari setiap pagi?", ["g26b"]),
    ("id-en", "Berapa sering cek gigi ke dokter?", ["g27b"]),
    ("id-en", "Lampu pintar di rumah merek apa?", ["g29a"]),
    ("id-en", "Buku apa yang sedang dibaca sekarang?", ["g30a"]),
    ("id-en", "Bahasa apa yang sedang dipelajari pengguna lewat Duolingo?", ["g32a", "s216"]),

    # ---------------- en-id (30): query EN, answer entries lang=="id" ----------------
    ("en-id", "How does Dimas take his coffee?", ["g01a"]),
    ("en-id", "What coffee does Dimas's wife like?", ["g01b"]),
    ("en-id", "Why did Dimas stop drinking coffee after 3pm?", ["g01c"]),
    ("en-id", "What school does Aira attend?", ["g03a"]),
    ("en-id", "Who takes Aira to school in the morning?", ["g03b"]),
    ("en-id", "When is Aira's piano lesson?", ["g03c"]),
    ("en-id", "Where does the Brio get serviced?", ["g04c"]),
    ("en-id", "What editor theme does Dimas use?", ["g05c"]),
    ("en-id", "What frontend framework does the team use?", ["g06c"]),
    ("en-id", "What day are production deploys for the shop app?", ["g07b"]),
    ("en-id", "What time is the daily standup?", ["g08a"]),
    ("en-id", "When is the weekly client review?", ["g08b"]),
    ("en-id", "What food must Dimas avoid?", ["g09a"]),
    ("en-id", "What is Sari allergic to?", ["g09b"]),
    ("en-id", "What time does Sari usually sleep?", ["g10b"]),
    ("en-id", "Who uses Dimas's old phone now?", ["g11b"]),
    ("en-id", "What laptop does Aira use?", ["g12b"]),
    ("en-id", "When is the family photo backup done?", ["g13a"]),
    ("en-id", "When is the production database backed up?", ["g13c"]),
    ("en-id", "What music does Dimas listen to while coding?", ["g14a"]),
    ("en-id", "Where did the family go on vacation last year?", ["g15a"]),
    ("en-id", "Where does Dimas go fishing?", ["g16b"]),
    ("en-id", "What day does the salary arrive?", ["g17a"]),
    ("en-id", "Who is the second client?", ["g18b"]),
    ("en-id", "What is the deadline for the annual tax report?", ["g19a"]),
    ("en-id", "What language is used for project documentation?", ["g20b"]),
    ("en-id", "Is rebasing allowed on shared branches?", ["g21c"]),
    ("en-id", "What database is used for local development?", ["g22b"]),
    ("en-id", "Where was the domain purchased?", ["g23b"]),
    ("en-id", "What is Dimas's favorite food?", ["g24a"]),

    # ---------------- informal (40): casual register, any lang target ----------------
    ("informal", "gw pake editor apa ya", ["g05a", "g05c"]),
    ("informal", "istri gw demen ngopi apa", ["g01b"]),
    ("informal", "kenapa gw stop ngopi sore-sore", ["g01c"]),
    ("informal", "kucing gw jenis apa sih", ["g02a"]),
    ("informal", "mobil gw merek apa", ["g04a"]),
    ("informal", "editor buat edit cepet di server gw pake apa", ["g05b"]),
    ("informal", "bahasa backend gw apaan", ["g06a"]),
    ("informal", "kalo bikin script cepet gw pake bahasa apa", ["g06b"]),
    ("informal", "frontend internal gw pake apa", ["g06c"]),
    ("informal", "gw lg ngerjain proyek apa buat klien utama", ["g18a"]),
    ("informal", "jam brp standup gw", ["g08a"]),
    ("informal", "gw ga boleh makan apa", ["g09a"]),
    ("informal", "sari alergi apa ya", ["g09b"]),
    ("informal", "jam brp biasanya gw bangun", ["g10a"]),
    ("informal", "hp gw apaan", ["g11a"]),
    ("informal", "laptop kerja gw apa", ["g12a"]),
    ("informal", "spek desktop rumah gw gmn", ["g12c"]),
    ("informal", "foto keluarga gw di-backup kemana", ["g13a"]),
    ("informal", "gw main bulutangkis dimana", ["g16a"]),
    ("informal", "berapa persen target nabung gw tiap bulan", ["g17b"]),
    ("informal", "klien kedua gw siapa", ["g18b"]),
    ("informal", "deadline lapor pajak gw kapan", ["g19a"]),
    ("informal", "dokumentasi proyek gw pake bahasa apa", ["g20b"]),
    ("informal", "boleh ga rebase di branch bareng", ["g21c"]),
    ("informal", "db produksi gw pake apa", ["g22a"]),
    ("informal", "db buat development gw pake apa", ["g22b"]),
    ("informal", "vps gw di provider mana", ["g23a"]),
    ("informal", "domain gw beli dimana", ["g23b"]),
    ("informal", "makanan favorit gw apa", ["g24a"]),
    ("informal", "camilan favorit aira apaan", ["g24c"]),
    ("informal", "dokter keluarga gw siapa", ["g27a"]),
    ("informal", "berapa kali setahun cek gigi", ["g27b"]),
    ("informal", "lampu pintar rumah merek apa", ["g29a"]),
    ("informal", "buku apa yang gw lg baca", ["g30a"]),
    ("informal", "novel apa yang sari lg baca", ["g30b"]),
    ("informal", "gw belajar bahasa apa pake duolingo", ["g32a", "s216"]),
    ("informal", "laporan mingguan ke klien gw kirim kapan", ["s066"]),
    ("informal", "progress belajar dimas taun ini soal rust & k8s gimana", ["g51a", "s268", "s269"]),
    ("informal", "guru piano aira siapa namanya", ["s281"]),
    ("informal", "siapa yang jemput aira kalo sari rapat guru", ["s283"]),

    # ---------------- typo (30): natural typing mistakes, any lang target ----------------
    ("typo", "Dimas minum kopinya kayak gmn ya", ["g01a"]),
    ("typo", "Kapan les pinao Aira", ["g03c"]),
    ("typo", "Jam brapa standpu tim?", ["g08a"]),
    ("typo", "Kapan revew mingguan ama klien?", ["g08b"]),
    ("typo", "Dimas alergy apa?", ["g09a"]),
    ("typo", "Sari alergi apaan ya, kcang?", ["g09b"]),
    ("typo", "Jam brapa Sari biasa tdur?", ["g10b"]),
    ("typo", "Hp lama Dimas skrng dipake sapa?", ["g11b"]),
    ("typo", "Laptop Aira itu laptop apaan?", ["g12b"]),
    ("typo", "Kapan backup photo keluarga dilakuin?", ["g13a"]),
    ("typo", "Database produski di-backup jam brp?", ["g13c"]),
    ("typo", "Musik apa yg didengerin Dimas pas ngoding?", ["g14a", "s250"]),
    ("typo", "Liburan kluarga taun lalu kemana?", ["g15a"]),
    ("typo", "Dimas mancingnya dimna?", ["g16b"]),
    ("typo", "Gajian tanggal brapa?", ["g17a"]),
    ("typo", "Klien kedua namnya apa?", ["g18b"]),
    ("typo", "Kapan deadline lapor pajek tahunan?", ["g19a"]),
    ("typo", "Dokumentasi proyek pake bhsa apa?", ["g20b"]),
    ("typo", "Rebase boleh ga di branch bersma?", ["g21c"]),
    ("typo", "Db development pake apaan?", ["g22b"]),
    ("typo", "Domain dibeli dmna?", ["g23b"]),
    ("typo", "Makanan favorit Dimas apaa?", ["g24a"]),
    ("typo", "Nomor sepatu dimas brapa, yg buat lari jg sama ga?", ["g38a", "s316"]),
    ("typo", "Gw suka dijawab kyk gmn sih, maunya yang gmn?", ["g20a", "g45a"]),
    ("typo", "Brapa sring cek gigi ke dokter?", ["g27b"]),
    ("typo", "Lampu pintar di rumah merek apaan?", ["g29a"]),
    ("typo", "Buku apa yg sdg dibaca Sari?", ["g30b"]),
    ("typo", "Bahasa apa yg dipelajari pake duolingo?", ["g32a", "s216"]),
    ("typo", "Laporan minggun ke klien dikirim kpn?", ["s066"]),
    ("typo", "Target blajar Dimas taun ini apa?", ["g51a"]),
]

EXPECTED_COUNTS = {
    "id-id": 40, "en-en": 30, "id-en": 30, "en-id": 30, "informal": 40, "typo": 30,
}
TYPE_LANG = {"id-id": "id", "en-en": "en", "id-en": "en", "en-id": "id"}

STOP = set("""
yang dan di ke dari untuk dengan pada ini itu atau juga akan sudah belum tidak bukan ada adalah
apa siapa kapan mana berapa bagaimana kenapa mengapa saya aku dia kami kita mereka nya sih ya yak
the and for are was were with that this what when where which who how does did his her its their
from into has have had not but you your user users dimas sari aira
dgn utk yg gw gue lu lo ga gak tdk dmn brp kpn gmn
""".split())


def tokens(text: str):
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOP}


def main():
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf8"))
    by_id = {e["id"]: e for e in corpus}

    assert len(DATA) == 200, f"expected 200 queries, got {len(DATA)}"
    counts = Counter(t for t, _, _ in DATA)
    assert counts == Counter(EXPECTED_COUNTS), f"type distribution mismatch: {counts}"

    queries = []
    errors = []
    for n, (typ, q, rel) in enumerate(DATA, 1):
        qid = f"qv2{n:03d}"
        for r in rel:
            if r not in by_id:
                errors.append(f"{qid}: unknown id {r}")
        if typ in TYPE_LANG:
            want = TYPE_LANG[typ]
            for r in rel:
                if r in by_id and by_id[r]["lang"] != want:
                    errors.append(f"{qid} ({typ}): {r} has lang={by_id[r]['lang']}, expected {want}")
        queries.append({"id": qid, "query": q, "type": typ, "relevant_ids": rel})

    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(f"{len(errors)} validation error(s)")

    out = HERE / "queries_v2.json"
    out.write_text(json.dumps(queries, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"wrote {len(queries)} queries to {out}")
    print("by type:", dict(counts))
    multi = sum(1 for q in queries if len(q["relevant_ids"]) > 1)
    print("multi-label:", multi)


if __name__ == "__main__":
    main()
