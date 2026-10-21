"""Generate the demo video's voice-over with Amazon Polly (neural Ruth, the app's narrator).

One MP3 per scene in voiceover/, named after the script's scene numbers. Re-run after editing a
line; unchanged lines are skipped, so each line is only paid for once.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import boto3

OUT = Path(__file__).resolve().parent / "voiceover"
VOICE = "Ruth"

LINES = {
    "1_hook": "Every child's drawing wants to come alive. Tonight, these four are going to be on TV.",
    "2_idea": "Doodle Theater turns a drawing on paper into a puppet on your Fire TV, and puts it in a "
              "bedtime story your child steers with the remote. No app to install, no account, no drawing tablet.",
    "3a_add": "A parent scans the code on the TV and snaps the drawing. Our open-source rigger, doodle-rig, "
              "cuts the character out, finds the joints, and builds a mesh. If a dot is off, you drag it.",
    "3b_send": "Press send, and... Queen Whiskers walks on stage.",
    "3c_fix": "A whole page of drawings? Tap the one you want. And if the cut-out misses a bit, "
              "paint it back, and the puppet is rebuilt.",
    "4_story": "Every line is narrated by Amazon Polly, with word timings driving the read-along highlight "
               "and the puppets' moves. Halfway through, the child decides what happens next.",
    "5_pause": "It behaves like real TV. Alexa, pause, stops the story mid-word, and it picks up right where it left off.",
    "6_dance": "And when the story's over... everybody dance!",
    "7a_built": "The story writer is a Strands agent built for Amazon Bedrock and Nova. It checks its own work "
                "with the same validator the TV uses, and Bedrock Guardrails keep every story gentle.",
    "7b_honest": "Our new AWS account was still waiting for Bedrock access during the build, so this demo plays "
                 "from our hand-written story set. It's the same offline fallback that keeps the show going when the network drops.",
    "7c_open": "The rigger is open source, under the M I T licence, and we logged every snag we hit along the way.",
    "6b_bedtime": "After seven, Bedtime mode turns the screen warm and dim, the narrator slows down, and every "
                  "story ends by saying goodnight to each star. A parent can even set how many stories are allowed tonight.",
    "8_close":"Doodle Theater. Every drawing gets its moment on stage.",
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    polly = boto3.client("polly", region_name="us-east-1")
    for name, text in LINES.items():
        mp3 = OUT / f"{name}.mp3"
        stamp = OUT / f"{name}.txt"
        tag = hashlib.sha1(f"{VOICE}|{text}".encode()).hexdigest()
        if mp3.exists() and stamp.exists() and stamp.read_text() == tag:
            continue
        audio = polly.synthesize_speech(Text=text, VoiceId=VOICE, Engine="neural", OutputFormat="mp3")
        mp3.write_bytes(audio["AudioStream"].read())
        stamp.write_text(tag)
        print("made", mp3.name)
    print("characters:", sum(len(t) for t in LINES.values()))


if __name__ == "__main__":
    main()
