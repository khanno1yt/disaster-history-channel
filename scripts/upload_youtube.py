"""
Uploads data/current_video/final.mp4 to YouTube using the title/description/
tags from script.json, then attaches the custom thumbnail if one exists.

Requires a one-time OAuth setup (see README) to get a refresh token, stored
as the YOUTUBE_REFRESH_TOKEN secret alongside YOUTUBE_CLIENT_ID and
YOUTUBE_CLIENT_SECRET.
"""
import json
import os
from pathlib import Path

import yaml
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_authenticated_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    script_data = json.loads((VIDEO_DIR / "script.json").read_text())
    video_path = VIDEO_DIR / "final.mp4"

    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": script_data["title"],
            "description": script_data["description"],
            "tags": script_data.get("tags", []) + config["youtube"]["default_tags"],
            "categoryId": config["youtube"]["category_id"],
        },
        "status": {
            "privacyStatus": config["youtube"]["privacy_status"],
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Upload complete: https://youtu.be/{video_id}")

    thumbnail_path = VIDEO_DIR / "thumbnail.jpg"
    if thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
        ).execute()
        print("Custom thumbnail set")
    else:
        print("No thumbnail.jpg found -- skipping thumbnail upload")


if __name__ == "__main__":
    main()
