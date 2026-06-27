"""
Étape UPLOAD (OPTIONNELLE, désactivée par défaut) — publie sur YouTube.

⚠️ POLITIQUE 2026 : l'upload 100% automatique de contenu IA répétitif est
exactement ce que YouTube démonétise. Ce module existe, mais le bot le laisse
DÉSACTIVÉ par défaut : tu télécharges le MP4, tu le revois 30 secondes, et tu
publies toi-même (ou tu actives l'upload en connaissance de cause).

Setup (si tu veux l'activer) :
  1. Google Cloud Console -> active "YouTube Data API v3"
  2. Crée des identifiants OAuth (Desktop) -> télécharge client_secret.json dans bot/
  3. pip install google-auth-oauthlib google-api-python-client
  4. Lance avec --upload : un navigateur s'ouvre pour autoriser (1re fois seulement)
"""
from __future__ import annotations

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload_short(video: Path, title: str, description: str, tags: list[str],
                 client_secret: Path, token_cache: Path) -> str:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        raise RuntimeError(
            "Dépendances upload manquantes. Lance :\n"
            "  pip install google-auth-oauthlib google-api-python-client"
        ) from e

    creds = None
    if token_cache.exists():
        creds = Credentials.from_authorized_user_file(str(token_cache), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
            creds = flow.run_local_server(port=0)
        token_cache.write_text(creds.to_json(), encoding="utf-8")

    youtube = build("youtube", "v3", credentials=creds)
    # #Shorts dans le titre/description + ratio 9:16 = traité comme Short par YouTube.
    body = {
        "snippet": {"title": title[:100], "description": description, "tags": tags,
                    "categoryId": "22"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response["id"]
