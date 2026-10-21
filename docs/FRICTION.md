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
- **Workaround:** We simulate "Alexa, pause" with `adb shell cmd media_session dispatch pause`
  against our MediaSession. (The older `media dispatch` shell command does not exist on the API 30
  TV image.) A second trap: a session only receives media buttons if the app itself plays audio.
  Narration through the system TextToSpeech plays in the engine's process, so "Media button
  session is null" and Alexa transport commands went nowhere. We now render speech to a file and
  play it with our own MediaPlayer.
- **Suggestion:** Document in the Fire TV media-session guide which app Alexa transport commands
  are routed to, and how to test it without a device.
- **Suggestion:** Publish a Fire OS 8 emulator image for Android Studio's SDK Manager, even one
  without DRM video, so developers can test launcher and voice integration.

---

## 2026-10-21: AWS account onboarding

### 4. An unfinished signup sends every service to one ambiguous page
- **Task:** Open Amazon Bedrock, IAM and Billing on an older AWS account to enable models and
  create an access key.
- **Steps:** Signed in to the console and opened each service.
- **Expected:** The service console, or a message naming the exact signup step still missing.
- **Actual:** Bedrock, IAM and Billing all redirected to the same generic *Complete your account
  setup* page. It says the account has "either not finished registering, or your account is
  currently on free plan", so it does not say which of the two applies or which step is missing.
- **Severity:** High. No service was usable until signup was finished, and the page gave no way to
  tell what was left.
- **Workaround:** Finished the remaining signup steps (see entry 6), after which the services opened.
- **Suggestion:** Name the missing step (payment method, identity verification, phone check,
  support plan) and link straight to it. Keep "unfinished signup" and "Free plan limit" as two
  separate messages.

### 5. The credits page shows $0 until signup is finished
- **Task:** Check the account's credits before using paid services.
- **Expected:** The credit balance, or a note that credits appear after signup.
- **Actual:** The credits page showed $0 while signup was unfinished, which reads as "no credits".
- **Severity:** Low.
- **Workaround:** Finished signup first.
- **Suggestion:** Show "Credits become available when you finish account setup" instead of $0.

### 6. Indian signup: UPI AutoPay mandate and DigiLocker KYC to the Aadhaar-linked number
- **Task:** Complete AWS signup from India.
- **Steps:** Payment step, then identity verification.
- **Expected:** A card check and an OTP to the phone number given to AWS.
- **Actual:** Payment needed a UPI AutoPay mandate, with a ₹15,000 limit shown on the mandate.
  Identity verification went through DigiLocker KYC, whose OTP is sent to the mobile number
  linked to the Aadhaar, not the phone number entered on the AWS form.
- **Severity:** High for anyone whose Aadhaar-linked number is old or held by a parent, as is
  common for students.
- **Workaround:** None inside the flow; the OTP has to be received on the Aadhaar-linked number.
- **Suggestion:** Say before the KYC step that the OTP goes to the Aadhaar-linked number, and
  explain on the mandate screen that ₹15,000 is a ceiling, not a charge.

### 7. Free plan appears to block Anthropic models on Bedrock; defaults switched to Nova
- **Task:** Run the vision and story steps on the code's default model,
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- **Expected:** Model access granted from the Bedrock console like other models.
- **Actual:** Anthropic models need a use-case form, and the account is on the AWS Free plan,
  which appears to block AWS Marketplace models, Anthropic's included.
- **Severity:** Medium.
- **Workaround:** Changed both defaults in `server/doodle_theater/config.py` to Amazon Nova 2 Lite
  (`us.amazon.nova-2-lite-v1:0`). The Converse API made this a model-id change only.
- **Suggestion:** In the Bedrock model catalog, mark which models a Free plan account can call and
  why a model is unavailable (plan, form pending, region).

### 8. Nova Canvas not listed in us-east-1 for this account
- **Task:** Optionally replace the code-drawn crayon backdrops with Nova Canvas art.
- **Expected:** Nova Canvas in the us-east-1 foundation model list.
- **Actual:** It was not listed for this account in us-east-1.
- **Severity:** Low. Backdrops are drawn in code (`backdrops.py`) and need no model.
- **Workaround:** Kept the 18 code-drawn backdrops.
- **Suggestion:** When a model is missing from a region's list for an account, say whether it is
  the region, the plan or access that hides it.

### 9. No AWS CLI on Windows by default
- **Task:** Give boto3 credentials on the Windows dev laptop.
- **Expected:** `aws configure`.
- **Actual:** The AWS CLI is not installed on Windows by default, so `aws configure` is not
  available without a separate install.
- **Severity:** Low.
- **Workaround:** Entered the credentials through a small local pop-up instead of the CLI.
- **Suggestion:** Next to the new access key, show the plain `~/.aws/credentials` file format as
  an alternative to `aws configure`.

### 10. Bedrock calls denied for hours after signup was finished
- **Task:** First live Nova call right after completing the account signup.
- **Expected:** The call works once the console and IAM work.
- **Actual:** `Converse` returned `AccessDeniedException: Your account is currently being verified.
  Verification normally takes less than 2 hours.` The console, IAM, STS and Bedrock list calls all
  worked, so nothing hinted that invoking would be blocked.
- **Severity:** Medium on a deadline: the AI path could not be tested the same afternoon.
- **Workaround:** The server falls back to the offline templates on any Bedrock error, so the app
  kept working; the live test waited for verification.
- **Suggestion:** Show "account verification in progress" with an estimate on the console home and
  Bedrock pages, not only in the error from the first invoke.

### 11. Bedrock invocation blocked with "Operation not allowed" after verification
- **Task:** First live Nova `Converse` call after signup, once the verification wait in entry 10
  was over.
- **Steps:** Called `Converse` on `amazon.nova-lite-v1:0`, `amazon.nova-micro-v1:0` and
  `us.amazon.nova-2-lite-v1:0` in us-east-1, then retried through the afternoon.
- **Expected:** The call works once verification passes, as the earlier error ("less than 2
  hours") implied.
- **Actual:** Every `Converse` call returned `ValidationException: Operation not allowed`, still
  at about 17:30 IST the same day. On the same account and credentials, `ListFoundationModels`,
  `CreateGuardrail` and Polly all worked. The error does not say why the call is refused or what
  to do. AWS Support has a category *Account and billing → Account Activation → Bedrock
  Allowlisting*, so this is a known gate. Opening a case first goes through a generative-AI
  troubleshooting assistant, which answered that it was unable to offer a recommendation before
  the case form appeared. A case was filed on 21 October at about 18:20 IST.
- **Severity:** High on a deadline. The AI story path cannot be shown live.
- **Workaround:** The app falls back to the hand-written stories, still narrated live by Polly. A
  local-model path for the same Strands agent (Ollama, `DT_STORY_MODEL=ollama:qwen3:8b`) is being
  added so the agent loop can be demonstrated.
- **Suggestion:** Name the gate in the error, for example "Bedrock access for this account
  requires allowlisting; open a case in Account Activation → Bedrock Allowlisting", and show the
  same notice on the Bedrock console before the first call.
