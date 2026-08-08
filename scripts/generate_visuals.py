"""
Generates one AI illustration per scene in script.json, saved to
data/current_video/images/scene_00.png, scene_01.png, ...

Uses Pollinations.ai — free, no API key, no signup required. Anonymous
requests are rate-limited (~1 every 15s), so we space requests out to stay
under that. If you later register a free Pollinations account, set
POLLINATIONS_TOKEN as an env var/secret to remove the watermark and raise
the rate limit — the script picks it up automatically if present.
"""
import json
import os
import time
import urllib.parse
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
REQUEST_DELAY_SECONDS = 16  # stay under the ~1/15s anonymous rate limit


def generate_image(prompt: str, width: int, height: int, token: str | None) -> bytes:
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt))
    params = {"width": width, "height": height, "nologo": "true"}
    if token:
        params["token"] = token
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.content


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    script_data = json.loads((VIDEO_DIR / "script.json").read_text())
    scenes = script_data["scenes"]

    images_dir = VIDEO_DIR / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    style = config["visuals"]["style"]
    token = os.environ.get("POLLINATIONS_TOKEN")  # optional, works fine without it

    for i, scene in enumerate(scenes):
        prompt = f"{scene['visual_prompt']}. Style: {style}. Widescreen cinematic composition."
        image_bytes = generate_image(prompt, width=1536, height=1024, token=token)
        out_path = images_dir / f"scene_{i:02d}.png"
        out_path.write_bytes(image_bytes)
        print(f"Generated {out_path}")
        if i < len(scenes) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Generated {len(scenes)} images in {images_dir}")


if __name__ == "__main__":
    main()
