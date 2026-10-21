"""Settings, all overridable by environment variables (see server/.env.example)."""
from __future__ import annotations

import os
import socket
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DT_DATA", SERVER_DIR / "data"))
STATIC = SERVER_DIR / "static"
PORT = int(os.environ.get("DT_PORT", "8787"))

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Vision (joints + one-line description) and story writing. Any Bedrock Converse model id or
# inference profile works; DT_*_MODEL=off disables that feature (offline fallbacks take over).
# Amazon Nova by default: first-party, so it also runs on AWS Free plan accounts.
VISION_MODEL = os.environ.get("DT_VISION_MODEL", "us.amazon.nova-2-lite-v1:0")
STORY_MODEL = os.environ.get("DT_STORY_MODEL", "us.amazon.nova-2-lite-v1:0")
# DT_STORY_MODEL=ollama:qwen3:8b runs the same story agent on a local Ollama model instead.
OLLAMA_HOST = os.environ.get("DT_OLLAMA_HOST", "http://127.0.0.1:11434")
# Empty = use the guardrail named GUARDRAIL_NAME, which scripts/make_guardrail.py creates.
GUARDRAIL_ID = os.environ.get("DT_GUARDRAIL_ID", "")
GUARDRAIL_NAME = "doodle-theater-kids"
GUARDRAIL_VERSION = os.environ.get("DT_GUARDRAIL_VERSION", "DRAFT")
NARRATOR_VOICE = os.environ.get("DT_NARRATOR_VOICE", "Ruth")


def lan_ip() -> str:
    """The laptop's address on the Wi-Fi, which the parent's phone must reach. No packets are sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def public_url() -> str:
    return os.environ.get("DT_PUBLIC_URL") or f"http://{lan_ip()}:{PORT}"
