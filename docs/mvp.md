# A useful personal study session

The recurring task: while learning Python or investigating a small coding issue,
collect the visible example, explain what is confusing, and get a checkable next
step without losing control of what leaves the computer.

## Current foundation

Local image preview plus question/context preparation and an explicit OpenAI
send/cancel path are implemented. Copying a prepared request still copies only
text; Send includes the selected image. Provider behavior is mock-tested; no live
answer or usefulness claim is established. See [AI workflow](ai-workflow.md).
The image hash identifies the bytes selected for preview; it does not establish
truth, correctness, completeness, or safe sharing.

## Next implementation gate

1. Review one provider's current image/text API and choose a model using explicit
   requirements, costs and authorization. No automatic account linking.
2. Show the exact image and text to send, destination, and an explicit Send action.
   Run requests outside the UI thread; implement cancellation, timeout and useful
   errors. Keep unsent input available after failures.
3. Verify the selected snapshot is what gets sent. Provider mocks test transport
   behavior; a live call requires separate authorization and is labeled as live.
4. Try a known coding example: predict the result before asking, check the answer,
   and record whether the explanation helped. Synthetic tests alone cannot show
   model quality or personal usefulness.
5. Check Windows foreground operation, file dialog, clipboard, DPI scaling and
   keyboard access before preparing an installer.

Only after that end-to-end study workflow is usable should this be called an AI
MVP. Meeting audio/transcription/notes is a later opt-in slice. A database, local
OCR, multiple providers, account system, agent framework and deployment are not
needed for this foundation. A local-model option can be evaluated later against
the actual machine and required quality, not assumed to be free or fast.

StudyFrame is the active portfolio sprint. SettleTrace remains paused at its
verified v0.3; choose a deliberate switch back after the study MVP review.
No revenue, adoption, performance, demand, or time-savings claim is established.
