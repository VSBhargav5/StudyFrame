# Local OCR source and model attribution

StudyFrame uses unmodified RapidOCR3.10.0 engineering components and three bundled
PaddleOCR-derived ONNX assets, distributed under Apache2.0. RapidOCR Authors hold
source-code copyright; upstream model rights are held by Baidu and/or respective
PaddleOCR rights holders. The accompanying RapidOCR-LICENSE.txt is copied from the
pinned distribution. Installed dependency licenses accompany portable bundles.

Primary sources:
- https://github.com/RapidAI/RapidOCR/tree/v3.10.0
- https://github.com/RapidAI/RapidOCR/blob/main/python/MODEL_LICENSES.md
- https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml

Bundled filenames/SHA256 (also match the pinned wheel registry):
- PP-OCRv6_det_small.onnx:090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f
- PP-OCRv6_rec_small.onnx:6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884
- ch_ppocr_mobile_v2.0_cls_mobile.onnx:e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c

Worker verifies these exact local assets and explicitly supplies model paths.
No first-use model download, remote OCR or visualization/font download is invoked.
Classification is disabled for the upright screenshot workflow. Synthetic tests
block network connections while running the real CPU models. OCR can lose symbols,
spacing, ordering and indentation; output is never executed or sent automatically.
