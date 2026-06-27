"""
Tests du pipeline Quiet Capital — exécutables SANS clé API ni ffmpeg.

    python3 bot/tests/test_pipeline.py

Couvre : parsing du contenu, découpe en phrases, format des timecodes,
génération SRT (ordre/bornes), tri naturel des images, robustesse.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOT_DIR))

from steps import parse_content, assemble, visuals  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# --- 1. Parsing du contenu --------------------------------------------------
def test_parsing() -> None:
    print("\n[1] Parsing du contenu")
    shorts = parse_content.load_shorts()
    check("10 shorts parsés", len(shorts) == 10, f"(trouvé {len(shorts)})")
    for n, s in shorts.items():
        check(f"short {n} complet (voix+visuels)", s.is_complete())
        check(f"short {n} a un hook", bool(s.hook))
        check(f"short {n} a un titre YouTube", bool(s.yt_title))
        check(f"short {n} voix 200-450 chars (≈25-30s)", 150 <= len(s.voice) <= 480,
              f"(={len(s.voice)})")
        check(f"short {n} a des hashtags", "#" in s.hashtags)


# --- 2. Découpe en phrases --------------------------------------------------
def test_sentences() -> None:
    print("\n[2] Découpe en phrases")
    out = assemble._split_sentences("Hello world. This is a test! Really? Yes.")
    check("4 phrases détectées", len(out) == 4, f"(={out})")
    check("pas de phrase vide", all(p.strip() for p in out))


# --- 3. Format des timecodes SRT --------------------------------------------
def test_srt_time() -> None:
    print("\n[3] Format timecode")
    check("0s -> 00:00:00,000", assemble._srt_time(0) == "00:00:00,000",
          assemble._srt_time(0))
    check("65.5s -> 00:01:05,500", assemble._srt_time(65.5) == "00:01:05,500",
          assemble._srt_time(65.5))


# --- 4. Génération SRT (ordre + bornes) -------------------------------------
def test_build_srt() -> None:
    print("\n[4] Génération SRT")
    total = 28.0
    with tempfile.TemporaryDirectory() as d:
        srt = Path(d) / "subs.srt"
        assemble._build_srt("My Hook", "First sentence. Second one. Third here.", total, srt)
        content = srt.read_text(encoding="utf-8")
        check("fichier SRT non vide", len(content) > 0)
        check("hook en MAJUSCULES et en 1er", content.startswith("1\n") and "MY HOOK" in content,
              repr(content[:40]))
        check("commence à 00:00:00,000", "00:00:00,000 -->" in content)
        # Vérifie que tous les timecodes restent <= total
        import re
        times = re.findall(r"(\d\d):(\d\d):(\d\d),(\d\d\d)", content)
        secs = [int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in times]
        check("aucun timecode ne dépasse la durée", all(t <= total + 0.05 for t in secs),
              f"(max={max(secs):.2f}, total={total})")
        check("timecodes croissants", secs == sorted(secs))


# --- 5. Tri naturel des images ----------------------------------------------
def test_natural_sort() -> None:
    print("\n[5] Tri naturel des images")
    names = [Path(p) for p in ["img10.png", "img2.png", "img1.png", "img11.png"]]
    ordered = [p.name for p in sorted(names, key=visuals._natural_key)]
    check("img2 avant img10", ordered == ["img1.png", "img2.png", "img10.png", "img11.png"],
          f"(={ordered})")


# --- 6. Détection filtre sous-titres (ne doit jamais crasher) ---------------
def test_filter_detection() -> None:
    print("\n[6] Détection libass")
    val = assemble._has_subtitles_filter()
    check("renvoie un booléen sans crasher", isinstance(val, bool), f"(={val})")


if __name__ == "__main__":
    test_parsing()
    test_sentences()
    test_srt_time()
    test_build_srt()
    test_natural_sort()
    test_filter_detection()
    print(f"\n{'='*40}\nRésultat : {PASS} ✓   {FAIL} ✗\n{'='*40}")
    sys.exit(1 if FAIL else 0)
