# YouTube upload

**File:** `submission/final/doodle-theater-demo.mp4` · **Thumbnail:** `submission/images/thumbnail.png`
**Visibility:** Public (or Unlisted) · **Audience:** "No, it's not made for kids". It's a demo for
judges and parents, and "made for kids" turns off comments and other features.
**Category:** Science & Technology

## Title (under 100 characters)
Doodle Theater: a child's drawing becomes a live puppet on Fire TV

## Description

A child's paper drawing becomes a live puppet on Fire TV and stars in a bedtime story they steer
with the remote.

How it works:
• The TV shows a QR code. A parent scans it and photographs the drawing; no app or account needed.
• Our open-source rigger cuts the drawing out and gives it a mesh, a 16-joint skeleton and skin
  weights, in about 2 seconds.
• The puppet walks onto the TV and is animated live at 60 fps. It's not a pre-rendered video.
• Tonight's story: the cast acts out a short play narrated by Amazon Polly. Words light up as
  they're read, and the child picks what happens next with the D-pad (picture choices for
  pre-readers).
• Made for bedtime: after 7 PM the screen turns warm and dim, narration gets slower and softer,
  and every story ends with a goodnight to each star. Parents can cap stories per night.
• "Alexa, pause" works, and so do "Alexa, next / previous" at a story choice.

Built for the Amazon "Build, Ship, Shape" hackathon (Fire TV track).

Code (MIT): https://github.com/biyonjose10/doodle-theater

Built with Kotlin, Jetpack Compose for TV, Python, FastAPI, Amazon Polly, Amazon Bedrock, Strands
Agents.

Drawings by a neighbour's child (shared with permission), cleaned up with Gemini.
The pig in the cut-out fix is a test drawing from Meta's AnimatedDrawings (MIT).
Voice-over: Amazon Polly (neural voice Ruth). No music.

## Tags
fire tv, amazon fire tv, kids, bedtime story, drawing animation, puppet, amazon polly, amazon
bedrock, strands agents, jetpack compose, hackathon, open source

## Before publishing
- [ ] The thumbnail is the re-shot one (no arm smear on King Bloop).
- [ ] If Bedrock still isn't working on upload day, it's fine that it's listed under "Built with":
      the story agent is built on it and the app falls back to templates. Don't claim live AI
      stories in the description.
- [ ] Paste the video link into `devpost.md` (`VIDEO_LINK_HERE`).
