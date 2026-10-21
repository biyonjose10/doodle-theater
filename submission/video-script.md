# Doodle Theater: demo video script and shot list

**Target: 2:45** (the hard limit is under 3:00). Upload to YouTube as **Public** or **Unlisted**,
whichever the rules accept; check Devpost.

**Rules this follows:** screen only, no face. **No copyrighted music**: use silence, or a track
from the **YouTube Audio Library** filtered to "No attribution required".

**Voice-over:** Amazon Polly reads the script (neural voice `Ruth`, the same narrator as the app).
On-brand, no recording booth needed, and it costs pennies from the AWS credit. Jarvis generates
the MP3s from the lines below. Alternative: on-screen captions only.

---

## Assets ready (2026-10-21) in `projects\doodle-video\`

- `clips\home_add.mp4` (B+D), `clips\party.mp4` (G), `clips\story_sound.mp4` (E, narration
  synced), `clips\pause_sound.mp4` (F). Trim the first ~12 s "Writing tonight's story" wait.
- `voiceover\*.mp3`, one per scene: `1_hook`, `2_idea`, `3a_add`, `3b_send`, `4_story`,
  `5_pause`, `6_dance`, `7a_built` + `7b_honest` (the Bedrock-pending version) + `7c_open`, `8_close`.
  If Bedrock starts working, replace `7b_honest` with a new line (edit `make_voiceover.py` and re-run).
- `images\diagram.png`, `images\endcard.png`, `images\rig_skeletons.png`, `images\cat_walk.gif`,
  `images\drawings_photo.webp`.

## What gets recorded, and who records it

| Clip | What | How | Who |
|---|---|---|---|
| A | The 4 paper drawings on the table | The photo you already have, slow zoom in editing | done |
| B | TV: Home screen → Add-a-star with QR | `adb shell screenrecord` on the emulator (free, 1080p, max 3 min per clip) | Jarvis |
| C | Phone: open the QR link → take photo → drag joint dots → name → Send | Built-in browser at phone size, recorded with **Snipping Tool → Record** (Win 11, free) | Jarvis sets it up, **you press record** |
| D | TV: the drawing walks in and waves with its name | screenrecord, same session as C | Jarvis |
| E | TV: pick "Under the Sea" → story plays with read-along + Polly voice → D-pad choice → The End | screenrecord | Jarvis |
| F | TV: pause mid-line with the media command ("Alexa, pause"), then resume | screenrecord + `adb shell cmd media_session dispatch pause/play` | Jarvis |
| G | TV: Dance party, everybody dance | screenrecord | Jarvis |
| H | Rig skeletons (the 4-up joint overlay) + walk GIF | Images already made | done |
| I | Architecture diagram (from the README) | Rendered to an image | Jarvis |
| J | End card: title, links, credits | Made as an image | Jarvis |

**Editing:** **Clipchamp** (built into Windows 11, free; export 1080p, no watermark on the free tier).
You assemble it, or Jarvis gives you an exact cut list with timestamps.

**Avoid on camera:** close-ups of **King Bloop with a raised arm** (dark smear glitch), and the end
screen where two name labels overlap. Pick takes where the stars stand apart.

---

## Script

### 1. Hook (0:00–0:12)
**Picture:** Clip A, slow zoom on the four paper drawings.
**VO:** "Every child's drawing wants to come alive. Tonight, these four are going to be on TV."
**Caption:** *Doodle Theater*

### 2. The idea (0:12–0:28)
**Picture:** Clip B, the Doodle Theater home screen; the cursor moves across the stars' cards.
**VO:** "Doodle Theater turns a drawing on paper into a puppet on your Fire TV, and puts it in a
bedtime story your child steers with the remote. No app to install, no account, no drawing tablet."

### 3. Add a star (0:28–1:00)
**Picture:** Clip B, Add-a-star with QR → Clip C, the phone page: photo, joint dots, name → Clip D on the
TV: Queen Whiskers walks in and waves.
**VO:** "A parent scans the code on the TV and snaps the drawing. Our open-source rigger, doodle-rig,
cuts the character out, finds the joints, and builds a mesh. If a dot is off, you drag it.
Press send, and..." *(beat)* "...Queen Whiskers walks on stage."
**Caption:** *Photo to puppet in about 2 seconds, rendered live at 60 fps*

