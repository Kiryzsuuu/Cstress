"""
Live camera test dengan preview visual
Tekan 'q' untuk keluar
"""
import cv2
import time
from pathlib import Path

print("=== Live Camera Test ===")
print("Membuka kamera...")

cam_index = 0
cap = cv2.VideoCapture(cam_index)

if not cap.isOpened():
    print(f"ERROR: Cannot open camera at index {cam_index}")
    exit(1)

print(f"✓ Camera opened at index {cam_index}")
print("\nWindow akan terbuka. Tekan 'q' untuk keluar.")
print("Posisikan wajah Anda di depan kamera.\n")

# Load MediaPipe
try:
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options
    
    backend_root = Path(__file__).resolve().parents[0]
    model_path = backend_root / "models" / "face_landmarker.task"
    
    options = vision.FaceLandmarkerOptions(
        base_options=base_options.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    has_mediapipe = True
    print("✓ MediaPipe loaded")
except Exception as e:
    print(f"⚠ MediaPipe not available: {e}")
    has_mediapipe = False

frame_count = 0
face_detected_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Cannot read frame")
        break
    
    frame_count += 1
    display_frame = frame.copy()
    
    # Add status text
    h, w = frame.shape[:2]
    cv2.putText(display_frame, f"Camera {cam_index} | {w}x{h}", 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Try face detection with MediaPipe
    if has_mediapipe:
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = landmarker.detect_for_video(mp_image, int(time.time() * 1000))
            
            if results.face_landmarks:
                face_detected_count += 1
                lm = results.face_landmarks[0]
                
                # Draw landmarks
                for idx, landmark in enumerate(lm):
                    x = int(landmark.x * w)
                    y = int(landmark.y * h)
                    cv2.circle(display_frame, (x, y), 1, (0, 255, 0), -1)
                
                # Draw bounding box
                x_coords = [int(lm[i].x * w) for i in range(len(lm))]
                y_coords = [int(lm[i].y * h) for i in range(len(lm))]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                cv2.rectangle(display_frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                
                cv2.putText(display_frame, "FACE DETECTED!", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "No face detected", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        except Exception as e:
            cv2.putText(display_frame, f"Error: {str(e)[:50]}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    # Show stats
    if frame_count > 0:
        detection_rate = (face_detected_count / frame_count) * 100
        cv2.putText(display_frame, f"Detection rate: {detection_rate:.1f}%", 
                   (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    cv2.putText(display_frame, "Press 'q' to quit", 
               (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    cv2.imshow('CStress Camera Test', display_frame)
    
    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

if has_mediapipe:
    landmarker.close()

print(f"\n=== Summary ===")
print(f"Total frames: {frame_count}")
print(f"Faces detected: {face_detected_count}")
if frame_count > 0:
    print(f"Detection rate: {(face_detected_count/frame_count)*100:.1f}%")
