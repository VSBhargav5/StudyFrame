"""One local snapshot through CPU OCR; no capture, credentials or API request."""
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from contextlib import redirect_stdout
from studyframe.images import MAX_FILE_BYTES,MAX_DIMENSION,MAX_PIXELS
from studyframe.ocr import MAX_OCR_TEXT


def recognize(data):
    if not 0<len(data)<=MAX_FILE_BYTES:raise ValueError('image limit')
    from PIL import Image
    image=Image.open(io.BytesIO(data))
    if image.format not in ('PNG','JPEG') or min(image.size)<1 or max(image.size)>MAX_DIMENSION or image.width*image.height>MAX_PIXELS:
        raise ValueError('image contract')
    return run_engine(image)


def run_engine(image):
    os.environ['ORT_DISABLE_TELEMETRY']='1'
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    import rapidocr
    models=Path(rapidocr.__file__).parent/'models'
    expected={
        'PP-OCRv6_det_small.onnx':'090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f',
        'PP-OCRv6_rec_small.onnx':'6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884',
        'ch_ppocr_mobile_v2.0_cls_mobile.onnx':'e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c',
    }
    for name,digest in expected.items():
        path=models/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size>40*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('bundled model integrity')
    engine=rapidocr.RapidOCR(params={
        'Det.model_path':str(models/'PP-OCRv6_det_small.onnx'),
        'Rec.model_path':str(models/'PP-OCRv6_rec_small.onnx'),
        'Cls.model_path':str(models/'ch_ppocr_mobile_v2.0_cls_mobile.onnx'),
        'Global.use_cls':False,'Global.log_level':'critical',
        'EngineConfig.onnxruntime.intra_op_num_threads':2,
        'EngineConfig.onnxruntime.inter_op_num_threads':1,
    })
    # All three paths are explicit, verified local assets; no downloader fallback.
    result=engine(image)
    return '\n'.join(result.txts or ())


def main():
    protocol=sys.stdout
    if hasattr(protocol,'reconfigure'):protocol.reconfigure(encoding='utf-8')
    try:
        source=getattr(sys.stdin,'buffer',sys.stdin)
        data=source.read(MAX_FILE_BYTES+1)
        with redirect_stdout(io.StringIO()):text=recognize(data)
        if not isinstance(text,str) or not 0<len(text.strip())<=MAX_OCR_TEXT:raise ValueError('text limit')
        protocol.write(json.dumps({'text':text,'sha256':hashlib.sha256(data).hexdigest()},ensure_ascii=False))
        protocol.flush()
        return 0
    except Exception:
        protocol.write('{"error":"Local OCR unavailable"}');protocol.flush()
        return 1


if __name__=='__main__':raise SystemExit(main())
