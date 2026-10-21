# Product feedback

Feedback on each Amazon tool we used to build Doodle Theater, based on the issues logged live in
[FRICTION.md](FRICTION.md) and on what the code had to do to work around them. Entry numbers
like (F3) refer to that file.

**Status note (2026-10-21):** the Fire TV app has been run end to end on the Android TV emulator.
The AWS path (Bedrock vision, the Strands story agent, Polly, Guardrails) is written and wired,
and its fallbacks are covered by tests, but every episode and rig produced so far came from the
offline path while the AWS account was being set up. Points about the AWS tools below come from
building against their APIs and docs, not yet from production use, and will be updated after the
first live runs.

---

## Fire TV / Fire OS development

**What worked well**
- Fire OS is Android, so standard Android Studio, Gradle, ADB and Jetpack Compose all apply. The
  TV app is one Kotlin activity with no Fire-specific SDK.
- The leanback manifest flags, banner and `androidx.tv:tv-material` give a TV-ready app with D-pad
  focus handling for free.
- Hardware-accelerated `Canvas.drawVertices` was fast enough to deform every puppet's mesh each
  frame, so characters animate live instead of from pre-rendered video.
- A plain `MediaSession` is the route for remote ⏯ and Alexa transport commands; no extra SDK.

**What hurt**
- The Vega SDK supports macOS and Ubuntu only, so a Windows-only developer cannot target Vega OS
  at all (F1).
- The official Kotlin sample, `hello-world-fire-tv`, pins 2023-era Compose and Gradle setup.
  Upgrading meant rewriting the Gradle plugin setup, and the newest AndroidX releases then needed
  AGP 9.1 and `compileSdk 37`, failing with 28 dependency errors until we pinned
  `compose-bom:2025.06.01` and `tv-material:1.0.1` (F2).
- There is no Fire OS emulator image. The Android TV emulator cannot exercise the Amazon
  launcher, Alexa voice routing or Appstore services (F3).
- Not documented: a media session only receives media buttons if the app itself plays audio.
  Our narration used the system TextToSpeech, which plays in the engine's process, so Alexa
  commands went nowhere until we rendered speech to a file and played it with our own
  `MediaPlayer` (F3).

**Suggestions**
- Ship Vega tooling that runs on Windows: a devcontainer/VVD image, official WSL2 support, or a
  browser simulator.
- Keep the sample repos current with Renovate/Dependabot and a CI build against the latest stable
  AGP, and note which Compose for TV versions pair with which AGP.
- Publish a Fire OS emulator image in the Android Studio SDK Manager, even without DRM video.
- In the media-session guide, state which app receives Alexa transport commands and give an
  emulator test recipe such as `adb shell cmd media_session dispatch pause`.

---

## Amazon Bedrock

**What worked well**
- The Converse API is the same for every model. Moving the vision and story steps from Claude
  Haiku to Amazon Nova 2 Lite was a change of model id in `config.py`, nothing else (F7).
- One Converse call takes an image and text together, which is all the joint-finding step needs.

**What hurt**
- On a Free plan account, it was unclear which models we could use. Anthropic models need a
  use-case form, and the Free plan appears to block AWS Marketplace models, but no single page
  said so (F7).
- Nova Canvas did not appear in the us-east-1 foundation model list for this account, with no
  reason shown (F8).
- Unavailability only shows up as an exception at call time. Our code has to treat "no access",
  "throttled" and "no credentials" the same way and fall back.

**Suggestions**
- In the model catalog, show per account whether each model is callable, and if not, why (plan,
  form pending, region, not yet requested).
- Add a cheap API such as `CanInvokeModel(modelId)` so apps can pick a working model at startup.

---

## Strands Agents

**What worked well**
- The `@tool` decorator turned three plain Python functions into tools, with docstrings as the
  descriptions.
- `BedrockModel` takes `guardrail_id` and `guardrail_version` directly, so adding Guardrails was
  two keyword arguments.
- The agent loop suits self-correction: `submit_episode` runs the same validator the TV uses and
  returns the problems as text, and the system prompt tells the agent to fix and resubmit until
  it gets ACCEPTED. The server validates the result again and falls back to templates if it
  still fails.

**What hurt**
- The agent's return value is free text, so we capture the accepted episode in a closure inside
  the `submit_episode` tool. It works, but it is a pattern we had to invent.
- The default callback handler prints the model's output to stdout; inside a web server we had
  to pass `callback_handler=None`.

**Suggestions**
- Document a "validated final answer" pattern: a tool whose acceptance ends the run and becomes
  the agent's result.
- Add a limit on how many times one tool can be called per run, for retry loops like ours, and
  document it next to the tool examples.

---

## Amazon Polly

**What worked well**
- The neural voice list includes child voices (Ivy, Justin, Kevin), so characters' own lines
  can sound different from the narrator.
- Word speech marks give the timing we need for the read-along highlight and for firing a
  puppet action on its cue word.

**What hurt**
- Speech mark `start`/`end` are byte offsets into the UTF-8 text. The TV indexes characters, so
  we convert every mark (`server/doodle_theater/story/voice.py`); without that, any non-ASCII
  character (an apostrophe, an accented name) shifts every later highlight.
- Audio and speech marks need two separate `SynthesizeSpeech` calls with the same text and voice,
  doubling requests per line.

**Suggestions**
- Return audio and speech marks from one call, for example as a multipart response or a marks
  header.
- Add an option to report character offsets (or UTF-16 offsets, which Android and JavaScript
  strings use).

---

## Amazon Bedrock Guardrails

**What worked well**
- Integration is one setting: the guardrail id and version passed to the agent's Bedrock model
  apply to both what goes in (theme, character names typed by the parent, drawing descriptions)
  and what comes out.
- Because the story path already falls back to hand-written templates on any error, a blocked
  request never leaves a child with a broken screen.

**What hurt**
- The guardrail is a separate resource created outside the code, so the app depends on an id
  configured per account (`DT_GUARDRAIL_ID`), and by default runs without one.
- Configuring one for a children's audience means choosing every filter and threshold by hand.

**Suggestions**
- Offer a ready-made "content for young children" guardrail preset.
- Make it easier to tell a guardrail block apart from other failures in agent frameworks, so apps
  can log and react to it specifically.

---

## AWS account onboarding

**What worked well**
- boto3 reads the standard credentials file, so the app needs no AWS settings in code; it
  switches its AI path on when credentials are present and off when they are not.

**What hurt**
- An old account with an unfinished signup sent Bedrock, IAM and Billing to one generic
  *Complete your account setup* page that did not say which step was missing, or whether the
  issue was the signup or the Free plan (F4).
- The credits page showed $0 until signup was finished (F5).
- Indian signup needed a UPI AutoPay mandate (₹15,000 limit shown) and DigiLocker KYC whose OTP
  goes to the Aadhaar-linked mobile, not the phone number given to AWS (F6).
- The AWS CLI is not installed on Windows, so `aws configure` was not available; we wrote the
  credentials with a small local pop-up instead (F9).

**Suggestions**
- Name the missing signup step on the blocking page and link to it.
- Show "credits appear after setup" instead of $0.
- Warn before KYC that the OTP goes to the Aadhaar-linked number, and explain the mandate limit
  is a ceiling, not a charge.
- Show the credentials file format next to a new access key.
