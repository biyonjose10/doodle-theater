"""Create the Bedrock Guardrail that screens every story prompt and every story the agent writes.

Run once per AWS account:  .venv/Scripts/python.exe scripts/make_guardrail.py
The server finds it by name, so no setting is needed. Creating a guardrail is free; each check is
billed per 1,000 characters screened.
"""
from __future__ import annotations

import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doodle_theater.config import AWS_REGION, GUARDRAIL_NAME as NAME  # noqa: E402
BLOCKED = "That story isn't right for bedtime. Let's pick a different adventure!"

FILTERS = [{"type": t, "inputStrength": "HIGH", "outputStrength": "HIGH"}
           for t in ("SEXUAL", "VIOLENCE", "HATE", "INSULTS", "MISCONDUCT")]
FILTERS.append({"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"})

TOPICS = [
    {"name": "Scary content", "type": "DENY",
     "definition": "Horror, monsters that hurt people, death, injury, blood, or anything meant to frighten a young child.",
     "examples": ["The monster ate the children.", "Write a ghost story where someone dies."]},
    {"name": "Personal information", "type": "DENY",
     "definition": "Asking for or revealing a child's real address, school, phone number or other identifying details.",
     "examples": ["What school do you go to?", "Tell me where you live."]},
]


def main() -> None:
    bedrock = boto3.client("bedrock", region_name=AWS_REGION)
    existing = [g for g in bedrock.list_guardrails()["guardrails"] if g["name"] == NAME]
    if existing:
        print(f"Already exists. DT_GUARDRAIL_ID={existing[0]['id']}")
        return
    g = bedrock.create_guardrail(
        name=NAME,
        description="Keeps Doodle Theater bedtime stories gentle and safe for ages 3 to 8.",
        contentPolicyConfig={"filtersConfig": FILTERS},
        topicPolicyConfig={"topicsConfig": TOPICS},
        wordPolicyConfig={"managedWordListsConfig": [{"type": "PROFANITY"}]},
        blockedInputMessaging=BLOCKED,
        blockedOutputsMessaging=BLOCKED,
    )
    print(f"Created. DT_GUARDRAIL_ID={g['guardrailId']}  (version DRAFT)")


if __name__ == "__main__":
    main()
