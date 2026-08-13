"""
Generates a YouTube thumbnail (1280x720): a dramatic AI-generated background
image via Pollinations, with short high-contrast text burned in via ffmpeg.
No manual design work needed -- runs unattended alongside the rest of the
pipeline.
"""
import json
import os
import shutil
import subprocess
import urllib.parse
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (GitHub Actions)
    "C:/Windows/Fonts/arialbd.ttf",                            # Windows bold
    "C:/Windows/Fonts/arial.ttf",                              # Windows regular
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",       # macOS
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise RuntimeError("No usable font found for thumbnail text.")


def ffmpeg_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def generate_base_image(prompt: str, token: str | None) -> bytes:
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt))
    params = {"width": 1280, "height": 720, "nologo": "true"}
    if token:
        params["token"] = token
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.content


def escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    script_data = json.loads((VIDEO_DIR / "script.json").read_text())
    thumb_text = script_data.get("thumbnail_text") or script_data["title"][:30]
    thumb_prompt = script_data.get("thumbnail_visual_prompt") or (
        script_data["scenes"][0]["visual_prompt"] if script_data.get("scenes") else script_data["title"]
    )

    style = config["visuals"]["style"]
    full_prompt = f"{thumb_prompt}. Style: {style}. Dramatic wide shot, high contrast, cinematic."
    token = os.environ.get("POLLINATIONS_TOKEN")
    base_image = generate_base_image(full_prompt, token)

    base_path = VIDEO_DIR / "thumbnail_base.png"
    base_path.write_bytes(base_image)

    out_path = VIDEO_DIR / "thumbnail.jpg"
    ffmpeg = ffmpeg_path()

    try:
        font = find_font()
        text = escape_drawtext(thumb_text.upper())
        vf = (
            f"drawtext=fontfile='{font}':text='{text}':"
            "fontsize=80:fontcolor=white:borderw=6:bordercolor=black:"
            "x=(w-text_w)/2:y=h-th-70:line_spacing=12"
        )
        cmd = [ffmpeg, "-y", "-i", str(base_path), "-vf", vf, "-q:v", "2", str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1500:])
    except Exception as e:
        print(f"Thumbnail text overlay failed ({e}), using plain base image instead.")
        cmd = [ffmpeg, "-y", "-i", str(base_path), "-q:v", "2", str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)

    print(f"Thumbnail written to {out_path}")


if __name__ == "__main__":
    main()
