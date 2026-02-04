from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .face_tracker import FaceTracker
from .openai_llm import ANALYSIS_MARKER, stream_chat
from .models import ChatStreamRequest

load_dotenv()

app = FastAPI(title="CStress Backend", version="0.1.0")

# CORS: Allow all localhost origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tracker = FaceTracker()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "openaiConfigured": bool(os.getenv("OPENAI_API_KEY"))}


@app.websocket("/ws/face")
async def ws_face(ws: WebSocket):
    await ws.accept()
    tracker.acquire()
    try:
        fps = int(os.getenv("TRACK_FPS", "10"))
        async for tel in tracker.aiter(fps=fps):
            if tel is None:
                await ws.send_json({"enabled": True, "ok": False})
            else:
                await ws.send_json(
                    {
                        "enabled": True,
                        "ok": (getattr(tel, "error", None) is None)
                        and (tel.stressIndex is not None or tel.blinkPerMin is not None or tel.jawOpenness is not None),
                        "ts": tel.ts,
                        "blinkPerMin": tel.blinkPerMin,
                        "blinkPer10s": getattr(tel, "blinkPer10s", None),
                        "jawOpenness": tel.jawOpenness,
                        "browTension": tel.browTension,
                        "stressIndex": tel.stressIndex,
                        "level": tel.level,
                        "error": getattr(tel, "error", None),
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        tracker.release()


@app.post("/api/chat/stream")
async def chat_stream(body: ChatStreamRequest):
    async def event_stream():
        # Initial ping
        yield "event: ping\n"
        yield f"data: {json.dumps({'t': __import__('time').time()})}\n\n"

        try:
            carry = ""
            analysis_started = False
            analysis_buffer = ""

            async for token in stream_chat(body.messages, body.faceSignals):
                if analysis_started:
                    analysis_buffer += token
                    continue

                carry += token
                idx = carry.find(ANALYSIS_MARKER)
                if idx >= 0:
                    # Emit everything before marker, then switch to analysis buffering.
                    visible = carry[:idx]
                    if visible:
                        yield "event: token\n"
                        yield f"data: {json.dumps({'token': visible})}\n\n"
                    analysis_started = True
                    analysis_buffer = carry[idx + len(ANALYSIS_MARKER) :]
                    carry = ""
                    continue

                # Emit safe portion, keep a tail to catch marker across chunk boundaries.
                safe_len = max(0, len(carry) - (len(ANALYSIS_MARKER) + 8))
                if safe_len > 0:
                    visible = carry[:safe_len]
                    carry = carry[safe_len:]
                    yield "event: token\n"
                    yield f"data: {json.dumps({'token': visible})}\n\n"

            # Flush any remaining visible carry (only if marker never appeared)
            if carry and not analysis_started:
                yield "event: token\n"
                yield f"data: {json.dumps({'token': carry})}\n\n"

            # Try parse analysis JSON
            if analysis_started:
                raw = analysis_buffer.strip()
                print(f"[DEBUG] Analysis buffer received: {raw[:200]}...")  # Debug log
                # Some models might add whitespace; ensure we parse the outermost object.
                start = raw.find("{")
                end = raw.rfind("}")
                if start >= 0 and end > start:
                    raw_obj = raw[start : end + 1]
                    try:
                        analysis = json.loads(raw_obj)
                        print(f"[DEBUG] Successfully parsed analysis: {analysis}")  # Debug log
                        yield "event: analysis\n"
                        yield f"data: {json.dumps({'analysis': analysis})}\n\n"
                    except Exception as parse_err:
                        print(f"[ERROR] Failed to parse analysis JSON: {parse_err}")  # Debug log
                        pass

            yield "event: done\n"
            yield f"data: {json.dumps({'ok': True})}\n\n"
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
