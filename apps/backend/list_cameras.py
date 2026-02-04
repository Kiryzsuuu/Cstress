"""
Scan semua kamera yang tersedia di sistem
"""
import cv2

print("=== Scanning Available Cameras ===\n")

available_cameras = []

# Test camera indices 0-10
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            # Get backend name if available
            backend = cap.getBackendName() if hasattr(cap, 'getBackendName') else 'Unknown'
            available_cameras.append({
                'index': i,
                'resolution': f'{w}x{h}',
                'backend': backend
            })
            print(f"✓ Camera {i}: {w}x{h} (Backend: {backend})")
        cap.release()

if not available_cameras:
    print("✗ Tidak ada kamera yang terdeteksi!")
    print("\nTroubleshooting:")
    print("1. Pastikan webcam terhubung dengan benar")
    print("2. Cek Device Manager (devmgmt.msc) di Windows")
    print("3. Pastikan driver kamera terinstall")
    print("4. Coba cabut dan colok ulang webcam (jika external)")
    print("5. Restart komputer")
    print("6. Periksa Windows Settings > Privacy > Camera")
    print("   - Pastikan 'Allow apps to access your camera' ON")
    print("   - Pastikan 'Allow desktop apps to access your camera' ON")
else:
    print(f"\n✓ Total {len(available_cameras)} kamera ditemukan")
    print("\nRekomendasi:")
    print(f"- Gunakan camera index {available_cameras[0]['index']} (default)")
    if len(available_cameras) > 1:
        print(f"- Jika kamera tidak bekerja, coba camera index lain:")
        for cam in available_cameras[1:]:
            print(f"  Set CAMERA_INDEX={cam['index']} di file .env")
    
    print("\nCara mengubah camera index:")
    print("1. Buka file: apps/backend/.env")
    print("2. Tambahkan atau edit: CAMERA_INDEX=0")
    print("3. Restart aplikasi (Ctrl+C lalu ./start.ps1)")
