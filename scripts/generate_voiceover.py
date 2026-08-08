"""
Turns data/current_video/script.json narration into voiceover audio.
Uses edge-tts by default (free, no API key). Swap in ElevenLabs by replacing
synthesize() if you want higher-quality voice later.
"""
import asyncio
import json
from pathlib import Path

import edge_tts
import yaml

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"
CONFIG_PATH = ROOT / "config.yaml"


async def synthesize(text: str, voice: str, rate: str, out_path: Path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out_path))


def main():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    script_data = json.loads((VIDEO_DIR / "script.json").read_text())
    narration = script_data["narration"]

    voice_cfg = config["voice"]
    out_path = VIDEO_DIR / "voiceover.mp3"

    asyncio.run(
        synthesize(narration, voice_cfg["voice_name"], voice_cfg["rate"], out_path)
    )
    print(f"Voiceover written to {out_path}")


if __name__ == "__main__":
    main()
