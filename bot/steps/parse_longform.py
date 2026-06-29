"""
Parse les scripts LONG-FORM (8 min) en données structurées.

Mappe un numéro 1-4 vers son fichier :
  1 -> content/02-longform-01-rolex.md
  2 -> content/05-longform-02-debt.md
  3 -> content/06-longform-03-patek.md
  4 -> content/07-longform-04-salary.md

Récupère : titre, texte voix (tous les blocs VOICE concaténés), et les
métadonnées YouTube (titre, description avec chapitres, tags).
Stdlib uniquement -> testable sans dépendances.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = REPO_ROOT / "content"

FILES = {
    1: CONTENT_DIR / "02-longform-01-rolex.md",
    2: CONTENT_DIR / "05-longform-02-debt.md",
    3: CONTENT_DIR / "06-longform-03-patek.md",
    4: CONTENT_DIR / "07-longform-04-salary.md",
}


@dataclass
class LongForm:
    number: int
    title: str = ""
    voice: str = ""
    yt_title: str = ""
    yt_description: str = ""
    tags: str = ""
    visual_prompts: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return bool(self.voice and self.yt_title)


def _clean_voice(text: str) -> str:
    text = re.sub(r"[*`_]", "", text)          # enlève le markdown d'emphase
    return re.sub(r"\s+", " ", text).strip()


def _collect_voice(body: str) -> str:
    """Concatène tous les blocs '> ...' qui suivent un marqueur **VOICE**."""
    chunks: list[str] = []
    capturing = False
    cur: list[str] = []
    for line in body.splitlines():
        if "**VOICE" in line:
            capturing = True
            cur = []
            continue
        if capturing:
            s = line.strip()
            if s.startswith(">"):
                cur.append(s.lstrip(">").strip())
            elif s == "":
                continue  # tolère les lignes vides à l'intérieur
            else:
                if cur:
                    chunks.append(" ".join(cur))
                capturing = False
                cur = []
    if cur:
        chunks.append(" ".join(cur))
    return _clean_voice(" ".join(chunks))


def get_longform(number: int) -> LongForm:
    if number not in FILES:
        raise KeyError(f"Long-form #{number} inconnu. Disponibles : {sorted(FILES)}")
    path = FILES[number]
    if not path.exists():
        raise FileNotFoundError(f"Script long-form introuvable : {path}")
    text = path.read_text(encoding="utf-8")
    lf = LongForm(number=number)

    if m := re.search(r'^#\s+LONG-FORM SCRIPT.*?[—-]\s*"?(.+?)"?\s*$', text, re.MULTILINE):
        lf.title = m.group(1).strip().strip('"')

    # On coupe avant la section MÉTADONNÉES pour ne garder que la narration.
    meta_split = re.split(r"###\s*📌?\s*MÉTADONNÉES", text)
    body = meta_split[0]
    meta = meta_split[1] if len(meta_split) > 1 else ""

    lf.voice = _collect_voice(body)

    if m := re.search(r"\*\*Titre\s*:\*\*\s*(.+)", meta):
        lf.yt_title = m.group(1).strip()
    if m := re.search(r"\*\*Tags\s*:\*\*\s*(.+)", meta):
        lf.tags = m.group(1).strip()
    # Description = blockquote après **Description :** jusqu'au prochain **...**
    desc, capturing = [], False
    for line in meta.splitlines():
        if "**Description" in line:
            capturing = True
            continue
        if capturing:
            s = line.strip()
            if s.startswith(">"):
                desc.append(s.lstrip(">").strip())
            elif s.startswith("**"):
                break
    lf.yt_description = "\n".join(desc).strip()
    return lf


def load_all() -> dict[int, LongForm]:
    return {n: get_longform(n) for n in FILES}


if __name__ == "__main__":
    for n, lf in load_all().items():
        flag = "✅" if lf.is_complete() else "⚠️ "
        print(f"{flag} Long #{n}: {lf.title}")
        print(f"    voice   : {len(lf.voice)} chars (~{len(lf.voice)/15.9/60:.1f} min)")
        print(f"    yt_title: {lf.yt_title}")
        print(f"    tags    : {lf.tags[:60]}...")
        print()
