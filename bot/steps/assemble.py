"""
Étape MONTAGE — assemble la vidéo finale 9:16 avec ffmpeg.

Sous-titres (3 niveaux automatiques, dans l'ordre de préférence) :
  1. ffmpeg avec libass        -> gravure native du .srt (idéal)
  2. ffmpeg + Pillow (PIL)     -> le bot rend les sous-titres en PNG et les
                                  incruste (marche même SANS libass) ✅ ton Mac
  3. aucun des deux            -> vidéo sans sous-titres + fichier .srt à côté

Pipeline : images -> clips Ken Burns -> concat -> audio (voix + musique) +
sous-titres -> MP4 1080x1920.

Prérequis : ffmpeg + ffprobe. Sous-titres auto : `pip install pillow`.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30

# Polices possibles (macOS / Linux) pour les sous-titres PNG.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} introuvable. Installe ffmpeg : https://ffmpeg.org/download.html "
                "(macOS: `brew install ffmpeg`)"
            )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg a échoué (code {proc.returncode}) :\n{tail}")


def _has_subtitles_filter() -> bool:
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                             capture_output=True, text=True)
        return bool(re.search(r"\bsubtitles\b", out.stdout))
    except Exception:
        return False


def _pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ken_burns_clip(img: Path, dur: float, out: Path) -> None:
    frames = max(1, int(dur * FPS))
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:s={W}x{H}:fps={FPS}"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{dur:.3f}",
          "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _srt_time(t: float) -> str:
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    ms = int((s - int(s)) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def _build_cues(hook: str, voice: str, total: float) -> list[tuple[float, float, str]]:
    """Hook ~2.2s, puis chaque phrase répartie au prorata de sa longueur."""
    cues: list[tuple[float, float, str]] = []
    hook_end = min(2.2, total * 0.25)
    if hook:
        cues.append((0.0, hook_end, hook.upper()))
    sentences = _split_sentences(voice)
    if sentences:
        span = total - hook_end
        weights = [len(s) for s in sentences]
        wsum = sum(weights) or 1
        t = hook_end
        for s, w in zip(sentences, weights):
            d = span * (w / wsum)
            cues.append((t, min(total, t + d), s))
            t += d
    return cues


def _write_srt(cues: list[tuple[float, float, str]], out: Path) -> None:
    lines = []
    for i, (start, end, txt) in enumerate(cues, 1):
        lines += [str(i), f"{_srt_time(start)} --> {_srt_time(end)}", txt, ""]
    out.write_text("\n".join(lines), encoding="utf-8")


# --- Sous-titres en PNG (chemin sans libass) --------------------------------
def _load_font(size: int):
    from PIL import ImageFont
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _render_caption_png(text: str, out_path: Path) -> int:
    """Rend un sous-titre centré (blanc, gros contour noir) sur fond transparent.
    Retourne la hauteur du PNG."""
    from PIL import Image, ImageDraw
    font = _load_font(60)
    pad, stroke, max_w = 24, 8, W - 160
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = _wrap(probe, text, font, max_w)
    asc, desc = font.getmetrics()
    line_h = asc + desc + 14
    h = line_h * len(lines) + pad * 2
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        x = (W - draw.textlength(ln, font=font)) // 2
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += line_h
    img.save(out_path)
    return h


def _assemble_png_captions(silent: Path, voice_mp3: Path, music: Path | None,
                           cues: list, work_dir: Path, out_path: Path) -> None:
    cap_dir = work_dir / "caps"
    cap_dir.mkdir(exist_ok=True)
    for old in cap_dir.glob("*.png"):
        old.unlink()

    has_music = bool(music and music.exists())
    inputs = ["-i", str(silent), "-i", str(voice_mp3)]
    base = 2
    if has_music:
        inputs += ["-i", str(music)]
        base = 3

    placed = []  # (input_index, y, start, end)
    for i, (s, e, txt) in enumerate(cues):
        png = cap_dir / f"cap{i:02d}.png"
        h = _render_caption_png(txt, png)
        y = max(20, int(H * 0.64) - h // 2)  # zone de lecture, au-dessus de l'UI Shorts
        inputs += ["-loop", "1", "-i", str(png)]
        placed.append((base + i, y, s, e))

    parts, cur = [], "0:v"
    for idx, y, s, e in placed:
        nxt = f"v{idx}"
        parts.append(f"[{cur}][{idx}:v]overlay=x=0:y={y}:"
                     f"enable='between(t,{s:.3f},{e:.3f})'[{nxt}]")
        cur = nxt
    if has_music:
        parts.append("[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:"
                     "duration=first:dropout_transition=0[a]")
        amap = "[a]"
    else:
        amap = "1:a"

    map_v = f"[{cur}]" if placed else "0:v"
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", ";".join(parts),
           "-map", map_v, "-map", amap, "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(out_path)]
    _run(cmd)


def assemble_video(
    images: list[Path], voice_mp3: Path, hook: str, voice_text: str,
    work_dir: Path, out_path: Path, music: Path | None = None,
) -> Path:
    _require_ffmpeg()
    if not images:
        raise RuntimeError("Aucune image à monter (dossier visuals vide).")
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for old in work_dir.glob("clip*.mp4"):
        old.unlink()
    total = _audio_duration(voice_mp3)
    per = total / len(images)

    # 1. Clips Ken Burns
    clips = []
    for i, img in enumerate(images):
        clip = work_dir / f"clip{i:02d}.mp4"
        _ken_burns_clip(img, per, clip)
        clips.append(clip)

    # 2. Concat
    concat_list = work_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    silent = work_dir / "silent.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
          "-c", "copy", str(silent)])

    # 3. Sous-titres
    cues = _build_cues(hook, voice_text, total)
    srt = work_dir / "subs.srt"
    _write_srt(cues, srt)
    has_music = bool(music and music.exists())

    # Chemin 1 : libass (gravure native du .srt)
    if _has_subtitles_filter():
        srt_escaped = str(srt).replace("\\", "/").replace(":", "\\:")
        style = ("FontName=Arial,Fontsize=15,Bold=1,PrimaryColour=&H00FFFFFF,"
                 "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
                 "Alignment=2,MarginV=300")
        sub = f"subtitles='{srt_escaped}':force_style='{style}'"
        cmd = ["ffmpeg", "-y", "-i", str(silent), "-i", str(voice_mp3)]
        if has_music:
            cmd += ["-i", str(music), "-filter_complex",
                    f"[0:v]{sub}[v];[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:"
                    "duration=first:dropout_transition=0[a]", "-map", "[v]", "-map", "[a]"]
        else:
            cmd += ["-vf", sub, "-map", "0:v", "-map", "1:a"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out_path)]
        _run(cmd)
        print("  ✅ Sous-titres incrustés (libass).")
        return out_path

    # Chemin 2 : Pillow (le bot rend les sous-titres en PNG, sans libass)
    if _pillow_available():
        _assemble_png_captions(silent, voice_mp3, music, cues, work_dir, out_path)
        print("  ✅ Sous-titres incrustés par le bot (PNG).")
        return out_path

    # Chemin 3 : ni libass ni Pillow -> vidéo sans sous-titres + .srt
    cmd = ["ffmpeg", "-y", "-i", str(silent), "-i", str(voice_mp3)]
    if has_music:
        cmd += ["-i", str(music), "-filter_complex",
                "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)]
    _run(cmd)
    sidecar = out_path.with_suffix(".srt")
    sidecar.write_text(srt.read_text(encoding="utf-8"), encoding="utf-8")
    print("  ⚠️  Sous-titres non incrustés (installe Pillow : pip install pillow).")
    print(f"      → fichier {sidecar.name} déposé à côté.")
    return out_path
