# Try Doodle Theater in 5 minutes

No drawing, no phone and no AWS account needed: the server runs on your laptop, the TV app runs on
an Android TV emulator (or a real Fire TV), and three sample stars stand in for a child's drawings.

## 1. Start the server

You need Python 3.10+ and git. From the repo root:

```powershell
# Windows (PowerShell)
.\run.ps1
```

```bash
# macOS / Linux
./run.sh
```

The first run creates `server/.venv` and installs everything (a few minutes); later runs start
in seconds. When it is up it prints the addresses to use:

```
Doodle Theater server on port 8787
  TV on this Wi-Fi (Fire TV / Android TV):  http://192.168.1.23:8787   <- 'Set server address' on the TV
  Android TV emulator on this laptop:       http://10.0.2.2:8787   (no setup needed on port 8787)
```

Leave it running. If Windows asks, allow Python on **private** networks so a real TV or phone can
reach it. `.\run.ps1 -Help` / `./run.sh --help` list the options (another port: set `DT_PORT`).

## 2. Install the TV app

Download **`doodle-theater-tv.apk`** from the
[latest GitHub Release](https://github.com/biyonjose10/doodle-theater/releases/latest)
(or build it: `cd tv && ./gradlew assembleDebug`).

**Android TV emulator** (easiest): in Android Studio open *Device Manager*, create a *Television*
device (1080p, any recent system image) and start it. Then:

```bash
adb install doodle-theater-tv.apk
```

The app talks to `http://10.0.2.2:8787`, which is your laptop as seen from the emulator, so there
is nothing to set.

**Real Fire TV:** turn on *Settings > My Fire TV > Developer options > ADB debugging* (if Developer
options is hidden, open *My Fire TV > About* and click the device name seven times). Find the TV's
IP under *About > Network*, then:

```bash
adb connect <fire-tv-ip>:5555
adb install doodle-theater-tv.apk
```

Open Doodle Theater on the TV. It can't find the laptop yet, so Home shows **Set server address**:
press OK, enter the `TV on this Wi-Fi` address the run script printed (◀ ▶ pick a digit, ▲ ▼ change
it), then **Connect**. The TV remembers it. (Or set it over adb:
`adb shell am start -n com.doodletheater.tv/.MainActivity --es server 192.168.1.23:8787`.)

## 3. Add the sample stars

On Home, with no stars yet, press **✨ Try sample stars**. Three drawings (from Meta's MIT-licensed
AnimatedDrawings examples) are rigged by the same pipeline a phone photo goes through and appear
as stars. *Add a star* has the same option: **No drawing? Use sample stars**, and they walk in.

Have a real drawing? *Add a star* shows a QR code: scan it with a phone on the same Wi-Fi, photograph
the drawing, check the dots, and send it to the TV.

## 4. Pick a story

Choose a theme under **Start tonight's story**. During the story:

- ◀ ▶ picks a star and OK makes them jump; ⏯ (or "Alexa, pause") pauses.
- At the choice, ◀ ▶ and OK pick an option, or say **"Alexa, next"** (right) / **"Alexa,
  previous"** (left) on a Fire TV. The remote's ⏭ ⏮ do the same.

**👪 Parents** on Home removes drawings, sets a stories-per-night limit and bedtime mode, and
explains what leaves the laptop.

## AWS is optional

Everything above works offline. Without AWS credentials the server uses doodlerig's own joint
guess, writes stories from built-in templates, and the TV reads them aloud with its own
text-to-speech voice.

With credentials for an account that can use Amazon Bedrock (Nova 2 Lite) and Polly in
`us-east-1` (`~/.aws/credentials` or the usual environment variables), the server switches on by
itself: Bedrock finds the joints and writes a fresh story each time, and **Amazon Polly** narrates
it with word-by-word highlighting. See the README's
[Setup and run](../README.md#setup-and-run) section for the settings.
