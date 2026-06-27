"""
Étape VOIX — génère un MP3 via l'API ElevenLabs.

Coût indicatif : ~$0.04 par Short (Multilingual v2, ~350 caractères).
Nécessite la variable d'env ELEVENLABS_API_KEY.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

# Voix premade ElevenLabs. "Brian" = ton autorité/finance. Override via ELEVENLABS_VOICE_ID.
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian
MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def generate_voiceover(text: str, out_path: Path, *, voice_id: str | None = None) -> Path:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY manquante. Crée une clé sur elevenlabs.io "
            "et ajoute-la dans bot/.env"
        )
    voice_id = voice_id or DEFAULT_VOICE_ID
    out_path.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.post(
        API_URL.format(voice_id=voice_id),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": MODEL_ID,
            # Stability ~0.5 = ton posé et naturel (idéal luxe/finance).
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs a échoué ({resp.status_code}) : {resp.text[:300]}")

    out_path.write_bytes(resp.content)
    return out_path
