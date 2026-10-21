# Doodle Theater: Devpost write-up

> **Submission checklist (delete this box before pasting):**
> - [ ] **Video:** upload (under 3:00), then paste the link into the Devpost video field: `VIDEO_LINK_HERE`
> - [ ] **Repo public:** `github.com/biyonjose10/doodle-theater` (the rigger is in `rig/`) was
>   **private** on 2026-10-21. Run the leak-checker, then make it public before submitting. The
>   Open Source mini challenge needs a public repo. There is no separate doodle-rig repo any more
>   (the old one is archived), so link only this one.
> - [ ] **Pick variants:** every `[IF STILL BLOCKED]` / `[IF BEDROCK WORKS]` pair below: keep the
>   one that is true on submission day, delete the other and the square-bracket labels.
>   `[IF STILL BLOCKED]` is the current truth (21 Oct). Keep `[IF OLLAMA PATH IS DONE]` lines only
>   if `DT_STORY_MODEL=ollama:qwen3:8b` is committed and has produced a story end to end.
> - [ ] **Built-with tags:** paste the list under *Built with* into the Devpost tag field one by one.
> - [ ] **Try it out link:** `https://github.com/biyonjose10/doodle-theater` (there is no hosted
>   demo; the server runs on a laptop on the home network).

---

## Project name
Doodle Theater

## Tagline (under 200 characters)
A child's paper drawing becomes a live puppet on Fire TV and stars in a bedtime story they steer
with the remote. The parent's phone just scans a QR code.

---

## Inspiration

Children draw characters all the time, and the drawings usually end up on the fridge. Meta's
AnimatedDrawings showed how much fun it is to see one move, but it is now archived, needs a
detection model in Docker and renders with desktop OpenGL. We wanted that moment on the screen a
family already gathers around at bedtime, with nothing to install and no account to make.

## What it does

1. **Add a star.** The TV shows a QR code. A parent scans it (a web page, no app) and
   photographs the drawing.
2. **Rig.** The photo becomes a puppet: cut-out texture, triangle mesh, 16-joint skeleton, skin
   weights. The phone shows it moving, and any joint that looks wrong can be dragged into place.
   Name it, tap *Send to the TV*.
3. **Perform.** The drawing walks onto the TV and waves. Puppets are deformed every frame with
   `Canvas.drawVertices`, so they move live (walk, run, jump, wave, dance, spin and more) instead
   of playing a pre-rendered video.
4. **Tonight's story.** The child picks one of six themes. The cast acts out a short play with
   one D-pad choice halfway through and two happy endings. Amazon Polly narrates each line, the
   spoken word lights up for read-along, and stage directions fire on their cue word ("jumped"
   makes the puppet jump).
5. **Living-room controls.** OK makes a star jump, ⏯ pauses. The story player owns a
   `MediaSession`, so transport commands such as "Alexa, pause" can reach it (tested on the
   emulator with a media-session pause command).
6. **Dance Party.** Every star on stage at once, and everybody dances.

Drawings, rigs and episodes are stored only on the laptop running the server.

## How we built it

- **TV app:** Kotlin, Jetpack Compose for TV, `minSdk 25` (Fire OS 6+), with a small renderer
  that poses each puppet from its rig JSON.
- **Server:** Python and FastAPI on a laptop on the home network: pairing, photo-to-puppet,
  stories and narration.
- **Puppets:** **doodlerig**, our open-source rigger, in the repo's `rig/` folder (below).
- **Story writer:** a **Strands agent** with three tools. Its `submit_episode` tool runs the same
  check the TV relies on and returns the problems as text, so the agent fixes unknown moves or
  missing cue words and resubmits until the episode is accepted.
- **Safety:** a **Bedrock Guardrail** (`doodle-theater-kids`, created by script) with
  high-strength content filters and denied topics for scary content and a child's personal
  details.
- **Voice:** **Amazon Polly** neural voices, a narrator plus child voices for characters' own
  lines, with word speech marks driving the highlight and the cue-word actions.
- **Offline first:** every AI step has a non-AI fallback: doodlerig's silhouette heuristic for
  joints, six hand-written branching stories, the TV's own text-to-speech, and 18 crayon
  backdrops drawn in code.

**What is live today**

