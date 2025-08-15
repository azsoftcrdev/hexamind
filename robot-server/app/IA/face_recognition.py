# app/ai/face_recognition.py
import cv2
import numpy as np
from types import SimpleNamespace

class FaceDetector:
    def __init__(self, score_thresh=0.6, nms_thresh=0.3, top_k=5000, input_size=(320, 320)):
        self.input_size = tuple(input_size)
        self.score_thresh = float(score_thresh)
        self.nms_thresh = float(nms_thresh)
        self.top_k = int(top_k)
        self.yunet = None
        self._try_init_yunet()
        # fallback cascadas (por si no hay contrib)
        if self.yunet is None:
            self.frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            self.profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

    def _try_init_yunet(self):
        # YuNet está en OpenCV contrib (cv2.FaceDetectorYN_create)
        if hasattr(cv2, "FaceDetectorYN_create"):
            try:
                # en muchas builds YuNet viene “embebido”, se pasa vacío en model=
                self.yunet = cv2.FaceDetectorYN_create(
                    model="",
                    config="",
                    input_size=self.input_size,
                    score_threshold=self.score_thresh,
                    nms_threshold=self.nms_thresh,
                    top_k=self.top_k
                )
            except Exception:
                self.yunet = None

    def _detect_yunet(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        if self.yunet is None:
            return []
        # YuNet necesita que le fijes el tamaño de entrada si cambia
        self.yunet.setInputSize((w, h))
        faces, _ = self.yunet.detect(frame_bgr)
        if faces is None:
            return []
        # faces: Nx15 [x,y,w,h,score, lmk(10)]
        out = []
        for f in faces:
            x, y, w0, h0, score = f[:5]
            if score < self.score_thresh: 
                continue
            out.append([int(x), int(y), int(w0), int(h0), float(score)])
        return out

    def _detect_cascades_multi_pose(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray_eq = cv2.equalizeHist(gray)
        bboxes = []

        # frontal
        for (x,y,w,h) in self.frontal.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=5, minSize=(60,60)):
            bboxes.append([x,y,w,h,1.0])

        # perfil izquierdo (modelo detecta “perfil izquierdo”)
        for (x,y,w,h) in self.profile.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=5, minSize=(60,60)):
            bboxes.append([x,y,w,h,1.0])

        # perfil derecho: voltear imagen y re-proyectar
        gray_flip = cv2.flip(gray_eq, 1)
        w_img = gray_eq.shape[1]
        for (x,y,w,h) in self.profile.detectMultiScale(gray_flip, scaleFactor=1.1, minNeighbors=5, minSize=(60,60)):
            # reproyección horizontal
            x_reproj = w_img - (x + w)
            bboxes.append([x_reproj,y,w,h,1.0])

        return bboxes

    def process_frame(self, frame_bgr, draw=True):
        # 1) intenta YuNet
        bboxes = self._detect_yunet(frame_bgr)
        # 2) si no hay YuNet o no encontró nada, usa cascadas combinadas
        if not bboxes:
            bboxes = self._detect_cascades_multi_pose(frame_bgr)

        out = frame_bgr.copy()
        for (x,y,w,h,score) in bboxes:
            if draw:
                cv2.rectangle(out, (x,y), (x+w,y+h), (0,255,0), 2)
                cv2.putText(out, f"{score:.2f}", (x, max(0,y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        return SimpleNamespace(frame=out, bboxes=bboxes)
