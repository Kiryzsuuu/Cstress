"""
Interactive camera tester - mencoba setiap kamera dengan preview
Tekan angka (0-9) untuk ganti kamera, 'q' untuk keluar
"""
import cv2
import time
from pathlib import Path

def test_camera(cam_index):
    """Test specific camera index"""
    print(f"\n{'='*60}")
    print(f"Testing Camera {cam_index}")
    print(f"{'='*60}")
    
    cap = cv2.VideoCapture(cam_index)
    
    if not cap.isOpened():
        print(f"✗ Cannot open camera {cam_index}")
        return False
    
    print(f"✓ Camera {cam_index} opened successfully")
    
    # Try to read a frame
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f"✗ Cannot read frame from camera {cam_index}")
        cap.release()
        return False
    
    h, w = frame.shape[:2]
    print(f"✓ Resolution: {w}x{h}")
    
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
        print(f"⚠ MediaPipe error: {e}")
        has_mediapipe = False
        landmarker = None
    
    print(f"\n🎥 Showing live preview from Camera {cam_index}")
    print("   Press 'q' to try another camera")
    print("   Or close window when you find working camera\n")
    
    frame_count = 0
    face_count = 0
    window_name = f'Camera {cam_index} - Press q to switch'
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Cannot read frame")
                break
            
            frame_count += 1
            display = frame.copy()
            
            # Try face detection
            face_detected = False
            if has_mediapipe and landmarker:
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    results = landmarker.detect_for_video(mp_image, int(time.time() * 1000))
                    
                    if results.face_landmarks:
                        face_detected = True
                        face_count += 1
                        lm = results.face_landmarks[0]
                        
                        # Draw landmarks
                        for landmark in lm:
                            x = int(landmark.x * w)
                            y = int(landmark.y * h)
                            cv2.circle(display, (x, y), 1, (0, 255, 0), -1)
                        
                        # Draw bounding box
                        x_coords = [int(lm[i].x * w) for i in range(len(lm))]
                        y_coords = [int(lm[i].y * h) for i in range(len(lm))]
                        x_min, x_max = min(x_coords), max(x_coords)
                        y_min, y_max = min(y_coords), max(y_coords)
                        cv2.rectangle(display, (x_min, y_min), (x_max, y_max), (0, 255, 0), 3)
                        
                        cv2.putText(display, "WAJAH TERDETEKSI!", 
                                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                except Exception:
                    pass
            
            # Status overlay
            cv2.putText(display, f"Camera {cam_index} | {w}x{h}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            if not face_detected:
                cv2.putText(display, "Tidak ada wajah", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            # Stats
            if frame_count > 0:
                rate = (face_count / frame_count) * 100
                color = (0, 255, 0) if rate > 50 else (0, 165, 255) if rate > 0 else (0, 0, 255)
                cv2.putText(display, f"Detection: {rate:.0f}%", 
                           (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            cv2.putText(display, "Press 'q' = next camera, 's' = select this", 
                       (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            cv2.imshow(window_name, display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                print(f"\n✓ Camera {cam_index} selected!")
                print(f"\nCara menggunakan camera ini:")
                print(f"1. Buka: apps/backend/.env")
                print(f"2. Tambah/edit: CAMERA_INDEX={cam_index}")
                print(f"3. Restart: Ctrl+C lalu .\\start.ps1")
                cv2.destroyAllWindows()
                cap.release()
                if landmarker:
                    landmarker.close()
                return True
    
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        cap.release()
        if landmarker:
            landmarker.close()
    
    if frame_count > 0:
        rate = (face_count / frame_count) * 100
        print(f"\nStatistik:")
        print(f"  Frames: {frame_count}")
        print(f"  Wajah terdeteksi: {face_count}")
        print(f"  Detection rate: {rate:.1f}%")
        
        if rate > 50:
            print(f"\n✓ Camera {cam_index} BEKERJA DENGAN BAIK!")
            return True
        elif rate > 0:
            print(f"\n⚠ Camera {cam_index} deteksi kadang-kadang")
            return False
        else:
            print(f"\n✗ Camera {cam_index} tidak mendeteksi wajah")
            return False
    
    return False


if __name__ == "__main__":
    print("="*60)
    print("CSTRESS - CAMERA SELECTOR")
    print("="*60)
    print("\nProgram ini akan mencoba setiap kamera secara berurutan.")
    print("Posisikan wajah Anda di depan kamera untuk testing.\n")
    
    # Try cameras 0-5
    for i in range(6):
        result = test_camera(i)
        if result:
            print(f"\n{'='*60}")
            print(f"✓ SELESAI - Gunakan CAMERA_INDEX={i}")
            print(f"{'='*60}")
            break
        
        if i < 5:
            print(f"\nMencoba camera berikutnya...")
            time.sleep(1)
    
    print("\nProgram selesai.")
