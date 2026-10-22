<!-- Ready to paste into Devpost: the "Bedrock still blocked" version of devpost.md. Paste each section into the matching Devpost field. -->

# Doodle Theater: Devpost write-up

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
   weights. If the photo holds several drawings, the phone shows each one and the child taps the
   star. The phone shows the puppet moving. A missing hand or a bit of leftover paper can be fixed
   with an Erase/Add brush, and any joint that looks wrong can be dragged into place. Name it,
   tap *Send to the TV*.
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
7. **Made for bedtime.** From 7 PM (or with the 🌙 chip) the screen turns warm and dim, Polly
   narrates slower and softer, and stories avoid scary or running moves. Every story ends with a
   wind-down: the stage dims to night and the narrator says goodnight to each star by name. A
   parent can cap "stories tonight" at 1, 2 or 3. We pitch this as a calmer routine, not a sleep aid.
8. **Picture choices.** Each option has a picture and a LEFT/RIGHT badge, so pre-readers can choose.

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

Polly is live: neural voices and word speech marks work end to end, and the
TV plays the narration with the read-along highlight. The Guardrail has been created on our
account. The Strands agent and the Bedrock vision step are written and wired (the agent's
fallbacks are covered by tests), but our new AWS account (India, Free plan) gets `Operation not allowed` on every Bedrock
model call. We filed a support case for Bedrock access on 21 October. Until it is granted, the
demo stories come from the hand-written set, narrated by Polly, and joints come from doodlerig's
heuristic.

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
  verified" wait before the first model call. After that, every Bedrock model
  call was refused with "Operation not allowed", an error that does not say an allowlisting
  support case is the way through. Each step is in our friction log.

## Accomplishments that we're proud of

- A photo of a paper drawing becomes a puppet that moves live on a TV, not a rendered video.
- The story agent checks its own work with the TV's validator before anything reaches a child.
- The whole show still runs on a home network with no AWS account and no internet.
- doodlerig stands on its own as an MIT library with 49 passing tests, plus 6 marked as known gaps.

## What we learned

- Fire OS is Android: standard Android Studio, ADB and Compose all applied, no Fire-specific SDK.
- Giving an agent a tool that runs your real validator is a simple way to make it repair its
  own mistakes.
- Design for "the AI is unavailable" from day one. Our account setup showed why.

## What's next

- Test on a physical Fire TV stick. So far it is built and tested on the Android TV emulator
  (1080p), which the hackathon FAQ allows.
- Switch the story agent and vision step to Bedrock as soon as access is
  granted, and update the feedback with live results.
- Vega OS, once its tools run on Windows.

## Built with

kotlin, jetpack-compose, compose-for-tv, android, fire-tv, python, fastapi, uvicorn, numpy,
opencv, scipy, pillow, webgl, javascript, amazon-bedrock, amazon-nova, strands-agents,
bedrock-guardrails, amazon-polly, boto3

---

## Submission form fields

- **Primary track:** Fire TV (runs on Fire OS; the demo is on the Android TV emulator, which the
  hackathon FAQ allows).
- **Mini challenges:** AWS Builder, Open Source.
- **Code repository:** https://github.com/biyonjose10/doodle-theater (public, MIT licence).
- **Open Source contribution URL:** https://github.com/biyonjose10/doodle-theater/tree/main/rig
- **Open Source project repository URL:** https://github.com/biyonjose10/doodle-theater
- **GitHub username:** biyonjose10

## Try it

- **Repo:** https://github.com/biyonjose10/doodle-theater (setup steps in `docs/QUICKSTART.md`)
- **TV app:** https://github.com/biyonjose10/doodle-theater/releases/tag/v1.0.0
  (`doodle-theater-tv.apk`)
- **Rigger (open source, MIT):** https://github.com/biyonjose10/doodle-theater/tree/main/rig

Short version:

1. **Server:** Python 3.10+. Run `run.ps1` (Windows) or `run.sh` (macOS/Linux) from the repo root.
   It creates the virtual environment, installs everything and starts the server on port 8787.
2. **TV app:** `adb install doodle-theater-tv.apk` on the Android TV emulator or a Fire TV with
   ADB debugging on. The emulator finds the laptop by itself. On a real Fire TV, enter the
   laptop's address on the *Set server address* screen with the remote.
3. **No drawing handy?** Choose *Try sample stars* on the TV.
4. **Phone:** on the TV choose *Add a star*, scan the QR code and photograph a drawing.
5. **AWS (optional):** with no credentials everything runs on the offline fallbacks. With
   credentials for Bedrock and Polly in `us-east-1`, run `python scripts/make_guardrail.py` once
   from `server/`.
6. To simulate "Alexa, pause" or "Alexa, next" on the emulator:
   `adb shell cmd media_session dispatch pause` (or `next` / `previous` at a story choice).

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
- **Robust cut-out:** shadows across the page are flattened, small gaps in an outline are sealed
  instead of leaking, and pale crayon is found by colour, not just darkness. Edges are
  anti-aliased. `find_characters()` returns every drawing on a sheet, and
  `extract_character(box=...)` cuts out the chosen one.
- **49 passing tests, plus 6 marked as known gaps:** segmentation against reference masks, synthetic
  photos with known true shapes (shadows, gaps, pale crayon, two drawings on one sheet), joints near hand-made annotations, mesh
  inside the drawing, normalised weights, every motion, save/load round-trips, and
  JavaScript-vs-Python posing parity.
- **The leg-following fix:** feet used to be found by splitting the silhouette at its centre
  line. A kicking cat, or a robot whose centre line ran down one leg, ended up with both feet on
  the same leg. Now the two lowest-reaching pieces of the silhouette are taken as the legs and
  followed up to where they join; the old split stays as the fallback for dresses and blobs.
- **MIT licence.**

**Why it matters:** Meta's AnimatedDrawings showed how much children love seeing their drawings
move, but it is archived, needs a detection model in Docker and renders with desktop OpenGL.
doodlerig does the same job in plain Python with no model and no GPU, and its output is a small
JSON file any renderer can play: a TV, a phone browser, a game engine. It was written during the
hackathon window (first commit 19 October 2026) and is the core of Doodle Theater.

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

Polly runs live in the demo, and the Guardrail was created on our account.
Bedrock model invocation has been blocked on our new account ("Operation not allowed"; support
case filed 21 October), so the agent and vision code are written and wired but have not yet run
against a live model, and the demo stories come from the offline set.

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
