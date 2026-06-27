"""
Étape MONTAGE — assemble la vidéo finale 9:16 avec ffmpeg.

Pipeline :
  1. Chaque image -> clip vidéo avec léger zoom lent (effet Ken Burns)
  2. Concaténation des clips
  3. Génération de sous-titres (.srt) : hook en 1er, puis le texte voix réparti
  4. Mix audio voix + musique de fond optionnelle (assets/music.mp3)
  5. Gravure des sous-titres + export MP4 1080x1920

Prérequis : ffmpeg et ffprobe installés (https://ffmpeg.org/download.html).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30


def _require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} introuvable. Installe ffmpeg : https://ffmpeg.org/download.html "
                "(macOS: `brew install ffmpeg`)"
            )


def _audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _ken_burns_clip(img: Path, dur: float, out: Path) -> None:
    frames = max(1, int(dur * FPS))
    # scale/crop pour remplir 9:16, puis zoom progressif jusqu'à 1.12x.
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:s={W}x{H}:fps={FPS}"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-t", f"{dur:.3f}",
         "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)],
        check=True, capture_output=True,
    )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _srt_time(t: float) -> str:
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    ms = int((s - int(s)) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def _build_srt(hook: str, voice: str, total: float, out: Path) -> None:
    """Hook affiché ~2.2s, puis phrases de la voix réparties sur la durée restante."""
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

    lines = []
    for i, (start, end, txt) in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
        lines.append(txt)
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")


def assemble_video(
    images: list[Path], voice_mp3: Path, hook: str, voice_text: str,
    work_dir: Path, out_path: Path, music: Path | None = None,
) -> Path:
    _require_ffmpeg()
    work_dir.mkdir(parents=True, exist_ok=True)
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
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(silent)],
        check=True, capture_output=True,
    )

    # 3. Sous-titres
    srt = work_dir / "subs.srt"
    _build_srt(hook, voice_text, total, srt)
    style = (
        "FontName=Arial,Fontsize=15,Bold=1,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
        "Alignment=2,MarginV=120"
    )
    srt_escaped = str(srt).replace("\\", "/").replace(":", "\\:")

    # 4 + 5. Mix audio + gravure sous-titres -> export
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if music and music.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(silent), "-i", str(voice_mp3), "-i", str(music),
            "-filter_complex",
            f"[0:v]subtitles='{srt_escaped}':force_style='{style}'[v];"
            f"[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(silent), "-i", str(voice_mp3),
            "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(out_path),
        ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
