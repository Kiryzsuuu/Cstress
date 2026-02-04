# CStress

Chat konsultasi dini (non-medis) untuk tingkat stres + ringkasan topik/kesimpulan, terhubung dengan real-time face tracking.

## Stack
- Frontend: React (Vite)
- Backend: Python FastAPI
  - Face tracking: OpenCV + MediaPipe (jalan lokal di mesin kamu)
  - Chat: OpenAI API streaming via SSE

## Setup

### 1) Backend (Python)
Opsi A (disarankan):

```powershell
cd apps\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-face.txt
copy .env.example .env
# edit .env, isi OPENAI_API_KEY
```

Opsi B (kalau kamu terlanjur di root repo):
```powershell
python -m pip install -r requirements.txt
```

Jalankan backend:
```powershell
python -m uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8001 --reload
```

Atau jalankan otomatis (buat venv + install deps + start):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev.ps1 -WithFace
```

Kalau backend sering berhenti karena terminal dipakai untuk command lain, jalankan detached:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev.ps1 -WithFace -Detach
```

Mode auto-reload (opsional, lebih tidak stabil kalau kamera aktif):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev.ps1 -WithFace -Reload
```

Catatan Windows: kalau install `mediapipe`/`opencv-python` gagal (sering terjadi di Python 3.13), pakai Python 3.12 lalu buat ulang venv.

WebSocket face tracking ada di: `ws://127.0.0.1:8001/ws/face`

### 2) Frontend (React)
Di root repo:

```powershell
npm install
npm run dev:web
```

Atau jalankan bareng backend (butuh python + uvicorn sudah tersedia di env aktif):

```powershell
npm run dev
```

Jika UI menampilkan error `Failed to fetch`, biasanya karena Vite dev server berhenti/terminalnya tertutup (request ke `/api/...` tidak bisa diproxy). Pastikan `npm run dev:web` masih berjalan.

## Catatan Privasi
- Kamera diproses lokal oleh Python di perangkat kamu.
- Backend hanya mengirim sinyal numerik (blink/jaw/brow/stressIndex) ke UI.

## Catatan Output Analisis
- Teks chat ditampilkan normal.
- JSON analisis (topik, ringkasan, langkah awal) dikirim sebagai event SSE terpisah dan ditampilkan di panel kanan.

## Disclaimer
Aplikasi ini hanya untuk edukasi/konsultasi dini di luar medis dan bukan diagnosis.
Jika kamu merasa tidak aman, memiliki pikiran menyakiti diri, atau gejala berat, segera hubungi layanan darurat/tenaga profesional.
