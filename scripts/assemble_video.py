"""
Combines voiceover + images (Ken Burns pan/zoom) + burned captions + background
music into the final MP4.

Written for MoviePy 2.x (the moviepy.editor namespace was removed in 2.0;
methods like set_duration/set_position were renamed to with_duration/
with_position; resize was renamed to resized).

Captions are rendered directly with Pillow rather than MoviePy's TextClip,
since ImageMagick is no longer used by MoviePy 2.x anyway.

Output: data/current_video/final.mp4
"""
import json
from pathlib import Path

import numpy as np
import yaml
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_audioclips,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"
MUSIC_DIR = ROOT / "assets" / "music"

W, H = 1920, 1080

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (GitHub Actions)
    "C:/Windows/Fonts/arialbd.ttf",                            # Windows bold
    "C:/Windows/Fonts/arial.ttf",                              # Windows regular
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",       # macOS
]


def load_font(size=54):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_caption_image(text: str, width=W) -> np.ndarray:
    """Renders a caption as white text with a black outline on a transparent image."""
    font = load_font(54)
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    max_width = int(width * 0.85)
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)

    line_height = 66
    img_height = line_height * len(lines) + 20
    img = Image.new("RGBA", (width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (width - line_w) // 2
        y = i * line_height
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    return np.array(img)


def ken_burns_clip(image_path: Path, duration: float):
    clip = ImageClip(str(image_path)).with_duration(duration)
    clip = clip.resized(height=H * 1.15).with_position("center")
    zoomed = clip.resized(lambda t: 1 + 0.04 * (t / duration))
    return CompositeVideoClip([zoomed], size=(W, H)).with_duration(duration)


def looped_audio(path: Path, target_duration: float):
    clip = AudioFileClip(str(path))
    if clip.duration >= target_duration:
        return clip.subclipped(0, target_duration)
    n_loops = int(target_duration // clip.duration) + 1
    looped = concatenate_audioclips([clip] * n_loops)
    return looped.subclipped(0, target_duration)


def parse_srt(srt_path: Path):
    entries = []
    blocks = srt_path.read_text().strip().split("\n\n")
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        start_str, end_str = lines[1].split(" --> ")

        def to_seconds(ts):
            h, m, rest = ts.split(":")
            s, ms = rest.split(",")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        text = " ".join(lines[2:])
        entries.append((to_seconds(start_str), to_seconds(end_str), text))
    return entries


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    script_data = json.loads((VIDEO_DIR / "script.json").read_text())
    images_dir = VIDEO_DIR / "images"

    image_files = sorted(images_dir.glob("scene_*.png"))
    if not image_files:
        raise RuntimeError("No scene images found -- run generate_visuals.py first.")

    audio = AudioFileClip(str(VIDEO_DIR / "voiceover.mp3"))
    total_duration = audio.duration
    per_scene = total_duration / len(image_files)

    clips = [ken_burns_clip(p, per_scene) for p in image_files]
    video = concatenate_videoclips(clips, method="compose")

    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if music_files:
        music = looped_audio(music_files[0], total_duration).with_volume_scaled(0.08)
        final_audio = CompositeAudioClip([music, audio])
    else:
        final_audio = audio
        print("No background music found in assets/music/ -- proceeding with narration only.")

    video = video.with_audio(final_audio).with_duration(total_duration)

    srt_path = VIDEO_DIR / "captions.srt"
    if srt_path.exists():
        caption_clips = []
        for start, end, text in parse_srt(srt_path):
            img_array = render_caption_image(text)
            txt_clip = (
                ImageClip(img_array)
                .with_start(start)
                .with_end(end)
                .with_position(("center", int(H * 0.78)))
            )
            caption_clips.append(txt_clip)
        video = CompositeVideoClip([video, *caption_clips], size=(W, H))

    out_path = VIDEO_DIR / "final.mp4"
    video.write_videofile(
        str(out_path), fps=30, codec="libx264", audio_codec="aac", threads=4
    )
    print(f"Final video written to {out_path}")


if __name__ == "__main__":
    main()
