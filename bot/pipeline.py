#!/usr/bin/env python3
"""
Quiet Capital — pipeline de production faceless.

Transforme un script (déjà écrit dans ../content/) en vidéo Short prête à publier :
    script  ->  voix (ElevenLabs)  ->  visuels (Grok/manuel)  ->  montage (ffmpeg)  ->  MP4 + métadonnées

USAGE
    python bot/pipeline.py list                 # liste les 10 Shorts
    python bot/pipeline.py make 1               # produit le Short #1
    python bot/pipeline.py make 1 2 3           # produit plusieurs
    python bot/pipeline.py make all             # produit les 10
    python bot/pipeline.py make 1 --upload      # produit ET met en ligne (privé) — désactivé par défaut

Chaque vidéo finie atterrit dans bot/output/short<N>/ avec un fichier
metadata.txt (titre + description + hashtags) à copier-coller au moment de publier.

⚠️ Garde le contrôle humain : revois chaque MP4 ~30s avant publication
(politique YouTube 2026 sur le contenu "inauthentique").
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# Charge bot/.env si python-dotenv est présent (sinon variables d'env système).
BOT_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BOT_DIR / ".env")
except ImportError:
    pass

sys.path.insert(0, str(BOT_DIR))
from steps import parse_content, parse_longform, voiceover, visuals, assemble  # noqa: E402

OUTPUT_DIR = BOT_DIR / "output"
WORK_DIR = BOT_DIR / ".work"
ASSETS_DIR = BOT_DIR / "assets"
MUSIC = ASSETS_DIR / "music.mp3"
LINKS_FILE = BOT_DIR / "links.txt"  # bloc monétisation (affiliation) ajouté aux descriptions


def cmd_list() -> None:
    shorts = parse_content.load_shorts()
    print(f"\n{len(shorts)} SHORTS (9:16) :\n")
    for n, s in shorts.items():
        flag = "✅" if s.is_complete() else "⚠️ "
        print(f"  {flag} {n:>2}. {s.title}")
    longs = parse_longform.load_all()
    print(f"\n{len(longs)} LONG-FORM (16:9, le revenu) :\n")
    for n, lf in longs.items():
        flag = "✅" if lf.is_complete() else "⚠️ "
        print(f"  {flag} {n:>2}. {lf.title}")
    print("\nShort :     ./bot/run.sh make 1")
    print("Long-form : ./bot/run.sh make-long 1\n")


def _links_block() -> str:
    """Bloc monétisation (liens d'affiliation) ajouté à chaque description."""
    if LINKS_FILE.exists():
        body = LINKS_FILE.read_text(encoding="utf-8").strip()
        if body:
            return f"\n\n— LIENS —\n{body}"
    return ""


def _write_metadata(title: str, description: str, tags: str, out_dir: Path) -> None:
    description = (description or "") + _links_block()
    txt = (
        f"TITRE\n{title}\n\n"
        f"DESCRIPTION\n{description}\n\n"
        f"TAGS / HASHTAGS\n{tags}\n\n"
        f"---\n"
        f"⚠️ Coche \"contenu généré par IA\" à l'upload.\n"
        f"Disclaimer : Education, not financial advice.\n"
    )
    (out_dir / "metadata.txt").write_text(txt, encoding="utf-8")


def make_short(number: int, *, do_upload: bool) -> Path:
    short = parse_content.get_short(number)
    print(f"\n🎬 Short #{number} — {short.title}")
    if not short.voice:
        raise RuntimeError("Pas de texte voix dans le script.")

    out_dir = OUTPUT_DIR / f"short{number}"
    work = WORK_DIR / f"short{number}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    # 1. Voix
    print("  [1/4] Voix (ElevenLabs)…")
    voice_mp3 = voiceover.generate_voiceover(short.voice, work / "voice.mp3")

    # 2. Visuels
    print("  [2/4] Visuels…")
    images = visuals.get_visuals(f"short{number}", short.visual_prompts, work, ASSETS_DIR)

    # 3. Montage
    print("  [3/4] Montage (ffmpeg)…")
    final = assemble.assemble_video(
        images=images, voice_mp3=voice_mp3, hook=short.hook, voice_text=short.voice,
        work_dir=work, out_path=out_dir / f"short{number}.mp4",
        music=MUSIC if MUSIC.exists() else None,
    )

    # 4. Métadonnées
    print("  [4/4] Métadonnées…")
    _write_metadata(short.yt_title or short.title, short.yt_description, short.hashtags, out_dir)

    print(f"  ✅ Prêt : {final}")
    print(f"     Métadonnées : {out_dir / 'metadata.txt'}")

    if do_upload:
        print("  [↑] Upload YouTube (privé)…")
        from steps import youtube_upload
        tags = [t.lstrip("#") for t in short.hashtags.split() if t.startswith("#")]
        vid = youtube_upload.upload_short(
            final, short.yt_title or short.title, short.yt_description, tags,
            client_secret=BOT_DIR / "client_secret.json",
            token_cache=BOT_DIR / ".yt_token.json",
        )
        print(f"  ✅ Mis en ligne (privé) : https://youtube.com/watch?v={vid}")
        print("     Revois-le puis passe-le en public depuis YouTube Studio.")
    return final


def make_longform(number: int) -> Path:
    """Produit une vidéo LONG-FORM 16:9 (le moteur de revenu : RPM élevé)."""
    lf = parse_longform.get_longform(number)
    print(f"\n🎥 Long-form #{number} — {lf.title}  (~{len(lf.voice)/15.9/60:.1f} min)")
    if not lf.voice:
        raise RuntimeError("Pas de texte voix dans le script long-form.")

    out_dir = OUTPUT_DIR / f"long{number}"
    work = WORK_DIR / f"long{number}"
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    print("  [1/4] Voix (ElevenLabs)…")
    voice_mp3 = voiceover.generate_voiceover(lf.voice, work / "voice.mp3")

    print("  [2/4] Visuels (dossier long%d)…" % number)
    # Long-form : on dépose les images dans bot/assets/visuals/long<N>/ (15-25 conseillé,
    # le bot recycle si moins). Pas de prompts auto -> mode manuel/xAI via le folder_key.
    images = visuals.get_visuals(f"long{number}", lf.visual_prompts, work, ASSETS_DIR)

    print("  [3/4] Montage 16:9 (ffmpeg)…")
    final = assemble.assemble_video(
        images=images, voice_mp3=voice_mp3, hook="", voice_text=lf.voice,
        work_dir=work, out_path=out_dir / f"long{number}.mp4",
        music=MUSIC if MUSIC.exists() else None,
        vertical=False, captions=False,  # 16:9, sous-titres via YouTube auto-captions
    )

    print("  [4/4] Métadonnées…")
    _write_metadata(lf.yt_title or lf.title, lf.yt_description, lf.tags, out_dir)
    print(f"  ✅ Prêt : {final}")
    print(f"     Métadonnées : {out_dir / 'metadata.txt'}")
    return final


def cmd_make_long(targets: list[str]) -> None:
    if targets == ["all"]:
        numbers = list(parse_longform.FILES.keys())
    else:
        numbers = [int(t) for t in targets if t.isdigit()]
    if not numbers:
        print("Rien à produire. Exemple : ./bot/run.sh make-long 1")
        return
    ok, failed = [], []
    for n in numbers:
        try:
            make_longform(n)
            ok.append(n)
        except Exception as e:  # noqa: BLE001
            failed.append(n)
            print(f"  ❌ Long-form #{n} : {e}")
            if "--debug" in sys.argv:
                traceback.print_exc()
    print(f"\n=== Terminé : {len(ok)} OK {ok}  |  {len(failed)} échec(s) {failed} ===")


def cmd_make(targets: list[str], do_upload: bool) -> None:
    if targets == ["all"]:
        numbers = list(parse_content.load_shorts().keys())
    else:
        numbers = []
        for t in targets:
            if t.isdigit():
                numbers.append(int(t))
            else:
                print(f"  ⚠️  ignoré (pas un numéro de Short) : {t!r}")
        if not numbers:
            print("Rien à produire. Exemple : ./bot/run.sh make 1")
            return

    ok, failed = [], []
    for n in numbers:
        try:
            make_short(n, do_upload=do_upload)
            ok.append(n)
        except Exception as e:  # noqa: BLE001
            failed.append(n)
            print(f"  ❌ Short #{n} : {e}")
            if "--debug" in sys.argv:
                traceback.print_exc()

    print(f"\n=== Terminé : {len(ok)} OK {ok}  |  {len(failed)} échec(s) {failed} ===")
    if ok:
        print(f"Tes vidéos sont dans {OUTPUT_DIR}/  → revois puis publie.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quiet Capital — production faceless")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Liste les Shorts disponibles")
    mk = sub.add_parser("make", help="Produit un ou plusieurs Shorts")
    mk.add_argument("targets", nargs="+", help="numéros, ou 'all'")
    mk.add_argument("--upload", action="store_true", help="met en ligne en privé (désactivé par défaut)")
    mk.add_argument("--debug", action="store_true", help="trace complète en cas d'erreur")
    ml = sub.add_parser("make-long", help="Produit une ou plusieurs vidéos LONG-FORM 16:9 (revenu)")
    ml.add_argument("targets", nargs="+", help="numéros 1-4, ou 'all'")
    ml.add_argument("--debug", action="store_true", help="trace complète en cas d'erreur")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list()
    elif args.command == "make":
        cmd_make(args.targets, args.upload)
    elif args.command == "make-long":
        cmd_make_long(args.targets)


if __name__ == "__main__":
    main()
