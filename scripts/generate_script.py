"""
Pulls the next topic off the queue and writes a full narration script plus a
scene-by-scene visual breakdown (used later to generate images), and now
also a thumbnail hook line + thumbnail visual prompt.

Rotates between structure styles defined in config.yaml so consecutive videos
don't share the same opening/pacing pattern -- this is the "variation" layer
YouTube's inauthentic-content reviewers look for.

Uses Google's Gemini API free tier (no cost, no credit card).
"""
import json
import os
import random
import time
from pathlib import Path

import yaml
from google import genai

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "data" / "topics_queue.json"
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "data" / "last_structure.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def pop_next_topic():
    with open(QUEUE_PATH) as f:
        data = json.load(f)
    if not data["queue"]:
        raise RuntimeError("Topic queue is empty -- run generate_topics.py first.")
    topic = data["queue"].pop(0)
    data["used"].append(topic)
    with open(QUEUE_PATH, "w") as f:
        json.dump(data, f, indent=2)
    return topic


def pick_structure(config):
    structures = config["script"]["structures"]
    last = None
    if STATE_PATH.exists():
        last = json.loads(STATE_PATH.read_text()).get("last")
    choices = [s for s in structures if s != last] or structures
    chosen = random.choice(choices)
    STATE_PATH.write_text(json.dumps({"last": chosen}))
    return chosen


STRUCTURE_INSTRUCTIONS = {
    "cold_open_moment": (
        "Open mid-incident, at the moment things start going wrong, with no "
        "context yet. Then cut back to explain how it built up to that point, "
        "then carry through to the resolution and lessons learned."
    ),
    "timeline_countdown": (
        "Structure the video as a countdown of key moments (e.g. '6 hours "
        "before', '40 minutes before', 'the moment of failure'), building "
        "tension toward the incident itself, then close with the aftermath "
        "and what changed afterward."
    ),
    "investigator_perspective": (
        "Frame the narration as walking through the official investigation "
        "report -- what investigators found, in the order they found it -- "
        "building to the root cause."
    ),
    "myth_vs_fact": (
        "Open by stating a common misconception people have about this "
        "incident, then spend the video systematically correcting it with "
        "what actually happened and why the myth took hold."
    ),
}


SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "narration": {"type": "string"},
        "thumbnail_text": {"type": "string"},
        "thumbnail_visual_prompt": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "visual_prompt": {"type": "string"},
                },
                "required": ["text", "visual_prompt"],
            },
        },
    },
    "required": [
        "title", "description", "tags", "narration",
        "thumbnail_text", "thumbnail_visual_prompt", "scenes",
    ],
}


def generate_script(client, config, topic, structure):
    word_min = config["script"]["min_words"]
    word_max = config["script"]["max_words"]
    prompt = f"""Write a narration script for a documentary-style YouTube video.

TOPIC: {topic}
NICHE: {config['channel']['niche']}
GUARDRAILS: {config['channel']['content_guardrails']}
STRUCTURE STYLE: {structure} -- {STRUCTURE_INSTRUCTIONS[structure]}

Requirements:
- {word_min}-{word_max} words of spoken narration.
- Written to be read aloud naturally by TTS -- short-to-medium sentences, no
  bullet points, no headers within the narration text itself.
- Factually accurate to publicly documented accounts of this incident.
- End with the concrete lesson, procedural change, or engineering standard
  that came out of the incident.
- Do NOT describe graphic injury/death detail. Focus on decisions, systems,
  timelines, and causes.
- Avoid using double-quote characters inside the narration text (write
  he said the bridge was failing instead of using quotation marks).

Also produce a scene breakdown: split the narration into 12-16 scenes. For
each scene give a short visual description suitable for an AI image
generator (documentary-illustration style, no real people's likenesses, no
graphic imagery).

Also write, in the high-CTR style used by popular history-documentary
YouTube channels (e.g. Mighty Monk, Fascinating Horror):
- thumbnail_text: 1-2 short punchy lines separated by a newline character.
  ALL CAPS, each line under 14 characters, as few words as possible while
  staying accurate (not misleading clickbait) -- e.g. "IGNORED\\nWARNING"
  or "167 DIED"
- thumbnail_visual_prompt: one dramatic visual description centered on an
  EXPRESSIVE ILLUSTRATED CHARACTER reacting to the unfolding disaster in
  the moment (e.g. a technician staring in shock at a warning light, an
  engineer looking up in horror at a failing structure) -- bold cinematic
  digital-illustration style, strong directional lighting, high contrast.
  NOT a real named person's likeness. No on-image text. No graphic injury
  detail.
"""
    response = client.models.generate_content(
        model=config["script"]["model"],
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCRIPT_SCHEMA,
            max_output_tokens=8192,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not response.text:
        raise RuntimeError(
            f"Gemini returned no text. finish_reason="
            f"{response.candidates[0].finish_reason if response.candidates else 'unknown'}"
        )
    return json.loads(response.text)


def generate_script_with_retry(client, config, topic, structure, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return generate_script(client, config, topic, structure)
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt}/{attempts} failed ({e}); retrying...")
            time.sleep(3)
    raise last_error


def main():
    config = load_config()
    topic = pop_next_topic()
    structure = pick_structure(config)
    print(f"Topic: {topic}\nStructure: {structure}")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    script_data = generate_script_with_retry(client, config, topic, structure)

    out_dir = ROOT / "data" / "current_video"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "script.json").write_text(json.dumps(script_data, indent=2))
    print(f"Script written to {out_dir / 'script.json'}")


if __name__ == "__main__":
    main()
