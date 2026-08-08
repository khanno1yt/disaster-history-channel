"""
Single entrypoint that runs the whole pipeline: topics -> script -> voiceover
-> visuals -> captions -> assemble -> upload -> cleanup.

Any stage raising an exception stops the run before upload, so a broken step
never posts a broken video. GitHub Actions will show the run as failed and
you'll get a notification email from GitHub — that's the only "check" this
system needs from you.
"""
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "data" / "current_video"

sys.path.insert(0, str(ROOT / "scripts"))

import generate_topics
import generate_script
import generate_voiceover
import generate_visuals
import generate_captions
import assemble_video
import upload_youtube


STAGES = [
    ("Refilling topic queue", generate_topics.main),
    ("Writing script", generate_script.main),
    ("Generating voiceover", generate_voiceover.main),
    ("Generating visuals", generate_visuals.main),
    ("Generating captions", generate_captions.main),
    ("Assembling video", assemble_video.main),
    ("Uploading to YouTube", upload_youtube.main),
]


def main():
    if VIDEO_DIR.exists():
        shutil.rmtree(VIDEO_DIR)

    for label, fn in STAGES:
        print(f"\n=== {label} ===")
        try:
            fn()
        except Exception:
            print(f"\nPIPELINE FAILED at stage: {label}")
            traceback.print_exc()
            sys.exit(1)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
