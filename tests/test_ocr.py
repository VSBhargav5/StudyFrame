"""Local OCR ownership/review gates; no personal screen, key or model request."""
import hashlib
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.images import LoadedImage
from studyframe.ocr import OcrSession,MAX_OCR_OUTPUT
from studyframe.provider import StudyProvider
from test_provider import Reply,response


class OfflineOcr(QObject):
    succeeded=Signal(str)
    failed=Signal(str)
    active=False
    def start(self,image):self.active=True;self.snapshot=image
    def cancel(self):self.active=False
    def complete(self,text):self.active=False;self.succeeded.emit(text)


class OcrReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager=Mock();self.manager.post.return_value=Reply(response('5'))
        self.ocr=OfflineOcr();self.w=StudyWindow(StudyProvider(manager=self.manager),ocr=self.ocr)
        self.addCleanup(self.w.close);self.addCleanup(self.w.deleteLater)
        image=QImage(50,20,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.white)
        data=b'synthetic-only-snapshot'
        self.w.attachment=LoadedImage(data,image,hashlib.sha256(data).hexdigest(),50,20,'png')
        self.w.update_send()

    def test_extract_without_key_then_reviewed_send_has_text_only_and_no_old_image(self):
        w=self.w;w.question.setPlainText('What does this print?')
        w.extract_image_text();self.assertTrue(w.busy)
        self.manager.post.assert_not_called()
        self.ocr.complete('print(2 + 3)')
        self.assertFalse(w.busy);self.assertEqual(w.ocr_text.toPlainText(),'print(2 + 3)')
        self.assertFalse(w.ask_ocr.isEnabled())
        w.key.setText('synthetic-key');w.ask_image_text();self.manager.post.assert_not_called()
        w.ocr_consent.setChecked(True);self.assertTrue(w.ask_ocr.isEnabled());w.ask_image_text()
        record=json.loads(self.manager.post.call_args.args[1]);parts=record['input'][0]['content']
        self.assertEqual(len(parts),1);self.assertEqual(parts[0]['type'],'input_text')
        self.assertIn('print(2 + 3)',parts[0]['text']);self.assertFalse(w.ocr_consent.isChecked())

    def test_read_screen_text_captures_locally_without_key_or_provider_request(self):
        from types import SimpleNamespace
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QPixmap
        w=self.w
        image=QImage(50,20,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.white)
        screen=SimpleNamespace(geometry=lambda:QRect(0,0,50,20),devicePixelRatio=lambda:1,
                              grabWindow=lambda _:QPixmap.fromImage(image))
        w.screen_choice.clear();w.screen_choice.addItem('Synthetic',screen)
        with patch('studyframe.app.QApplication.screens',return_value=[screen]):
            w.capture_for_text();self.assertTrue(w.ocr_after_capture);w.complete_capture()
        self.assertTrue(self.ocr.active);self.assertFalse(w.key.text())
        self.manager.post.assert_not_called()
        self.ocr.complete('StudyFrame 12345');self.assertFalse(w.ask_ocr.isEnabled())

    def test_edits_revoke_consent_and_changed_image_drops_text_binding(self):
        w=self.w;w.key.setText('synthetic-key');w.extract_image_text();self.ocr.complete('print(2)')
        w.ocr_consent.setChecked(True);w.ocr_text.setPlainText('print(3)')
        self.assertFalse(w.ocr_consent.isChecked());self.assertFalse(w.ask_ocr.isEnabled())
        w.ocr_consent.setChecked(True);w.material_changed()
        self.assertFalse(w.ocr_text.toPlainText());self.assertFalse(w.ask_ocr.isEnabled())

    def test_cancel_ignores_late_extraction_even_during_new_network_request(self):
        w=self.w;w.extract_image_text();w.cancel_request()
        self.assertFalse(w.busy);self.assertFalse(self.ocr.active)
        w.set_busy(True);self.ocr.succeeded.emit('late stale pixels')
        self.assertFalse(w.ocr_text.toPlainText());self.assertTrue(w.busy)
        self.assertIn('No image or text sent',w.feedback.text())

    def test_401_status_is_not_silently_presented_as_accepted_key(self):
        w=self.w;w.key.setText('synthetic-key');w.set_busy(True);w.receive_error('HTTP 401: rejected')
        self.assertIn('Auth rejected',w.provider_badge.text());self.assertEqual(w.key.text(),'synthetic-key')
        w.set_busy(True);w.receive_quota('Synthetic metadata counters')
        self.assertIn('Metadata accepted',w.provider_badge.text());self.assertNotIn('Answer received',w.provider_badge.text())
        w.key.setText('synthetic-new-key');self.assertIn('Key entered',w.provider_badge.text())
        w.provider_choice.setCurrentIndex(w.provider_choice.findData('openai'));w.key.setText('synthetic-openai-key')
        w.set_busy(True);w.receive_error('HTTP 401: rejected')
        self.assertIn('OpenAI project',w.feedback.text());self.assertNotIn('Check free usage',w.feedback.text())
        self.manager.post.assert_not_called()

    def test_oversized_or_wrong_snapshot_worker_output_is_not_accepted(self):
        session=OcrSession();self.addCleanup(session.cancel);errors=[];texts=[]
        session.failed.connect(errors.append);session.succeeded.connect(texts.append)
        process=Mock();process.readAllStandardOutput.return_value=b'x'*(MAX_OCR_OUTPUT+1)
        session.process=process;session.read(process)
        self.assertFalse(session.active);self.assertIn('limit',errors[-1])
        process=Mock();process.readAllStandardOutput.return_value=json.dumps({'text':'private output','sha256':'wrong'}).encode()
        session.process=process;session.source_hash='expected';session.finished(process,0)
        self.assertFalse(texts);self.assertNotIn('private',errors[-1])


class OcrBackendTests(unittest.TestCase):
    def test_real_bundled_cpu_models_recognize_synthetic_text_without_network(self):
        from io import BytesIO
        from PIL import Image,ImageDraw,ImageFont
        from studyframe.ocr_worker import recognize
        os.environ['ORT_DISABLE_TELEMETRY']='1'
        import onnxruntime
        image=Image.new('RGB',(850,160),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('DejaVuSans.ttf',40) if os.name!='nt' else ImageFont.truetype('C:/Windows/Fonts/consola.ttf',40)
        draw.text((25,25),'StudyFrame 12345',font=font,fill='black')
        encoded=BytesIO();image.save(encoded,'PNG')
        with patch('socket.socket.connect',side_effect=AssertionError('Network forbidden')), \
             patch.object(onnxruntime,'disable_telemetry_events',wraps=onnxruntime.disable_telemetry_events) as disable:
            text=recognize(encoded.getvalue())
        disable.assert_called_once()
        self.assertIn('STUDYFRAME12345',''.join(c for c in text.upper() if c.isalnum()))
        with self.assertRaises(ValueError):recognize(b'')
