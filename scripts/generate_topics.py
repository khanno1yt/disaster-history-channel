"""
Keeps data/topics_queue.json stocked so the pipeline never runs dry.
Called automatically by run_pipeline.py when the queue drops below MIN_QUEUE_SIZE.

Uses Google's Gemini API free tier (no cost, no credit card).
"""
import json
import os
from pathlib import Path

import yaml
from google import genai

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "data" / "topics_queue.json"
CONFIG_PATH = ROOT / "config.yaml"
MIN_QUEUE_SIZE = 5
BATCH_SIZE = 15


def load_queue():
    with open(QUEUE_PATH) as f:
        return json.load(f)


def save_queue(data):
    with open(QUEUE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def generate_new_topics(client, config, existing_titles):
    prompt = f"""You are researching topics for a documentary-style YouTube channel about
{config['channel']['niche']}.

Content guardrails: {config['channel']['content_guardrails']}

Generate {BATCH_SIZE} NEW topic ideas (real historical incidents, well-documented,
with a settled official cause) that are NOT in this list of already-used or
queued topics:

{chr(10).join('- ' + t for t in existing_titles)}

Rules:
- Each topic must be a real, verifiable historical incident.
- Avoid duplicating the same incident with a different title.
- Skew toward incidents with strong investigative/engineering-lesson angles
  (design flaws, procedural failures, decision-making chains) rather than
  just "what happened" -- this makes for better long-form narration.
- Avoid events from the last 5 years unless the official investigation is
  fully published and well covered already.

Format each topic like: "Short Name (Year) - one-line hook" (use a hyphen,
not a colon or quotation marks, to avoid breaking JSON formatting).
"""
    response = client.models.generate_content(
        model=config["script"]["model"],
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={"type": "array", "items": {"type": "string"}},
            max_output_tokens=2048,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not response.text:
        raise RuntimeError(
            f"Gemini returned no text. finish_reason="
            f"{response.candidates[0].finish_reason if response.candidates else 'unknown'}"
        )
    return json.loads(response.text)


def main():
    queue_data = load_queue()
    if len(queue_data["queue"]) >= MIN_QUEUE_SIZE:
        print(f"Queue has {len(queue_data['queue'])} topics, no refill needed.")
        return

    config = load_config()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    existing = queue_data["queue"] + queue_data["used"]
    new_topics = generate_new_topics(client, config, existing)

    queue_data["queue"].extend(new_topics)
    save_queue(queue_data)
    print(f"Added {len(new_topics)} new topics. Queue size now {len(queue_data['queue'])}.")


if __name__ == "__main__":
    main()
