# A screenshot is data, not understanding

Spend 60–90 minutes on this one boundary: selecting information is different from
asking a model to interpret it.

## Predict first — 10 minutes

For `for i in range(3): print(i)`, predict the exact output and whether 3 appears.
Explain what a half-open interval means. Then predict what StudyFrame can know
when given only an image: it can decode pixels, but has no OCR or model to read
their meaning.

## Run and inspect — 35 minutes

From the repository root, after installing requirements:

```powershell
.\.venv\Scripts\python.exe -m examples.demo
```

Switch from Hint to Debug. The prepared request disappears. Prepare it again and
compare the instructions. Change the pasted code's indentation and verify that it
survives in the request. Remove the screenshot; the old request disappears again.

Trace three small modules:

- `studyframe/requests.py`: validates text and chooses a learning instruction.
- `studyframe/images.py`: reads bounded bytes and decodes that same snapshot.
- `studyframe/app.py`: connects buttons and text changes to those operations.

There is no network operation on this path. A future provider call must be a
separate deliberate action, with an inspected destination and payload.

## Break an assumption — 15 minutes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_images.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_app.py -v
```

Read the test that replaces a selected file after loading. Explain why the preview
still represents the old captured bytes. Read the test for a failed replacement:
the prior selection stays, and the status explains the failure. Explain why a
file named `.png` is insufficient evidence of its format.

## Explain a tradeoff — 10 minutes

PySide6 gives Python a desktop UI but brings a large native dependency. A browser
UI might be easier to share, but adds another interface/runtime boundary for this
personal Windows tool. Why does the desktop choice fit this first workflow?

Prepared prompts are neither answers nor proof that a future model will obey
instructions. State the exact action at which data would first leave the app.
This session is prepared; learning is not marked complete until you practice it.