[IF STILL BLOCKED:] Polly is live: neural voices and word speech marks work end to end, and the
TV plays the narration with the read-along highlight. The Guardrail has been created on our
account. The Strands agent and the Bedrock vision step are written and wired (the agent's
fallbacks are covered by tests), but our new AWS account (India, Free plan) gets `Operation not allowed` on every Bedrock
model call. We filed a support case for Bedrock access on 21 October. Until it is granted, the
demo stories come from the hand-written set, narrated by Polly, and joints come from doodlerig's
heuristic. [IF OLLAMA PATH IS DONE:] The same Strands agent also runs on a local model through
Ollama (`DT_STORY_MODEL=ollama:qwen3:8b`), which shows the write-check-repair loop working.

[IF BEDROCK WORKS:] The story agent runs on Amazon Nova 2 Lite through Bedrock with the
Guardrail attached, and Polly narrates every line. The hand-written stories take over if the
network or a model call fails.

## Challenges we ran into

- **No Vega on Windows.** The Vega SDK supports macOS and Ubuntu only, so we built for Fire OS.
- **The official Kotlin Fire TV sample pins 2023-era dependencies.** Upgrading meant rebuilding
  the Gradle setup, then 28 dependency errors until we pinned compatible versions.
- **"Alexa, pause" went nowhere at first.** A media session only receives media buttons if the
  app itself plays audio, and system text-to-speech plays in another process. We now render
  speech to a file and play it with our own `MediaPlayer`.
- **Polly's speech marks are UTF-8 byte offsets** while the TV counts characters, so a curly
  apostrophe would shift every later highlight. We convert every mark.
- **Both feet on one leg.** When one foot reached lower and across the body's centre line (a
  kicking cat, a robot), the rigger put both feet on the same leg. It now follows the legs up
  from the feet instead.
- **AWS onboarding from India:** a UPI AutoPay mandate, DigiLocker KYC, then an "account being
  verified" wait before the first model call. [IF STILL BLOCKED: After that, every Bedrock model
  call was refused with "Operation not allowed", an error that does not say an allowlisting
  support case is the way through.] Each step is in our friction log.

## Accomplishments that we're proud of

- A photo of a paper drawing becomes a puppet that moves live on a TV, not a rendered video.
- The story agent checks its own work with the TV's validator before anything reaches a child.
- The whole show still runs on a home network with no AWS account and no internet.
- doodlerig stands on its own as an MIT library with 26 tests.

## What we learned

- Fire OS is Android: standard Android Studio, ADB and Compose all applied, no Fire-specific SDK.
- Giving an agent a tool that runs your real validator is a simple way to make it repair its
  own mistakes.
- Design for "the AI is unavailable" from day one. Our account setup showed why.

## What's next

- Test on a physical Fire TV stick. So far it is built and tested on the Android TV emulator
  (1080p), which the hackathon FAQ allows.
- [IF STILL BLOCKED:] Switch the story agent and vision step to Bedrock as soon as access is
  granted, and update the feedback with live results.
- Vega OS, once its tools run on Windows.

## Built with

kotlin, jetpack-compose, compose-for-tv, android, fire-tv, python, fastapi, uvicorn, numpy,
opencv, scipy, pillow, webgl, javascript, amazon-bedrock, amazon-nova, strands-agents,
bedrock-guardrails, amazon-polly, boto3 [IF OLLAMA PATH IS DONE: , ollama]

---

## Try it

- **Repo:** https://github.com/biyonjose10/doodle-theater
- **Rigger (open source, MIT):** https://github.com/biyonjose10/doodle-theater/tree/main/rig

Short version (full steps in the README):

1. **Server:** Python 3.10+. In `server/`, create a venv, install the packages listed in the
   README and `pip install -e ../rig`, then run
   `python -m uvicorn doodle_theater.app:app --host 0.0.0.0 --port 8787`.
2. **TV app:** JDK 17 + Android SDK. In `tv/`, run `gradlew installDebug` on an Android TV
   emulator or a Fire TV with ADB debugging on. The emulator reaches the laptop at
   `http://10.0.2.2:8787`; for a real Fire TV, set `SERVER_URL` to the laptop's LAN address.
