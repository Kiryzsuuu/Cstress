"""
Skrip diagnostik untuk memeriksa akses kamera
Jalankan dengan: python test_camera.py atau .venv/Scripts/python test_camera.py
"""
import sys

print("=== CStress Camera Diagnostic ===\n")

# 1. Cek dependencies
print("1. Checking dependencies...")
try:
    import cv2
    print(f"   ✓ OpenCV version: {cv2.__version__}")
except ImportError as e:
    print(f"   ✗ OpenCV not installed: {e}")
    print("   Install: pip install opencv-python")
    sys.exit(1)

try:
    import mediapipe as mp
    print(f"   ✓ MediaPipe installed")
except ImportError as e:
    print(f"   ✗ MediaPipe not installed: {e}")
    print("   Install: pip install mediapipe")
    sys.exit(1)

# 2. Cek kamera
print("\n2. Checking camera access...")
cam_index = 0
cap = cv2.VideoCapture(cam_index)

if not cap.isOpened():
    print(f"   ✗ Cannot open camera at index {cam_index}")
    print("\n   Troubleshooting:")
    print("   - Pastikan webcam terhubung")
    print("   - Pastikan tidak ada aplikasi lain yang menggunakan kamera")
    print("   - Coba camera index lain: CAMERA_INDEX=1 di .env")
    print("   - Periksa permission kamera di Windows Settings")
    sys.exit(1)

print(f"   ✓ Camera opened successfully at index {cam_index}")

# 3. Test capture frame
print("\n3. Testing frame capture...")
ret, frame = cap.read()
if not ret or frame is None:
    print("   ✗ Cannot read frame from camera")
    cap.release()
    sys.exit(1)

h, w, c = frame.shape
print(f"   ✓ Frame captured: {w}x{h}, {c} channels")

# 4. Cek model MediaPipe
print("\n4. Checking MediaPipe face landmarker model...")
from pathlib import Path
import os

backend_root = Path(__file__).resolve().parents[0]
model_path = backend_root / "models" / "face_landmarker.task"
print(f"   Model path: {model_path}")

if not model_path.exists():
    print("   ⚠ Model file not found, will be downloaded on first run")
else:
    size_mb = model_path.stat().st_size / (1024 * 1024)
    print(f"   ✓ Model exists ({size_mb:.1f} MB)")

# 5. Test MediaPipe detection
print("\n5. Testing MediaPipe face detection...")
try:
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options
    
    if not model_path.exists():
        print("   Downloading model...")
        from urllib.request import urlretrieve
        model_path.parent.mkdir(parents=True, exist_ok=True)
        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        urlretrieve(url, model_path.as_posix())
        print("   ✓ Model downloaded")
    
    options = vision.FaceLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    
    # Convert to RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    
    import time
    results = landmarker.detect_for_video(mp_image, int(time.time() * 1000))
    
    if results.face_landmarks:
        print(f"   ✓ Face detected! ({len(results.face_landmarks[0])} landmarks)")
    else:
        print("   ⚠ No face detected in frame")
        print("   Tip: Pastikan wajah terlihat jelas di kamera")
    
    landmarker.close()
    
except Exception as e:
    print(f"   ✗ MediaPipe error: {e}")
    cap.release()
    sys.exit(1)

cap.release()

print("\n" + "="*50)
print("✓ All checks passed!")
print("="*50)
print("\nCamera is working correctly.")
print("If face tracking still doesn't work in the app:")
print("1. Make sure backend is running: http://127.0.0.1:8001")
print("2. Check WebSocket connection in browser console")
print("3. Enable face tracking toggle in the app")
print("4. Position your face clearly in front of camera")
