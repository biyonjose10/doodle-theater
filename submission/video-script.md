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

This matches the rendered `final\doodle-theater-demo.mp4` (built by `build_video.py`; every time
was checked on the render on 2026-10-21 with frame grabs and silence detection). **Total:
2:35.3**, well under 3:00. You only need it if you rebuild the video by hand in Clipchamp.

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

"src" times are inside the source file; timeline times are in the finished video. Clips were
re-recorded on 2026-10-21 with the new TV UI and phone page (first takes kept as `clips\*_v1.mp4`).
"xfade" = a crossfade of that length from the previous row.

| # | Timeline | Source file | In → out (src) | Length | Notes |
|---|---|---|---|---|---|
| 1 | 0:00.0–0:07.5 | `images\drawings_photo.webp` | still | 7.5 s | Slow zoom 1.0→1.12. Fade in 0.6 s. |
| 2 | 0:07.0–0:24.5 | `clips\home_add.mp4` | 1.5 → 12.0, then 12.0 → 18.0 at **3×**, then 18.0 → 23.0 | 17.5 s | xfade 0.5. Daytime Home (Bedtime OFF): focus over the stars with the ★ Selected tag (src 2.5–7), the themes (7.5–11); back to *Add a star* (sped up); Add a star opens src 19.5, **QR at src 20.5 (timeline 0:22.0)**. No sound in this file. |
| 3C | 0:24.2–0:37.7 | `clips\phone.mp4` | 4.3 → 9.25; 11.9 → 17.5 at **1.5×**; 17.5 → 22.3 | 13.5 s | xfade 0.3. Top 182 px (status + URL bar) cropped, on cream with rounded corners. Step bar 1 Photo → 2 Check (cut-out spinner src 7.8, "Finding elbows and knees" 8.8) → cat preview 9.25; src 9.3–11.7 skipped (a stray keyboard); name typed 17.9–19.9; Send ~21.0; "Queen Whiskers is on the TV now!" with all three steps ticked at 21.5 (timeline 0:37.1). `images\rig_skeletons.png` (cat only, crop 320×400) beside the phone from 0:31.9. Muted. |
| 3b | 0:37.4–0:46.9 | `clips\home_add.mp4` | 28.7 → 38.2 | 9.5 s | xfade 0.3. "🎉 Queen Whiskers has arrived!" pops up at **src 30.4 (timeline 0:39.1)**; she walks in to ~src 34 and waves from ~34.5. |
| 4 | 0:46.9–1:17.3 | `clips\story_sound.mp4` | 12.1 → 42.5 | 30.4 s | Cut. Under the Sea, daytime. Title card src 12.3; narration from src 14.1; **"What should they do?" with the emoji picture cards at src 32.3 (timeline 1:07.1)**; focus moves to *Swim through the kelp* src 36.0 (1:10.8); kelp scene src 38.0 (1:12.8). The story's wind-down and Goodnight card are shown in scene 6b instead. |
| 5 | 1:17.3–1:26.0 | `clips\pause_sound.mp4` | 19.3 → 28.0 | 8.7 s | Cut. Space story. "Look! A little star…" starts src 23.0; **Paused at src 23.33 (timeline 1:21.3)**; resumes src 26.42 (1:24.4). |
| 6 | 1:26.0–1:37.4 | `clips\party.mp4` | 18.5 → 29.95 | 11.5 s | Cut. Dance party with the spotlight and the Selected / Now dancing tags; everybody dances from ~src 23 (timeline 1:30.5). No sound in this file. |
| 6b | 1:37.1–1:58.2 | `clips\bedtime.mp4` | 3.0 → 5.0; 5.0 → 10.4 **cropped to the top-right 1280×720 (x 640, y 0)**; 79.3 → 93.0 | 21.1 s | xfade 0.3. Home at night with **🌙 Bedtime ON** (warm, dim); the punch-in shows focus on **📖 Stories tonight** (src 5.3–7.5, timeline 1:39.4) and on **🌙 Bedtime ON** (src 7.8–10.3, 1:41.9). Cut at 1:44.5 to the end of the bedtime Space story: "…everyone yawned a big, sleepy yawn. The end!"; the wind-down starts src 81.0 (1:46.2): stars wave, the stage dims to night with a moon and twinkling stars over 9 s; the **Goodnight card** (🔁 Watch again / 🏠 Home) at src 90.6 (1:55.9). |
| 7a | 1:57.8–2:12.4 | `images\diagram.png` | still | 14.6 s | xfade 0.4. Slow zoom 1.0→1.06. |
| 7b | 2:12.1–2:21.1 | `clips\story_sound.mp4` | 42.5 → 51.5 at 1× | 9.0 s | xfade 0.3. The rest of the kelp scene (turtle and shell lines). **Muted.** |
| 7c | 2:20.8–2:24.4 | `images\rig_skeletons.png` | still | 3.6 s | xfade 0.3. The 4-up joint overlay, letterboxed. |
| 7c | 2:24.1–2:27.3 | `images\cat_walk.gif` | whole GIF, twice | 3.2 s | xfade 0.3. |
| 8 | 2:26.8–2:35.3 | `images\endcard.png` | still | 8.5 s | xfade 0.5. Fade out the last 1.0 s (picture and sound). |

