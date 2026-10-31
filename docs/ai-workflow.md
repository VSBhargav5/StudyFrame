# Predict, ask, verify

StudyFrame now has a deliberately initiated OpenAI text/image request path.
Its 58 offline tests cover the existing image/request rules and the new transport
and widget transitions. No paid request, personal screenshot transmission,
account access, or answer-quality experiment was performed during implementation.

## Contract reviewed on 29 October 2026

- [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create):
  POST JSON with model, user input content, store=false and max_output_tokens.
- [Image input guide](https://developers.openai.com/api/docs/guides/images-vision):
  input_image accepts a base64 data URL. The selected byte snapshot is encoded,
  not reopened from disk. The complete PNG/JPEG and its metadata are transmitted.
- [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini):
  supports image input and text output through Responses. Listed text rates at
  review were $0.40 per million input tokens and $1.60 per million output tokens;
  image input is also billed. These are not a per-question estimate or guarantee.

This is one narrow non-reasoning model integration, not a claim that this model
is newest or best. Account availability is unverified. Check current rates and
project billing before sending. No tools, files service, remote URLs, persistent history,
streaming, automatic retry, or arbitrary provider endpoint is enabled.

Qt networking is asynchronous: the UI event loop receives completion signals
without blocking on network I/O. Cancel clears the active reply before aborting;
late signals from that reply cannot finish a subsequent request. A 60-second
timer bounds local waiting; the remote service may still process and bill it.
Requests disable redirect following so credentials are not forwarded to another
destination. TLS errors are not ignored. Provider error bodies are not echoed.

The app accepts only completed assistant text. Refusals, incomplete responses,
malformed JSON, missing text, HTTP errors and oversized responses produce useful
errors. Mocks prove local behavior, not the remote API or model's correctness.
There is no code execution. Prompt instructions are not a security boundary.

## One 60–90 minute practice session

October 31 upgrade: use Question → Review & send → Answer tabs. After a completed
answer, Ask a follow-up returns to Question. Only the immediately prior question
and answer are retained, not the earlier chain. They appear verbatim in the next
prepared text as reference that may contain errors. Current notes and image are
included again. Review and consent are required for each send. Editing the notes,
replacing/removing the image or Start a new question drops the previous exchange.
Cancelled/failed image replacement preserves it. Clear drops all retained exchanges.

We reviewed [OpenAI's conversation-state documentation](https://developers.openai.com/api/docs/guides/conversation-state)
on October 31. Each request is independent; our implementation includes a bounded
prior exchange as explicit reference text in a fresh request. It uses no response
IDs, Conversations service or hidden server-side session. The existing model,
endpoint and store=false contract are unchanged. A maximum 4,000-character prior
question and 12,000-character answer are accepted, without silent truncation.
Earlier facts may therefore be absent; add needed material explicitly. Provider
mocks validate what is sent, not whether the model uses that context correctly.

For today's focused exercise, predict what will be included in a second and
third follow-up. Run the tests and inspect `test_followup_requires_a_new_question_and_review_before_sending`.
Explain the tradeoff: one exchange bounds retained/transmitted text but omits
older context. Practice and live answer quality remain unverified.

1. Run `python -m unittest discover -s tests -v` from the project environment.
2. Run `python -m examples.demo`. Predict `range(3)` before reading any answer.
3. Prepare a hint. Trace `requests.py` to `provider.payload`: identify the exact
   text and optional image bytes. Preparing alone must not start networking.
4. Trace `send_request` and `StudyProvider.send`. Find the one point at which
   data leaves the app. Review the recipient, model, costs and embedded metadata.
5. Read the cancel and old-reply regression tests. Explain why aborting a local
   connection is different from reversing a charge or deleting received data.
6. A live trial is optional and requires your own deliberate authorization/key.
   Start with synthetic material. Check the returned explanation against Python;
   do not infer correctness from a successful HTTP response.

Tradeoff: using existing Qt networking avoids another runtime dependency but
requires our own bounded response parsing and lifecycle tests. No learning
completion is recorded until the user actually practices.

Next evidence gate: an authorized synthetic live trial, manual Windows key/send/
cancel/dialog/clipboard operation, then a personally checked useful study answer.
There is no installer or proven AI MVP yet. SettleTrace remains paused.
