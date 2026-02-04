"""
Test WebSocket face tracking connection
"""
import asyncio
import json
import websockets

async def test_websocket():
    uri = "ws://127.0.0.1:8001/ws/face"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected!\n")
            print("Receiving face tracking data (Ctrl+C to stop):\n")
            print("-" * 80)
            
            count = 0
            face_detected_count = 0
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    count += 1
                    
                    # Check if face is detected
                    if data.get('ok'):
                        face_detected_count += 1
                        print(f"[{count}] ✓ FACE DETECTED")
                        print(f"    Stress Index: {data.get('stressIndex')}")
                        print(f"    Level: {data.get('level')}")
                        print(f"    Blink/min: {data.get('blinkPerMin')}")
                        print(f"    Jaw: {data.get('jawOpenness')}")
                        print(f"    Brow: {data.get('browTension')}")
                    elif data.get('error'):
                        print(f"[{count}] ✗ ERROR: {data.get('error')}")
                    else:
                        print(f"[{count}] ⚠ No face detected")
                    
                    print("-" * 80)
                    
                    if count >= 30:  # Show 30 messages then stop
                        break
                        
                except asyncio.TimeoutError:
                    print("⚠ No data received for 5 seconds")
                    break
            
            print(f"\n=== Summary ===")
            print(f"Total messages: {count}")
            print(f"Face detected: {face_detected_count}")
            if count > 0:
                print(f"Detection rate: {(face_detected_count/count)*100:.1f}%")
            
            if face_detected_count == 0:
                print("\n⚠ TIDAK ADA WAJAH YANG TERDETEKSI")
                print("\nTips:")
                print("1. Posisikan wajah Anda di depan kamera")
                print("2. Pastikan cahaya cukup terang")
                print("3. Jangan terlalu dekat atau jauh dari kamera")
                print("4. Coba jalankan: python test_camera_live.py untuk preview")
                
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
        print("\nPastikan backend sedang running:")
        print("  http://127.0.0.1:8001")
    except ConnectionRefusedError:
        print("✗ Connection refused!")
        print("\nBackend tidak running. Jalankan:")
        print("  .\\start.ps1")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\nStopped by user")