3. **Phone:** on the TV choose *Add a star* and scan the QR code.
4. **AWS (optional):** with no credentials everything runs on the offline fallbacks. With
   credentials for Bedrock and Polly in `us-east-1`, run `python scripts/make_guardrail.py` once
   from `server/`.
5. To simulate "Alexa, pause" on the emulator: `adb shell cmd media_session dispatch pause`.

---

## Open Source mini challenge: doodlerig

**doodlerig** (in `rig/` of the Doodle Theater repo, installable on its own with
`pip install "git+https://github.com/biyonjose10/doodle-theater#subdirectory=rig"`) turns a photo
of a hand-drawn character into a rigged 2D puppet that any renderer can animate. It finds the
paper, then the ink, cuts the character out, guesses a 16-joint skeleton, builds a triangle mesh
and computes geodesic skin weights, so a hand drawn near the belly follows the arm, not the
torso. The output is a small documented JSON file (posing maths in `rig/SCHEMA.md`) plus a
transparent texture.

- **No model required:** pure Python (NumPy, OpenCV, SciPy, Pillow). A vision model can plug in
  through `joint_provider=`, which is how Doodle Theater adds Bedrock.
- **Renderer-agnostic:** a WebGL player ships in `rig/web/`; Doodle Theater has a Kotlin one.
- **Interoperable:** joint names match AnimatedDrawings, with converters both ways.
- **26 tests:** segmentation against reference masks, joints near hand-made annotations, mesh
  inside the drawing, normalised weights, every motion, save/load round-trips, and
  JavaScript-vs-Python posing parity.
- **The leg-following fix:** feet used to be found by splitting the silhouette at its centre
  line. A kicking cat, or a robot whose centre line ran down one leg, ended up with both feet on
  the same leg. Now the two lowest-reaching pieces of the silhouette are taken as the legs and
  followed up to where they join; the old split stays as the fallback for dresses and blobs.
- **MIT licence.**

## AWS Builder mini challenge: Bedrock + Strands

- **Strands agent** (`server/doodle_theater/story/agent.py`) with three `@tool` functions. The
  `submit_episode` tool is a validated-final-answer loop: the TV's own validator runs inside the
  tool, and the agent repairs and resubmits until it gets ACCEPTED. The server validates the
  result again and falls back to the hand-written stories if it still fails.
- **Amazon Bedrock**, Converse API, **Amazon Nova 2 Lite** for both the story agent and the
  joint-finding vision step (`server/doodle_theater/vision.py`). Every vision proposal is checked
  against the cut-out mask.
- **Bedrock Guardrails** passed to the agent's `BedrockModel` (`guardrail_id`,
  `guardrail_version`), created by `server/scripts/make_guardrail.py` and found by name.
- **Amazon Polly** neural voices with word speech marks.

[IF STILL BLOCKED:] Polly runs live in the demo, and the Guardrail was created on our account.
Bedrock model invocation has been blocked on our new account ("Operation not allowed"; support
case filed 21 October), so the agent and vision code are written and wired but have not yet run
against a live model, and the demo stories come from the offline set. [IF OLLAMA PATH IS DONE:] The same agent
runs on a local Ollama model to show the loop working.

[IF BEDROCK WORKS:] All four run live in the demo.

## Friction log and feedback

- **Friction log:** `docs/FRICTION.md`, written while building, not afterwards. Eleven entries
  with severity, steps, expected vs actual, workaround and a suggestion: three Fire TV issues
  (Vega SDK on Windows, the outdated Kotlin sample, no Fire OS emulator and the media-session
  trap) and eight AWS ones (signup redirects, $0 credits, Indian KYC, Free plan model access,
  Nova Canvas missing, no CLI on Windows, the Bedrock verification wait, and the unexplained
  "Operation not allowed" Bedrock block).
- **Product feedback:** `docs/FEEDBACK.md`, per tool (Fire TV, Bedrock, Strands, Polly,
  Guardrails, account onboarding): what worked, what hurt, and specific suggestions, with a
  status note on what is verified live.

---

## Credits

Characters drawn by a neighbour's child and cleaned up with Gemini, used with a parent's
permission. Their names were chosen by the author.

Baloo 2 font under the SIL Open Font License 1.1. The sample puppets bundled with the app are
built from drawings in Meta's AnimatedDrawings (MIT).
