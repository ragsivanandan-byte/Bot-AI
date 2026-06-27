"""
Parse les fichiers de contenu Quiet Capital en données structurées par Short.

Lit 3 fichiers du dossier ../content/ :
  - 01-shorts-scripts.md      -> texte voix-off, hook à l'écran, titre
  - 03-grok-prompts.md        -> prompts visuels (par "VIDÉO N")
  - 08-shorts-metadata.md     -> titre YouTube, description, hashtags

N'utilise QUE la bibliothèque standard -> testable sans dépendances.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Racine du repo = deux niveaux au-dessus de ce fichier (bot/steps/ -> repo/)
REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = REPO_ROOT / "content"

SCRIPTS_FILE = CONTENT_DIR / "01-shorts-scripts.md"
PROMPTS_FILE = CONTENT_DIR / "03-grok-prompts.md"
META_FILE = CONTENT_DIR / "08-shorts-metadata.md"


@dataclass
class Short:
    number: int
    title: str = ""
    voice: str = ""                       # texte à envoyer à ElevenLabs
    hook: str = ""                         # gros texte affiché dès la 1re seconde
    cta: str = ""
    visual_prompts: list[str] = field(default_factory=list)  # prompts Grok
    yt_title: str = ""
    yt_description: str = ""
    hashtags: str = ""

    def is_complete(self) -> bool:
        return bool(self.voice and self.visual_prompts)


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Fichier de contenu introuvable : {path}")
    return path.read_text(encoding="utf-8")


def _split_sections(text: str, header_word: str) -> dict[int, str]:
    """Découpe un markdown en sections '## <header_word> N — ...' indexées par N."""
    pattern = re.compile(rf"^##\s+{header_word}\s+(\d+)\b.*$", re.MULTILINE)
    sections: dict[int, str] = {}
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        n = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[n] = text[start:end]
    return sections


def _extract_quoted(line: str) -> str:
    """Récupère le texte entre guillemets droits ou typographiques."""
    m = re.search(r'["“«]\s*(.+?)\s*["”»]', line)
    return m.group(1).strip() if m else line.strip()


def _parse_scripts(text: str, shorts: dict[int, Short]) -> None:
    headers = {n: re.search(rf"^##\s+SHORT\s+{n}\s+—\s+(.+)$", text, re.MULTILINE)
               for n in _split_sections(text, "SHORT")}
    for n, body in _split_sections(text, "SHORT").items():
        s = shorts.setdefault(n, Short(number=n))
        h = headers.get(n)
        if h:
            s.title = h.group(1).strip()
        # Hook : ligne **[ON-SCREEN ...]** "..."
        for line in body.splitlines():
            if "[ON-SCREEN" in line:
                s.hook = _extract_quoted(line)
            elif line.strip().startswith("**[CTA]**"):
                s.cta = _extract_quoted(line)
        # Voix : bloc de citation '>' qui suit le marqueur **VOICE
        voice_lines: list[str] = []
        capturing = False
        for line in body.splitlines():
            if "**VOICE" in line:
                capturing = True
                continue
            if capturing:
                if line.strip().startswith(">"):
                    voice_lines.append(line.strip().lstrip(">").strip())
                elif line.strip() == "":
                    if voice_lines:
                        break
                else:
                    break
        s.voice = " ".join(voice_lines).strip()


def _parse_prompts(text: str, shorts: dict[int, Short]) -> None:
    for n, body in _split_sections(text, "VIDÉO").items():
        s = shorts.setdefault(n, Short(number=n))
        prompts = re.findall(r"^\s*-\s+`([^`]+)`", body, re.MULTILINE)
        if prompts:
            s.visual_prompts = [p.strip() for p in prompts]


def _parse_meta(text: str, shorts: dict[int, Short]) -> None:
    for n, body in _split_sections(text, "SHORT").items():
        s = shorts.setdefault(n, Short(number=n))
        if m := re.search(r"\*\*Titre\s*:\*\*\s*(.+)", body):
            s.yt_title = m.group(1).strip()
        if m := re.search(r"\*\*Hashtags\s*:\*\*\s*(.+)", body):
            s.hashtags = m.group(1).strip()
        # Description = bloc de citation après **Description :**
        desc_lines: list[str] = []
        capturing = False
        for line in body.splitlines():
            if "**Description" in line:
                capturing = True
                continue
            if capturing:
                if line.strip().startswith(">"):
                    desc_lines.append(line.strip().lstrip(">").strip())
                elif line.strip().startswith("**"):
                    break
        s.yt_description = " ".join(desc_lines).strip()


def load_shorts() -> dict[int, Short]:
    """Charge et fusionne les 3 fichiers en {numéro: Short}."""
    shorts: dict[int, Short] = {}
    _parse_scripts(_read(SCRIPTS_FILE), shorts)
    _parse_prompts(_read(PROMPTS_FILE), shorts)
    _parse_meta(_read(META_FILE), shorts)
    return dict(sorted(shorts.items()))


def get_short(number: int) -> Short:
    shorts = load_shorts()
    if number not in shorts:
        raise KeyError(f"Short #{number} introuvable. Disponibles : {sorted(shorts)}")
    return shorts[number]


if __name__ == "__main__":
    # Auto-test : affiche un résumé de tout ce qui a été parsé.
    data = load_shorts()
    print(f"✓ {len(data)} Shorts parsés depuis {CONTENT_DIR}\n")
    for n, s in data.items():
        flag = "✅" if s.is_complete() else "⚠️ "
        print(f"{flag} Short {n}: {s.title}")
        print(f"    hook    : {s.hook!r}")
        print(f"    voice   : {len(s.voice)} chars — {s.voice[:60]}...")
        print(f"    visuals : {len(s.visual_prompts)} prompts")
        print(f"    yt_title: {s.yt_title}")
        print()