**Total: 2:35.3** (155.3 s).

### Voice-over row

Each MP3 **starts** at the time given. None of them overlap.

| VO file | Length | Starts | Ends | Lands on |
|---|---|---|---|---|
| `1_hook.mp3` | 5.4 s | 0:00.5 | 0:05.9 | the drawings photo |
| `2_idea.mp3` | 11.2 s | 0:07.5 | 0:18.7 | the home screen |
| `3a_add.mp3` | 11.9 s | 0:22.4 | 0:34.3 | "scans the code on the TV" over the QR (from 0:22.0), then the phone; "If a dot is off, you drag it" with the skeleton beside the phone (0:32.3) |
| `3b_send.mp3` | 3.9 s | 0:37.1 | 0:41.0 | "Press send, and…" just after Send; "…Queen Whiskers walks on stage" as she arrives (0:39.1) |
| `4_story.mp3` | 9.9 s | 0:57.0 | 1:06.9 | "Halfway through, the child decides…" ends as the choice cards appear (1:07.1) |
| `5_pause.mp3` | 7.1 s | 1:19.0 | 1:26.0 | "Alexa, pause" lands on the **Paused** badge (1:21.3) |
| `6_dance.mp3` | 3.2 s | 1:28.2 | 1:31.4 | "everybody dance!" as they start dancing (1:30.5) |
| `6b_bedtime.mp3` | 11.1 s | 1:37.5 | 1:48.6 | Home with Bedtime ON and the two chips, then the last line and the lights going down |
| `7a_built.mp3` | 10.7 s | 1:58.2 | 2:08.9 | the diagram |
| `7b_honest.mp3` | 11.7 s | 2:09.2 | 2:20.8 | starts on the diagram; "…this demo plays from our hand-written story set" over the muted story footage |
| `7c_open.mp3` | 5.9 s | 2:21.3 | 2:27.2 | skeletons, then the walking cat |
| `8_close.mp3` | 3.9 s | 2:27.4 | 2:31.4 | the end card |

### App sound (inside `story_sound.mp4`, `pause_sound.mp4` and `bedtime.mp4`)

The TV's own sound is ducked to 20% while any voice-over line plays (35% in scene 5, so the
pause is heard), and is at 100% in between.

- Screen recordings carry no sound, so `record.py` rebuilds it: every Polly line the TV fetches
  is placed at its fetch time. Lines the TV speaks with **its own** text-to-speech are not
  fetched, so `record.py` adds Polly stand-ins in the same narrator voice (Ruth) at the measured
  times: the choice read-out ("What should they do? Explore the shipwreck, or Swim through the
  kelp?", story src 32.7) and the wind-down's "The end!" and "Goodnight, Queen Whiskers, Professor
  Noodles, King Bloop and Bolt." (bedtime src 81.4 and 83.8–89.0). In scene 6b the goodnight line
  comes right after the voice-over ends (1:49.1–1:54.2), so it plays at full volume.
- **Scene 4:** narration at full volume from 0:48.9 to 0:56.7, ducked under `4_story`, then full
  volume again for the choice read-out (1:07.5) and the kelp line (from 1:12.8).
- **Scene 5:** ducked to 35%: the voice stops dead at the pause (1:21.3) and comes back at 1:24.4.
- **Scene 7b:** muted.
- `home_add.mp4` and `party.mp4` have no sound.

### Captions

| Timeline | Text |
|---|---|
| 0:00.5–0:06.2 | Doodle Theater |
| 0:24.6–0:37.4 | Phone: no app, just the camera and a QR code |
| 0:31.9–0:37.4 | Joint dots found by doodle-rig. One off? Drag it. (beside the skeleton) |
| 0:39.4–0:46.6 | Photo to puppet in seconds, animated live on the TV |
| 0:57.4–1:06.7 | Polly neural voices · word speech marks · picture choices on the D-pad |
| 1:19.0–1:25.7 | Emulator: "Alexa, pause" sent as a media-session pause command |
| 1:37.7–1:48.5 | Bedtime mode · goodnight wind-down · stories-tonight limit |
| 2:12.4–2:20.8 | **If still blocked:** Demo stories: hand-written offline set, narrated by Amazon Polly. **If Bedrock works:** delete this caption, or swap in footage of a story the agent wrote. |

### If Bedrock starts working before you record

Re-generate `7b_honest.mp3` with the "If Bedrock works" line (edit `make_voiceover.py`, re-run),
check its new length, and stretch or shorten scene 7b to match (`clip(story, 42.5, 51.5)` in
`build_video.py`; the story footage is clean up to src 52.9, where the wind-down starts).
Everything after it shifts by the difference.

### Before you export, check

- Scene 7b around 2:12–2:14: King Bloop raises an arm there and the dark smear shows a little. It
  is a wide shot, but look at it full screen.
- Scene 6b: a bedtime story already ends its last line with "The end!", and the TV says "The
  end!" again as the lights go down. Both are heard here, under the voice-over.
- Clip C: no notifications, no other tabs, no personal details on screen.
- Total under 3:00 (this render: 2:35.3).
