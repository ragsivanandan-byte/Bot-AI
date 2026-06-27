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
from steps import parse_content, voiceover, visuals, assemble  # noqa: E402

OUTPUT_DIR = BOT_DIR / "output"
WORK_DIR = BOT_DIR / ".work"
ASSETS_DIR = BOT_DIR / "assets"
MUSIC = ASSETS_DIR / "music.mp3"


def cmd_list() -> None:
    shorts = parse_content.load_shorts()
    print(f"\n{len(shorts)} Shorts disponibles :\n")
    for n, s in shorts.items():
        flag = "✅" if s.is_complete() else "⚠️ "
        print(f"  {flag} {n:>2}. {s.title}")
    print("\nProduis-en un :  python bot/pipeline.py make 1\n")


def _write_metadata(short, out_dir: Path) -> None:
    txt = (
        f"TITRE\n{short.yt_title or short.title}\n\n"
        f"DESCRIPTION\n{short.yt_description}\n\n"
        f"HASHTAGS\n{short.hashtags}\n\n"
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
    images = visuals.get_visuals(number, short.visual_prompts, work, ASSETS_DIR)

    # 3. Montage
    print("  [3/4] Montage (ffmpeg)…")
    final = assemble.assemble_video(
        images=images, voice_mp3=voice_mp3, hook=short.hook, voice_text=short.voice,
        work_dir=work, out_path=out_dir / f"short{number}.mp4",
        music=MUSIC if MUSIC.exists() else None,
    )

    # 4. Métadonnées
    print("  [4/4] Métadonnées…")
    _write_metadata(short, out_dir)

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


def cmd_make(targets: list[str], do_upload: bool) -> None:
    if targets == ["all"]:
        numbers = list(parse_content.load_shorts().keys())
    else:
        numbers = [int(t) for t in targets]

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

    args = parser.parse_args()
    if args.command == "list":
        cmd_list()
    elif args.command == "make":
        cmd_make(args.targets, args.upload)


if __name__ == "__main__":
    main()