### 4. Tonight's story (1:00–1:45)
**Picture:** Clip E: pick Under the Sea; the words light up as they're read; puppets act on cue
words; the choice screen; the remote picks "Swim through the kelp"; The End.
**VO:** *(let the app's own narration play for ~10 s, then duck it)*
"Every line is narrated by Amazon Polly, with word timings driving the read-along highlight and
the puppets' moves. Halfway through, the child decides what happens next."
**Caption:** *Polly neural voices · word speech marks · D-pad choices*

### 5. Made for the living room (1:45–1:58)
**Picture:** Clip F, pause mid-sentence, resume.
**VO:** "It behaves like real TV: 'Alexa, pause' pauses the story mid-word, and it picks up where it left off."

### 6. Dance party (1:58–2:08)
**Picture:** Clip G, everybody dances.
**VO:** "And when the story's over... everybody dance."

### 7. How it's built (2:08–2:38)
**Picture:** Clip I (diagram) → Clip H (skeleton overlay, walk GIF) → a glimpse of the Guardrail
script / FRICTION.md in the editor.
**VO (use the version that's TRUE on recording day):**

> **If Bedrock works by then:** "Behind the scenes, a Strands agent on Amazon Bedrock writes each
> story with Amazon Nova. It checks its own work with the same validator the TV uses, and fixes
> any mistakes before a child sees them. Bedrock Guardrails keep every story gentle. And if the
> network drops, the show goes on with hand-written stories."

> **If Bedrock is still blocked:** "The story writer is a Strands agent built for Amazon Bedrock
> and Nova, with Bedrock Guardrails keeping every story gentle. Our new AWS account was still
> waiting for Bedrock access during the build, so this demo plays from our hand-written story
> set. It's the same offline fallback that keeps the show going when the network drops."

"The rigger is open source under MIT, and we logged every snag we hit along the way."

### 8. Close (2:38–2:48)
**Picture:** Clip J, end card.
**VO:** "Doodle Theater. Every drawing gets its moment on stage."
**End card text:**
- Doodle Theater: Fire TV · Amazon Bedrock · Strands Agents · Amazon Polly
- github.com/biyonjose10/doodle-theater (the open-source rigger is in rig/)
- *Characters drawn by a neighbour's child, cleaned up with Gemini. Used with a parent's permission.*

---

## Your to-dos for the video

- [ ] Check the Devpost rules: Public vs Unlisted, and whether a voice-over by TTS is fine (it normally is).
- [ ] Thursday: record Clip C with Snipping Tool when Jarvis says "go" (about 1 minute).
- [ ] Assemble in Clipchamp, or ask for the cut list.
- [ ] Watch it once at full screen: under 3:00? No glitchy close-ups?
- [ ] Upload, then paste the link into Devpost.

---

## Clipchamp cut list

Every time below was checked against the files on 2026-10-21 (ffprobe for lengths, frame grabs
and silence detection for the moments). **Total: 2:18.5**, well under 3:00. If clip C comes out
longer or shorter than 12 s, everything after it simply shifts by the difference.

### Clipchamp in five steps (first time)

1. **Open it.** Start menu → type *Clipchamp* → **Create a new video**. Top left, click the
   project name and rename it *Doodle Theater*. Check the ratio button on the right says **16:9**.
2. **Import.** Left bar → **Your media** → **Import media**, then select everything in
   `projects\doodle-video\clips`, `images` and `voiceover` (only the `.mp3` files), plus your
   phone clip C. You can also drag files from File Explorer straight onto that panel.
3. **Put clips on the timeline.** Drag a clip from the media panel down onto the timeline at
   the bottom. Video and images go on the top row; drop each MP3 on the row **below** them, so it
   plays at the same time. Drop each new clip right after the previous one, with no gap.
4. **Trim to the times below.** Click a clip on the timeline, move the white playhead to the
   time you want, and press **S** (or the scissors icon) to split there; click the piece you
   don't want and press **Delete**. The time readout under the preview shows where the playhead
   is; zoom the timeline with **Ctrl + mouse wheel** for precise cuts. For an image, drag its
   right edge until it lasts the time given.
   - **Volume / mute:** click a clip → the **Audio** tab in the right-hand panel → volume slider
     (0% = mute).
   - **Speed:** click a clip → **Speed** tab on the right.
   - **Captions:** left bar → **Text** → drag a plain style onto the row above the video, then
     type in the right-hand panel.
   - **Fades:** click a clip → **Fade** tab on the right.
5. **Export.** Top right → **Export** → **1080p**. Watch the exported file once full screen
   before uploading.

"Duck" below means: split the app's own audio at the time given and lower that piece to the
volume given, so the voice-over is heard over it. Clipchamp has no automatic ducking.

### Timeline (video row)

"src" times are inside the source file; timeline times are in the finished video.

| # | Timeline | Source file | In → out (src) | Length | Notes |
|---|---|---|---|---|---|
| 1 | 0:00.0–0:07.0 | `images\drawings_photo.webp` | still | 7.0 s | Slow zoom if your Clipchamp has a zoom effect (right panel, **Effects**); otherwise leave it still. Fade in 0.5 s. |
| 2 | 0:07.0–0:19.5 | `clips\home_add.mp4` | 0.0 → 12.5 | 12.5 s | Home screen, focus moving across the stars and themes. No sound in this file. |
| 3a | 0:19.5–0:25.0 | `clips\home_add.mp4` | 12.5 → 18.0 | 5.5 s | *Add a star* opens; QR and code appear at src 14.0 (timeline 0:21.0). |
| 3C | 0:25.0–0:37.0 | **clip C (your phone recording)** | pick ~12 s | ~12 s | Keep in this order: photo taken → puppet moving on the phone → one joint dot dragged → name typed → **Send** tapped. Mute it. |
| 3b | 0:37.0–0:48.5 | `clips\home_add.mp4` | 22.5 → 34.0 | 11.5 s | "Waiting for a drawing…", then **"Queen Whiskers has arrived!" at src 24.2** (timeline 0:38.7); she walks in from the right until ~src 28 and waves from ~src 28.5. |
| 4a | 0:48.5–1:17.8 | `clips\story_sound.mp4` | 12.5 → 41.8 | 29.3 s | Skips the 12 s "Writing tonight's story" wait. Title card at src 13; narration starts src 14.9; "What should they do?" appears src 32.25; focus moves to *Swim through the kelp* src 35.75; kelp scene src 38.0. |
| 4b | 1:17.8–1:22.3 | `clips\story_sound.mp4` | 50.9 → 55.4 | 4.5 s | Jump to the last words: "The end!" (src 51.55) and the **The End** screen (src 52.1). Put a 0.3 s crossfade between 4a and 4b. |
| 5 | 1:22.3–1:30.4 | `clips\pause_sound.mp4` | 21.5 → 29.6 | 8.1 s | Space story. Professor Noodles' line "Look! A little star…" starts src 24.2; **Paused** at src 25.55 (timeline 1:26.35); resumes src 28.6 (timeline 1:29.4). **Out point must be 29.6**: the picture ends there even though the file's audio runs to 41.4 s. |
| 6 | 1:30.4–1:41.8 | `clips\party.mp4` | 18.5 → 29.9 | 11.4 s | Dance party; everybody starts dancing at ~src 22.75 (timeline 1:34.65). No sound in this file. |
| 7a | 1:41.8–1:53.3 | `images\diagram.png` | still | 11.5 s | Architecture diagram. Slow zoom if available. |
| 7b | 1:53.3–2:04.7 | `clips\story_sound.mp4` | 41.8 → 50.9 at **speed 0.8×** | 11.4 s | Part of the story not used in scene 4 (turtle and shell lines). **Mute it.** Caption below. |
| 7c | 2:04.7–2:08.3 | `images\rig_skeletons.png` | still | 3.6 s | The 4-up joint overlay. It is 1238×400, so it sits letterboxed; that's fine. |
| 7c | 2:08.3–2:11.5 | `images\cat_walk.gif` | whole GIF, twice | 3.2 s | The GIF is 1.6 s long: drop it on the timeline twice, back to back. |
| 8 | 2:11.5–2:18.5 | `images\endcard.png` | still | 7.0 s | Fade out the last 1.0 s (picture and sound). |

### Voice-over row

Drop each MP3 so it **starts** at the time given. None of them overlap.

| VO file | Length | Starts | Ends | Lands on |
|---|---|---|---|---|
| `1_hook.mp3` | 5.4 s | 0:00.5 | 0:05.9 | the drawings photo |
| `2_idea.mp3` | 11.2 s | 0:07.5 | 0:18.7 | the home screen |
| `3a_add.mp3` | 11.9 s | 0:20.5 | 0:32.4 | QR appears at 0:21.0, then the phone (clip C) |
| `3b_send.mp3` | 3.9 s | 0:37.0 | 0:40.9 | "Press send, and…" over the waiting screen; "…Queen Whiskers walks on stage" as she walks in (from 0:38.7) |
| `4_story.mp3` | 9.9 s | 0:58.6 | 1:08.5 | "Halfway through, the child decides…" ends as the choice appears (1:08.25) |
| `5_pause.mp3` | 7.1 s | 1:24.0 | 1:31.1 | "Alexa, pause" lands on the **Paused** badge (1:26.35); spills 0.7 s into the dance, which is fine |
| `6_dance.mp3` | 3.2 s | 1:32.6 | 1:35.8 | "everybody dance!" as they start dancing (1:34.65) |
| `7a_built.mp3` | 10.7 s | 1:42.2 | 1:52.9 | the diagram |
| `7b_honest.mp3` | 11.7 s | 1:53.3 | 2:05.0 | the muted story footage |
| `7c_open.mp3` | 5.9 s | 2:05.2 | 2:11.1 | skeletons, then the walking cat |
| `8_close.mp3` | 3.9 s | 2:12.0 | 2:15.9 | the end card |

### App narration (the sound inside `story_sound.mp4` and `pause_sound.mp4`)

- **Scene 4a:** full volume from 0:48.5 so the first line ("Down under the sea…", timeline
  0:50.9–0:58.0) plays clean with the read-along highlight. **Split at 0:58.3 and duck to 15%**
  until **1:08.6**, then split again and go back to **100%** (the choice screen is silent; the
  kelp line plays at full volume from 1:13.9).
- **Scene 4b:** 100%, so "The end!" is heard.
- **Scene 5:** 100% from 1:22.3 to 1:24.0, then **duck to 35%** to the end of the clip. Keep it
  audible: the point is that the voice stops dead at the pause (1:26.35) and comes back at
  1:29.4.
- **Scene 7b:** muted (0%).
- `home_add.mp4` and `party.mp4` have no sound. Optional: a quiet "No attribution required"
  track from the YouTube Audio Library under scenes 2, 3 and 6 at about 10%.

### Captions (Text row)

| Timeline | Text |
|---|---|
| 0:00.5–0:06.0 | Doodle Theater |
| 0:25.0–0:37.0 | Phone: no app, just the camera and a QR code |
| 0:39.0–0:46.0 | Photo to puppet in seconds, animated live on the TV *(say "about 2 seconds / 60 fps" only if you have measured it, e.g. on the Puppet Lab FPS readout)* |
| 0:59.0–1:08.0 | Polly neural voices · word speech marks · D-pad choices |
| 1:24.0–1:30.4 | Emulator: "Alexa, pause" sent as a media-session pause command |
| 1:53.3–2:04.7 | **If still blocked:** Demo stories: hand-written offline set, narrated by Amazon Polly. **If Bedrock works:** delete this caption, or swap in footage of a story the agent wrote. |

### If Bedrock starts working before you record

Re-generate `7b_honest.mp3` with the "If Bedrock works" line (edit `make_voiceover.py`, re-run),
check its new length, and stretch or shorten scene 7b to match by changing the speed (0.8× gives
11.4 s, 0.9× gives 10.1 s, 1.0× gives 9.1 s). Everything after it shifts by the difference.

### Before you export, check

- Scene 4a around 1:07–1:08, and scene 6 from 1:34 on: King Bloop raises his arms there. In
  these wide shots the dark smear is small, but look at it full screen. If it bothers you, end
  scene 6 at src 27.0 instead of 29.9 (saves 2.9 s).
- Clip C: no notifications, no other tabs, no personal details on screen.
- Total under 3:00 (this plan: 2:18.5, plus or minus clip C).
