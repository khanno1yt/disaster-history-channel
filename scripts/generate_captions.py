"""
Transcribes voiceover.mp3 with faster-whisper to get accurate word timings,
then writes an SRT file. We transcribe rather than estimate timing from text
because TTS speaking speed varies with punctuation and content.
"""
from pathlib import Path

import yaml
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    model_size = config["captions"]["whisper_model"]
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    audio_path = VIDEO_DIR / "voiceover.mp3"
    segments, _ = model.transcribe(str(audio_path), word_timestamps=False)

    srt_lines = []
    for i, seg in enumerate(segments, start=1):
        srt_lines.append(str(i))
        srt_lines.append(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}")
        srt_lines.append(seg.text.strip())
        srt_lines.append("")

    out_path = VIDEO_DIR / "captions.srt"
    out_path.write_text("\n".join(srt_lines))
    print(f"Captions written to {out_path}")


if __name__ == "__main__":
    main()
