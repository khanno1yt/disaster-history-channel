"""
Combines voiceover + images (Ken Burns pan/zoom) + burned captions +
background music into the final MP4, using ffmpeg directly.

Why not MoviePy: MoviePy's per-frame Python zoom/pan and caption compositing
is extremely slow -- slow enough that an 8-minute 1080p video was only 52%
rendered after 30+ minutes on a GitHub Actions runner, and the job timed
out. ffmpeg's zoompan and subtitles filters do the same work in compiled C
and finish an equivalent video in a couple of minutes.

Output: data/current_video/final.mp4
"""
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"
MUSIC_DIR = ROOT / "assets" / "music"

W, H = 1920, 1080
FPS = 30


def ffmpeg_path() -> str:
    """Prefer imageio-ffmpeg's bundled binary (works even if ffmpeg isn't
    separately installed, e.g. on a fresh Windows machine), falling back
    to whatever 'ffmpeg' is on PATH (this is what's used in CI, since the
    workflow apt-installs a full ffmpeg with subtitle-rendering support)."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        raise RuntimeError(f"ffmpeg command failed: {' '.join(cmd[:4])}...")


def get_audio_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run(
        [ffmpeg, "-i", str(path)], capture_output=True, text=True
    )
    for line in result.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = time_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"Could not determine duration of {path}")


def build_scene_clip(ffmpeg: str, image_path: Path, duration: float, out_path: Path):
    """Renders one scene image into a short Ken Burns zoom video clip."""
    frames = max(int(duration * FPS), 1)
    vf = (
        f"scale={W * 2}:{H * 2},"
        f"zoompan=z='min(zoom+0.0015,1.15)':d={frames}:s={W}x{H}:fps={FPS}"
    )
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-i", str(image_path),
        "-vf", vf, "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        str(out_path),
    ]
    run_ffmpeg(cmd)


def concat_clips(ffmpeg: str, clip_paths: list, out_path: Path):
    list_file = VIDEO_DIR / "concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))
    cmd = [
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out_path),
    ]
    run_ffmpeg(cmd)


def burn_captions(ffmpeg: str, video_in: Path, srt_path: Path, video_out: Path) -> bool:
    """Burns in captions via ffmpeg's subtitles filter. Returns True on
    success. If the local ffmpeg build lacks subtitle support (rare, but
    possible on some Windows setups), this fails gracefully and the video
    just goes out without captions rather than crashing the pipeline."""
    style = (
        "FontName=DejaVu Sans,FontSize=20,PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H000000,BorderStyle=1,Outline=2,"
        "Alignment=2,MarginV=60"
    )
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        ffmpeg, "-y", "-i", str(video_in),
        "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(video_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Caption burn-in failed, continuing without captions:")
        print(result.stderr[-1500:])
        return False
    return True


def mux_audio(ffmpeg: str, video_in: Path, voiceover: Path, total_duration: float, out_path: Path):
    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if music_files:
        cmd = [
            ffmpeg, "-y", "-i", str(video_in),
            "-stream_loop", "-1", "-i", str(music_files[0]),
            "-i", str(voiceover),
            "-filter_complex",
            f"[1:a]volume=0.08,atrim=0:{total_duration}[music];"
            "[music][2:a]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(out_path),
        ]
    else:
        cmd = [
            ffmpeg, "-y", "-i", str(video_in), "-i", str(voiceover),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(out_path),
        ]
    run_ffmpeg(cmd)


def main():
    images_dir = VIDEO_DIR / "images"
    image_files = sorted(images_dir.glob("scene_*.png"))
    if not image_files:
        raise RuntimeError("No scene images found -- run generate_visuals.py first.")

    ffmpeg = ffmpeg_path()
    voiceover_path = VIDEO_DIR / "voiceover.mp3"
    total_duration = get_audio_duration(ffmpeg, voiceover_path)
    per_scene = total_duration / len(image_files)

    clips_dir = VIDEO_DIR / "clips"
    clips_dir.mkdir(exist_ok=True)
    clip_paths = []
    for i, img in enumerate(image_files):
        out_path = clips_dir / f"clip_{i:02d}.mp4"
        build_scene_clip(ffmpeg, img, per_scene, out_path)
        clip_paths.append(out_path)
        print(f"Rendered scene clip {i + 1}/{len(image_files)}")

    silent_video = VIDEO_DIR / "silent.mp4"
    concat_clips(ffmpeg, clip_paths, silent_video)
    print("Concatenated scene clips")

    srt_path = VIDEO_DIR / "captions.srt"
    captioned_video = VIDEO_DIR / "captioned.mp4"
    if srt_path.exists() and burn_captions(ffmpeg, silent_video, srt_path, captioned_video):
        print("Captions burned in")
        video_for_audio = captioned_video
    else:
        video_for_audio = silent_video

    out_path = VIDEO_DIR / "final.mp4"
    mux_audio(ffmpeg, video_for_audio, voiceover_path, total_duration, out_path)
    print(f"Final video written to {out_path}")


if __name__ == "__main__":
    main()
