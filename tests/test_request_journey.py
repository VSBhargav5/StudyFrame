"""Real Qt HTTP/event-loop path with a local server and synthetic capture only."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtNetwork import QHostAddress,QNetworkAccessManager,QNetworkProxy,QTcpServer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.provider import StudyProvider
from test_provider import response


class RequestJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.server=QTcpServer();self.assertTrue(self.server.listen(QHostAddress.SpecialAddress.LocalHost,0))
        self.addCleanup(self.server.close)
        self.status=200;self.packets=[];self.connections=[];self.defer=False
        def accept():
            socket=self.server.nextPendingConnection();self.connections.append(socket);buffer=bytearray()
            def read():
                buffer.extend(bytes(socket.readAll()))
                if b'\r\n\r\n' not in buffer:return
                headers,body=bytes(buffer).split(b'\r\n\r\n',1)
                size=int(next(x.split(b':',1)[1] for x in headers.split(b'\r\n') if x.lower().startswith(b'content-length:')))
                if len(body)<size:return
                self.packets.append(json.loads(body[:size]))
                if self.defer:return
                data=response('Synthetic answer: 0, 1, 2.') if self.status==200 else b'{"error":{"message":"private body must not appear"}}'
                socket.write(f'HTTP/1.1 {self.status} Test\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n'.encode()+data)
                socket.disconnectFromHost()
            socket.readyRead.connect(read)
        self.server.newConnection.connect(accept)
        self.manager=QNetworkAccessManager()
        self.manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.window=StudyWindow(StudyProvider(manager=self.manager),start_collapsed=True)
        self.addCleanup(self.window.deleteLater);self.addCleanup(self.window.close)
        self.window.show();self.window.raise_();self.window.activateWindow();self.app.processEvents()
        self.window.key.setText('synthetic-test-key')
        image=QImage(40,20,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.blue)
        self.screen=SimpleNamespace(name=lambda:'Synthetic',geometry=lambda:QRect(0,0,40,20),
                                    devicePixelRatio=lambda:1,grabWindow=lambda _:QPixmap.fromImage(image))
        self.window.screen_choice.clear();self.window.screen_choice.addItem('Synthetic',self.screen)

    def wait(self,condition):
        for _ in range(250):
            if condition():return
            QTest.qWait(20)
        self.fail('Local UI/HTTP journey timed out')

    def config(self):
        return patch('studyframe.provider.provider_config',return_value={
            'model':'openrouter/free','label':'Local test','endpoint':f'http://127.0.0.1:{self.server.serverPort()}/responses'})

    def test_real_click_capture_timer_http_answer_and_viewport(self):
        w=self.window
        if os.name=='nt' and self.app.platformName()=='windows':
            # Verify actual native hit testing reaches Qt, not the backdrop HWND.
            import ctypes
            from ctypes.wintypes import POINT,RECT
            user=ctypes.WinDLL('user32',winmode=0x800)
            user.GetWindowRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(RECT)]
            user.WindowFromPoint.argtypes=[POINT];user.WindowFromPoint.restype=ctypes.c_void_p
            user.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint32];user.GetAncestor.restype=ctypes.c_void_p
            rect=RECT();user.GetWindowRect(int(w.winId()),ctypes.byref(rect))
            point=w.capture_button.mapTo(w,w.capture_button.rect().center());scale=w.devicePixelRatioF()
            hit=user.WindowFromPoint(POINT(rect.left+round(point.x()*scale),rect.top+round(point.y()*scale)))
            self.assertEqual(user.GetAncestor(hit,2),int(w.winId()))
        with self.config(),patch('studyframe.app.QApplication.screens',return_value=[self.screen]):
            QTest.mouseClick(w.capture_button,Qt.MouseButton.LeftButton)
            self.wait(lambda:bool(w.answer.toPlainText()))
        self.assertEqual(len(self.packets),1)
        self.assertEqual(self.packets[0]['input'][0]['content'][1]['type'],'input_image')
        self.assertFalse(w.collapse_button.isChecked())
        self.assertTrue(w.feedback.isVisible())
        self.app.processEvents()
        y=w.answer.mapTo(w.scroll.viewport(),QPoint()).y()
        self.assertGreaterEqual(y,0);self.assertLess(y,w.scroll.viewport().height())

    def test_text_error_is_prominent_preserves_draft_and_explains_http_status(self):
        w=self.window;self.status=404
        w.open_voice();w.speech_text.setPlainText('Why does range(3) stop at two?')
        with self.config():
            QTest.mouseClick(w.ask_speech,Qt.MouseButton.LeftButton)
            self.wait(lambda:w.request_failed)
        self.assertEqual(len(self.packets[0]['input'][0]['content']),1)
        self.assertIn('HTTP 404',w.feedback.text())
        self.assertNotIn('private body',w.feedback.text())
        self.assertTrue(w.feedback.isVisible());self.assertFalse(w.busy)
        self.assertEqual(w.speech_text.toPlainText(),'Why does range(3) stop at two?')
        self.assertFalse(w.answer.toPlainText())
        w.collapse_button.setChecked(True)
        self.assertIn('Request failed',w.privacy_badge.text())
        self.assertLess(w.height(),160)

    def test_preview_scrolls_to_actual_image_from_bottom_of_long_drawers(self):
        from studyframe.capture import capture_screen
        w=self.window;w.collapse_button.setChecked(False)
        w.attachment=capture_screen(self.screen);w.original_attachment=w.attachment
        w.open_voice();self.app.processEvents()
        w.scroll.verticalScrollBar().setValue(w.scroll.verticalScrollBar().maximum())
        w.review_toggle.setChecked(True);self.app.processEvents();self.app.processEvents()
        y=w.image_label.mapTo(w.scroll.viewport(),QPoint()).y()
        self.assertGreaterEqual(y,0)
        self.assertLessEqual(y+w.image_label.height(),w.scroll.viewport().height())
        self.assertFalse(w.image_label.pixmap().isNull())

    def test_waiting_request_can_be_cancelled_from_header_without_scrolling(self):
        w=self.window;self.defer=True
        w.open_voice();w.speech_text.setPlainText('Synthetic question')
        with self.config():
            QTest.mouseClick(w.ask_speech,Qt.MouseButton.LeftButton)
            self.wait(lambda:bool(self.packets))
            self.assertTrue(w.top_cancel.isVisible())
            QTest.mouseClick(w.top_cancel,Qt.MouseButton.LeftButton)
        self.assertFalse(w.busy)
        self.assertIn('Cancelled locally',w.feedback.text())
        self.assertTrue(w.capture_button.isVisible())

    def test_real_http_stream_displays_first_text_before_completion(self):
        w=self.window;self.defer=True
        first=b'data: '+json.dumps({'type':'response.output_text.delta','delta':'5'}).encode()+b'\n\n'
        last=b'data: '+json.dumps({'type':'response.completed','response':json.loads(response('5'))}).encode()+b'\n\n'
        w.open_voice();w.speech_text.setPlainText('What is 2+3?')
        with self.config():
            QTest.mouseClick(w.ask_speech,Qt.MouseButton.LeftButton)
            self.wait(lambda:bool(self.packets))
            socket=self.connections[0]
            socket.write(f'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {len(first+last)}\r\n\r\n'.encode()+first)
            self.wait(lambda:w.answer.toPlainText()=='5')
            self.assertTrue(w.busy);self.assertIsNone(w.last_exchange)
            socket.write(last);socket.disconnectFromHost()
            self.wait(lambda:not w.busy)
        self.assertEqual(w.last_exchange[1],'5');self.assertIn('first text',w.feedback.text())
        self.assertEqual(len(self.packets),1)

    def test_real_429_retry_header_is_read_without_binding_errors(self):
        w=self.window;self.defer=True
        w.open_voice();w.speech_text.setPlainText('Synthetic question')
        with self.config():
            QTest.mouseClick(w.ask_speech,Qt.MouseButton.LeftButton)
            self.wait(lambda:bool(self.packets))
            socket=self.connections[0]
            socket.write(b'HTTP/1.1 429 Limited\r\nRetry-After: 12\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            socket.disconnectFromHost();self.wait(lambda:not w.busy)
        self.assertIn('12 seconds',w.feedback.text());self.assertTrue(w.request_failed)
