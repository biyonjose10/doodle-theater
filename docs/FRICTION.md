# Friction log

Logged while we built it, not reconstructed afterwards. Severity: **Blocker** (no workaround),
**High** (workaround cost hours), **Medium** (workaround cost minutes), **Low** (papercut).

---

### 1. Vega SDK cannot be installed on Windows
- **Task:** Build Doodle Theater for Vega OS, Amazon's newest Fire TV platform, alongside Fire OS.
- **Steps:** Read *Install the Vega SDK* (v0.24) and its system requirements.
- **Expected:** A Windows installer or a supported WSL2 path, since Windows is the most common
  developer OS among hackathon entrants.
- **Actual:** The docs list macOS 10.15+ and Ubuntu 20.04/22.04/24.04 only, and say Windows and WSL
  are untested. The Vega Virtual Device needs KVM, and on Windows that means nested virtualisation.
- **Severity:** High. It rules out Vega OS for Windows-only developers.
- **Workaround:** Build for Fire OS (Android) in Kotlin + Compose for TV and test on the Android TV
  emulator, which the hackathon FAQ allows.
- **Suggestion:** Ship a VVD container or devcontainer image, or support WSL2 officially with a
  `/dev/kvm` check in the installer. Even a "Vega in the browser" simulator would let Windows
  developers try the platform before buying a Mac.

### 2. The official Kotlin Fire TV sample pins 2023-era dependencies
- **Task:** Start from `AmazonAppDev/hello-world-fire-tv` (Kotlin + Jetpack Compose).
- **Expected:** Current, stable Compose for TV libraries.
- **Actual:** `compose-bom:2023.08.00`, `tv-foundation:1.0.0-alpha11`, Java 1.8, `compileSdk 34`,
  and the old `kotlinCompilerExtensionVersion` setup that Kotlin 2.x replaced with the Compose
  compiler Gradle plugin. Upgrading means changing the Gradle plugin setup, not only bumping
  versions.
- **Severity:** Medium.
- **Workaround:** Kept the sample's structure (leanback manifest flags, banner, TV Material) and
  rebuilt the Gradle setup on AGP 8.13, Kotlin 2.3, the Compose compiler plugin and JDK 17. A
  second trap followed: the newest AndroidX releases (`core-ktx 1.19`, `compose-bom 2026.09`,
  `tv-material 1.1`) need AGP 9.1 and `compileSdk 37`. The build failed with 28 dependency
  errors until we pinned `compose-bom:2025.06.01` and `tv-material:1.0.1`.
- **Suggestion:** Add Renovate/Dependabot to the sample repos, and add a CI badge that builds
  against the latest stable AGP.

### 3. No Fire OS emulator: the Android TV emulator stands in
- **Task:** Test on "Fire TV" without hardware.
- **Expected:** A Fire OS system image (launcher, Alexa voice, Amazon Appstore services).
- **Actual:** The docs and the hackathon FAQ point to the stock Android TV emulator. It
  cannot exercise Fire-specific behaviour: the Amazon launcher's recommendation rows, Alexa
  voice commands reaching the app's media session, or Appstore In-App Purchasing through App
  Tester.
- **Severity:** Medium.
- **Workaround:** We simulate "Alexa, pause" with `adb shell media dispatch pause` against our
  MediaSession, and keep Fire-specific features behind interfaces.
- **Suggestion:** Publish a Fire OS 8 emulator image for Android Studio's SDK Manager, even one
  without DRM video, so developers can test launcher and voice integration.
