"""
Étape VOIX — génère un MP3 via l'API ElevenLabs, AVEC les timestamps.

On utilise l'endpoint `/with-timestamps` : il renvoie l'audio + l'alignement
caractère par caractère (temps de début/fin de chaque lettre prononcée).
Cet alignement est enregistré à côté du MP3 (voice.json) pour que le montage
cale les sous-titres EXACTEMENT sur la voix. Même coût qu'un TTS normal.

Nécessite ELEVENLABS_API_KEY.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import requests

DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian
MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
BASE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def _payload(text: str) -> dict:
    return {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
    }


def generate_voiceover(text: str, out_path: Path, *, voice_id: str | None = None) -> Path:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY manquante. Crée une clé sur elevenlabs.io "
            "et ajoute-la dans bot/.env"
        )
    voice_id = voice_id or DEFAULT_VOICE_ID
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    align_path = out_path.with_suffix(".json")
    if align_path.exists():
        align_path.unlink()

    # 1) Endpoint avec timestamps (pour caler les sous-titres sur la voix)
    resp = requests.post(BASE.format(voice_id=voice_id) + "/with-timestamps",
                         headers=headers, json=_payload(text), timeout=120)
    if resp.status_code == 200:
        data = resp.json()
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        align = data.get("alignment") or data.get("normalized_alignment")
        if align:
            align_path.write_text(json.dumps(align), encoding="utf-8")
        return out_path

    # 2) Repli : endpoint classique (audio brut, sans timestamps -> sous-titres estimés)
    resp = requests.post(BASE.format(voice_id=voice_id),
                         headers=headers, json=_payload(text), timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs a échoué ({resp.status_code}) : {resp.text[:300]}")
    out_path.write_bytes(resp.content)
    return out_path
