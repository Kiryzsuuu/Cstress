from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve
from typing import Any, Optional

from .stress import StressSignals, compute_stress_index

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


@dataclass
class FaceTelemetry:
    ts: float
    blinkPerMin: Optional[float]
    blinkPer10s: Optional[float]
    jawOpenness: Optional[float]
    browTension: Optional[float]
    stressIndex: Optional[float]
    level: Optional[str]
    error: Optional[str] = None


def _try_import_deps() -> tuple[Any, Any, Any, Any, Any, Optional[str]]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import mediapipe as mp  # type: ignore
        from mediapipe.tasks.python import vision  # type: ignore
        from mediapipe.tasks.python.core import base_options  # type: ignore

        return cv2, mp, np, vision, base_options, None
    except Exception as e:  # pragma: no cover
        return None, None, None, None, None, str(e)


def _ensure_face_landmarker_model(model_path: Path) -> tuple[bool, str | None]:
    if model_path.exists() and model_path.stat().st_size > 1024:
        return True, None

    model_path.parent.mkdir(parents=True, exist_ok=True)

    urls = [
        # Primary (most common) path
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        # Fallback
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float32/1/face_landmarker.task",
    ]

    last_err: str | None = None
    for url in urls:
        try:
            urlretrieve(url, model_path.as_posix())
            if model_path.exists() and model_path.stat().st_size > 1024:
                return True, None
        except Exception as e:  # pragma: no cover
            last_err = str(e)

    return False, last_err or "failed to download model"


class FaceTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Optional[FaceTelemetry] = None
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._refcount = 0

        self._blink_events: list[float] = []
        self._eye_closed = False
        self._last_frame_ts: float | None = None
        
        # Smoothing for more stable readings (EMA)
        self._smooth_jaw: float | None = None
        self._smooth_brow: float | None = None
        self._smooth_alpha = 0.3  # Smoothing factor (lower = more smoothing)

    def acquire(self) -> None:
        with self._lock:
            self._refcount += 1
            if self._thread is None:
                self._stop_evt.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()

    def release(self) -> None:
        with self._lock:
            self._refcount = max(0, self._refcount - 1)
            if self._refcount == 0:
                self._stop_evt.set()
                self._thread = None

    def latest(self) -> Optional[FaceTelemetry]:
        with self._lock:
            return self._latest

    async def aiter(self, fps: int = 10):
        interval = 1.0 / max(1, fps)
        while not self._stop_evt.is_set():
            yield self.latest()
            await asyncio.sleep(interval)

    def _run(self) -> None:
        cv2, mp, np, vision, base_options, dep_err = _try_import_deps()
        if dep_err or cv2 is None or mp is None or np is None or vision is None or base_options is None:
            # Dependencies missing (common on some Python versions). Keep backend alive; tracking becomes unavailable.
            while not self._stop_evt.is_set():
                with self._lock:
                    self._latest = FaceTelemetry(
                        time.time(),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        error=dep_err or "missing face-tracking dependencies",
                    )
                time.sleep(1.0)
            return

        def dist(a: 'np.ndarray', b: 'np.ndarray') -> float:
            return float(np.linalg.norm(a - b))

        # MediaPipe Tasks needs a model file.
        backend_root = Path(__file__).resolve().parents[1]
        default_model = backend_root / "models" / "face_landmarker.task"
        model_path = Path(os.getenv("FACE_LANDMARKER_MODEL", str(default_model)))
        ok_model, model_err = _ensure_face_landmarker_model(model_path)
        if not ok_model:
            while not self._stop_evt.is_set():
                with self._lock:
                    self._latest = FaceTelemetry(
                        time.time(),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        error=model_err or "model download failed",
                    )
                time.sleep(1.0)
            return

        cam_index = int(os.getenv("CAMERA_INDEX", "0"))
        track_fps = int(os.getenv("TRACK_FPS", "10"))
        min_interval = 1.0 / max(1, track_fps)

        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            # Could not open camera; keep publishing None.
            while not self._stop_evt.is_set():
                with self._lock:
                    self._latest = FaceTelemetry(
                        time.time(),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        error=f"camera not available (CAMERA_INDEX={cam_index})",
                    )
                time.sleep(1.0)
            return

        options = vision.FaceLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)

        try:
            while not self._stop_evt.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = landmarker.detect_for_video(mp_image, int(time.time() * 1000))

                blink_per_min: Optional[float] = None
                blink_per_10s: Optional[float] = None
                jaw_openness: Optional[float] = None
                brow_tension: Optional[float] = None

                if results.face_landmarks:
                    h, w = frame.shape[:2]
                    lm = results.face_landmarks[0]

                    def pt(i: int) -> np.ndarray:
                        return np.array([lm[i].x * w, lm[i].y * h], dtype=np.float32)

                    # Eye Aspect Ratio-ish (left eye)
                    # Landmarks: 33, 160, 158, 133, 153, 144 (common set)
                    p1, p2, p3, p4, p5, p6 = pt(33), pt(160), pt(158), pt(133), pt(153), pt(144)
                    ear = (dist(p2, p6) + dist(p3, p5)) / (2.0 * dist(p1, p4) + 1e-6)

                    # Blink detection with threshold + hysteresis
                    now = time.time()
                    if self._last_frame_ts is None:
                        self._last_frame_ts = now

                    # Slightly more sensitive thresholds
                    close_th = 0.20
                    open_th = 0.225
                    if not self._eye_closed and ear < close_th:
                        self._eye_closed = True
                    elif self._eye_closed and ear > open_th:
                        self._eye_closed = False
                        self._blink_events.append(now)

                    # Keep last 60s
                    cutoff = now - 60.0
                    self._blink_events = [t for t in self._blink_events if t >= cutoff]
                    blink_per_min = float(len(self._blink_events))

                    # Short-window count for more responsive UI
                    cutoff10 = now - 10.0
                    blink_per_10s = float(sum(1 for t in self._blink_events if t >= cutoff10))

                    # Jaw openness: distance between upper/lower inner lip normalized by nose-chin distance
                    upper = pt(13)  # upper lip
                    lower = pt(14)  # lower lip
                    nose = pt(1)
                    chin = pt(152)
                    mouth_open = dist(upper, lower)
                    face_scale = dist(nose, chin) + 1e-6
                    # Scale for UI sensitivity
                    jaw_raw = float(np.clip(mouth_open / face_scale * 6.0, 0.0, 1.0))
                    # Apply exponential moving average smoothing
                    if self._smooth_jaw is None:
                        self._smooth_jaw = jaw_raw
                    else:
                        self._smooth_jaw = self._smooth_alpha * jaw_raw + (1 - self._smooth_alpha) * self._smooth_jaw
                    jaw_openness = self._smooth_jaw

                    # Brow tension: eyebrow-eye distance (smaller distance => more tension) normalized
                    brow = pt(105)
                    eye_top = pt(159)
                    brow_dist = dist(brow, eye_top)
                    # Normalize with face scale
                    norm = brow_dist / (face_scale + 1e-6)
                    # Map: smaller norm -> higher tension
                    brow_raw = float(np.clip((0.043 - norm) / 0.02, 0.0, 1.0))
                    # Apply exponential moving average smoothing
                    if self._smooth_brow is None:
                        self._smooth_brow = brow_raw
                    else:
                        self._smooth_brow = self._smooth_alpha * brow_raw + (1 - self._smooth_alpha) * self._smooth_brow
                    brow_tension = self._smooth_brow

                stress_idx, level = compute_stress_index(
                    StressSignals(blink_per_min=blink_per_min, jaw_openness=jaw_openness, brow_tension=brow_tension)
                )

                tel = FaceTelemetry(
                    ts=time.time(),
                    blinkPerMin=blink_per_min,
                    blinkPer10s=blink_per_10s,
                    jawOpenness=jaw_openness,
                    browTension=brow_tension,
                    stressIndex=stress_idx,
                    level=level,
                    error=None,
                )
                with self._lock:
                    self._latest = tel

                dt = time.time() - t0
                if dt < min_interval:
                    time.sleep(min_interval - dt)
        finally:
            landmarker.close()
            cap.release()
