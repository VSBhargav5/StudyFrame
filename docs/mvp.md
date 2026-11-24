# StudyFrame Windows MVP scope and acceptance

A desktop learning companion for permitted screen/text/voice questions, with explicit
control of what leaves the laptop. No continuous screen/audio watching or execution.

## Implemented local workflows

| Workflow | Current behavior | Evidence and remaining acceptance |
|---|---|---|
| Screen to vision | Selected display, balanced/full pixels, local preview/crop or explicit Capture & ask | User verified one synthetic print(2+3) answer; speed/detail on other inputs not established |
| Screen to text | Read screen text captures locally; CPU OCR with bundled verified models; edit/consent; Ask reviewed text only | Real generated-image source/frozen checks; personal OCR accuracy and latency need comparison |
| Voice to text | Explicit prepare/Ready/Listen/Listening now/Stop, selected input/playback, editable transcript, text-only ask | Backend/worker and synthetic playback evidence; Indian-accent accuracy and opening words still need user acceptance |
| Model connection | Free OpenRouter default, separately labelled paid OpenAI, provider-isolated session-memory keys, manual quota GET and auth states | User obtained text/image answers and quota; later401 remains undiagnosed pending same-instance quota result |
| Answer handling | Quick/Explain/Hint/Debug, streaming, partial vs completed, cancellation, bounded follow-up/copy, clear answer/end session | Offline UI and real localhost streaming tests; current provider quality/availability not guaranteed |
| Desktop overlay | Rounded native frost/fallback, pin/collapse, display fit, capture-exclusion capability readback | Owned Windows light/dark fixtures; personal scaling/recorders/native dialogs vary |
| Distribution | Portable plus per-user installer, staged no-overwrite builds, runtime checks, integrity manifest, user-config retention | Windows CI lifecycle; unsigned and personal interrupted-upgrade/manual acceptance open |

These are implemented workflows, not a claim that account access, microphone/OCR
accuracy or all real-world acceptance is complete. No overall completion percentage.
Optional history, continuous meetings, local LLM hosting and arbitrary providers
are outside this MVP; no automatic screenshot/audio uploading or exam-browser bypass.

## Use the new local text route

1. Expand the capsule. Choose the display and click Read screen text. This captures
   and extracts locally, without a provider request or API key.
2. Check the preview; crop and Extract text locally again if necessary. Correct
   OCR ordering, symbols, indentation and any content you do not want to send.
3. Type a question, enter your own provider key only in settings, and check the
   extracted-text review checkbox. Click Ask reviewed text only. No image/audio or
   old notes are included by this action. Editing text or changing inputs revokes
   consent; changing the image invalidates the extracted source binding.
4. Predict an answer, verify it with a small example, and compare first-text/total
   timing. OCR can lose visual/diagram information; use vision when needed.

## Acceptance still requiring the user

- Same permitted phrase on US/Indian speech models and selected devices; compare
  opening words and errors. Readiness is not accuracy, and no audio trial is assumed.
- Resolve the observed401 by checking free usage in the same running app; share
  only its safe message. Key entered is not authenticated; metadata accepted is not
  proof a model request will succeed. No agent key access or automatic paid trial.
- Retest capture/voice key continuity, OCR text detail, real provider timing and UI
  on actual displays. Earlier reported10–20+s vision/1–2s text is not a benchmark.
- If desired, manually accept the unsigned installer. Signing and interrupted-
  upgrade recovery are not established by the current CI lifecycle checks.

For60–90minutes, use a synthetic code image: predict its text, extract/correct it,
show that edits revoke consent, inspect the one text-only request, then compare
image vs text tradeoffs. No learning completion until the user practices.
