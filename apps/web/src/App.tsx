import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { fetchSse } from './lib/sse'
import { useFaceSignals } from './hooks/useFaceSignals'
import { exportToPDF } from './lib/pdfExport'

type Role = 'user' | 'assistant'

type ChatMessage = {
  role: Role
  content: string
}

type Analysis = {
  topics: string[]
  summary: string
  stress_level: 'rendah' | 'sedang' | 'tinggi'
  chat_sentiment?: 'positif' | 'netral' | 'negatif'
  early_actions: string[]
  when_to_seek_help: string[]
  disclaimer: string
}

function tryExtractAnalysis(text: string): Analysis | null {
  // Look for [[ANALYSIS_JSON]] marker
  const marker = '[[ANALYSIS_JSON]]'
  const idx = text.indexOf(marker)
  if (idx >= 0) {
    const jsonPart = text.slice(idx + marker.length).trim()
    try {
      const obj = JSON.parse(jsonPart) as { analysis?: Analysis } | Analysis
      if ((obj as any).analysis?.topics) return (obj as any).analysis as Analysis
      if ((obj as any).topics) return obj as Analysis
    } catch {
      // fallback
    }
  }
  
  // Fallback: try last JSON block
  const lastIdx = text.lastIndexOf('{')
  if (lastIdx < 0) return null
  const tail = text.slice(lastIdx)
  try {
    const obj = JSON.parse(tail) as { analysis?: Analysis } | Analysis
    if ((obj as any).analysis?.topics) return (obj as any).analysis as Analysis
    if ((obj as any).topics) return obj as Analysis
    return null
  } catch {
    return null
  }
}

export default function App() {
  const [showLanding, setShowLanding] = useState(true)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Hai, aku di sini untuk mendengarkan kamu.\n\nApa yang sedang kamu rasakan sekarang? Cerita aja dengan nyaman - tidak ada yang perlu kamu sembunyikan. Aku akan mendengarkan dengan penuh perhatian dan membantu kamu menemukan cara untuk merasa lebih baik.\n\nIngat, kamu tidak sendirian.'
    }
  ])
  const [isStreaming, setIsStreaming] = useState(false)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [analysisUpdated, setAnalysisUpdated] = useState(false)
  const [trackingEnabled, setTrackingEnabled] = useState(true)

  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? (import.meta.env.DEV ? 'http://localhost:8001' : '')
  const chatUrl = apiBase ? `${apiBase}/api/chat/stream` : '/api/chat/stream'

  const { status: faceStatus, latest: faceLatest } = useFaceSignals({
    enabled: trackingEnabled,
    url: 'ws://localhost:8001/ws/face'
  })

  const canSend = input.trim().length > 0 && !isStreaming
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isStreaming])

  const faceSignals = useMemo(() => {
    if (!trackingEnabled || !faceLatest?.ok) return undefined
    return {
      enabled: true,
      stressIndex: faceLatest.stressIndex ?? undefined,
      level: faceLatest.level ?? undefined,
      blinkPerMin: faceLatest.blinkPerMin ?? undefined,
      jawOpenness: faceLatest.jawOpenness ?? undefined,
      browTension: faceLatest.browTension ?? undefined
    }
  }, [trackingEnabled, faceLatest])

  async function onSend() {
    if (!canSend) return

    const userText = input.trim()
    setInput('')
    setAnalysis(null)

    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: userText }, { role: 'assistant', content: '' }]
    setMessages(nextMessages)
    setIsStreaming(true)

    const assistantIndex = nextMessages.length - 1
    const bufferRef = { text: '' }
    let receivedAnalysis = false
    let raf: number | null = null

    const flush = () => {
      raf = null
      setMessages((prev) => {
        const copy = prev.slice()
        const current = copy[assistantIndex]
        if (!current || current.role !== 'assistant') return prev
        copy[assistantIndex] = { ...current, content: bufferRef.text }
        return copy
      })
    }

    try {
      await fetchSse(chatUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: nextMessages
            .slice(0, -1)
            .map((m) => ({ role: m.role, content: m.content }))
            // Backend supports 'system' but UI doesn't send it.
            .map((m) => m),
          faceSignals
        })
      }, (evt) => {
        console.log('SSE Event received:', evt.event, evt.data) // Debug log
        if (evt.event === 'token') {
          bufferRef.text += evt.data.token
          if (raf == null) raf = requestAnimationFrame(flush)
        }
        if (evt.event === 'analysis') {
          const a = evt.data?.analysis as Analysis | undefined
          console.log('Received analysis event:', a)
          if (a?.topics && a?.summary) {
            receivedAnalysis = true
            setAnalysis(a)
            setAnalysisUpdated(true)
            // Reset animation after 2 seconds
            setTimeout(() => setAnalysisUpdated(false), 2000)
          } else {
            console.warn('Analysis event received but incomplete:', evt.data)
          }
        }
        if (evt.event === 'done') {
          // final flush
          if (raf != null) cancelAnimationFrame(raf)
          flush()
          console.log('Stream done. Final text length:', bufferRef.text.length) // Debug log
        }
        if (evt.event === 'error') {
          throw new Error(evt.data?.message || 'Backend error')
        }
      })

      const finalText = bufferRef.text
      console.log('Final text preview:', finalText.slice(-500)) // Show last 500 chars
      if (!receivedAnalysis) {
        console.log('No analysis event received, trying to extract from text...')
        const extracted = tryExtractAnalysis(finalText)
        if (extracted) {
          console.log('Successfully extracted analysis from text:', extracted)
          setAnalysis(extracted)
          setAnalysisUpdated(true)
          setTimeout(() => setAnalysisUpdated(false), 2000)
        } else {
          console.warn('Failed to extract analysis from text')
        }
      } else {
        console.log('Analysis already received via event')
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setMessages((prev) => {
        const copy = prev.slice()
        const current = copy[assistantIndex]
        if (current?.role === 'assistant') {
          copy[assistantIndex] = { role: 'assistant', content: `Maaf, terjadi kendala: ${msg}` }
        }
        return copy
      })
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleExportPDF() {
    if (!analysis) {
      alert('Belum ada analisis untuk diekspor. Kirim pesan terlebih dahulu.')
      return
    }
    
    try {
      await exportToPDF(
        analysis,
        {
          stressIndex: faceLatest?.stressIndex,
          level: faceLatest?.level,
          blinkPerMin: faceLatest?.blinkPerMin,
          blinkPer10s: faceLatest?.blinkPer10s,
          jawOpenness: faceLatest?.jawOpenness,
          browTension: faceLatest?.browTension,
        },
        messages
      )
    } catch (e) {
      alert('Gagal membuat PDF: ' + (e instanceof Error ? e.message : 'Unknown error'))
    }
  }

  if (showLanding) {
    return (
      <div className="landingShell">
        <video 
          autoPlay 
          loop 
          muted 
          playsInline 
          className="landingVideo"
        >
          <source src="https://cdn.pixabay.com/video/2022/01/26/105884-669092792_large.mp4" type="video/mp4" />
        </video>
        <div className="landingOverlay"></div>
        <div className="landingContainer">
          <div className="landingLogo">
            <div className="logoCircle">C</div>
            <div className="logoText">Stress</div>
          </div>
          <p className="landingTagline">Konsultasi dini non-medis dengan dukungan face tracking lokal</p>
          <button className="startBtn" onClick={() => setShowLanding(false)}>
            Mulai Bercerita
          </button>
          <div className="landingFooter">
            <img 
              src="https://i.pinimg.com/736x/56/74/cd/5674cd4533352b347fefeb2dc37bcd71.jpg" 
              alt="Telkom University" 
              className="telkomLogo"
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="appShell">
      <header className="topbar">
        <div className="brand">
          <img 
            src="https://i.pinimg.com/736x/56/74/cd/5674cd4533352b347fefeb2dc37bcd71.jpg" 
            alt="Telkom University" 
            className="brandLogo"
          />
          <div>
            <div className="brandTitle">CStress</div>
            <div className="brandSub">Konsultasi dini non-medis + face tracking (lokal)</div>
          </div>
        </div>
        <div className="topbarRight">
          <label className="toggle">
            <input type="checkbox" checked={trackingEnabled} onChange={(e) => setTrackingEnabled(e.target.checked)} />
            <span>Face tracking</span>
          </label>
        </div>
      </header>

      <main className="content">
        <section className="chatPanel">
          <div className="chatHeader">
            <div className="chatTitle">Chat</div>
            <div className="chatMeta">
              <span className={`pill ${faceStatus === 'connected' ? 'pillOk' : faceStatus === 'disabled' ? 'pillMuted' : 'pillWarn'}`}>
                Tracking: {faceStatus}
              </span>
              {trackingEnabled && !faceLatest?.ok && faceLatest?.error && (
                <span className="pill pillWarn">{faceLatest.error}</span>
              )}
              {faceLatest?.ok && (
                <span className="pill pillInfo">
                  Stres (indikatif): {faceLatest.level ?? '-'} {faceLatest.stressIndex != null ? `(${Math.round(faceLatest.stressIndex)})` : ''}
                </span>
              )}
            </div>
          </div>

          <div className="chatList" ref={listRef}>
            {messages.map((m, i) => (
              <div key={i} className={`msgRow ${m.role === 'user' ? 'msgRight' : 'msgLeft'}`}>
                <div className={`msgBubble ${m.role === 'user' ? 'bubbleUser' : 'bubbleBot'}`}>
                  <div className="msgText">{m.content || (m.role === 'assistant' && isStreaming && i === messages.length - 1 ? '…' : '')}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="composer">
            <textarea
              className="composerInput"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Tulis ceritamu di sini... Aku siap mendengarkan (Enter untuk kirim, Shift+Enter baris baru)"
              rows={3}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void onSend()
                }
              }}
            />
            <div className="composerActions">
              <div className="hint">
                Konseling non-medis. Untuk kondisi darurat/serius, hubungi 119 atau psikolog profesional.
              </div>
              <button className="sendBtn" onClick={() => void onSend()} disabled={!canSend}>
                {isStreaming ? 'Mendengarkan…' : 'Kirim'}
              </button>
            </div>
          </div>
        </section>

        <aside className="sidePanel">
          <div className="card">
            <div className="cardTitle">Realtime Signals</div>
            <div className="grid2">
              <div className="kv">
                <div className="k">Blink/10s</div>
                <div className="v">
                  {faceLatest?.blinkPer10s != null ? faceLatest.blinkPer10s.toFixed(0) : faceLatest?.blinkPerMin != null ? faceLatest.blinkPerMin.toFixed(0) : '-'}
                </div>
              </div>
              <div className="kv">
                <div className="k">Jaw</div>
                <div className="v">{faceLatest?.jawOpenness != null ? faceLatest.jawOpenness.toFixed(2) : '-'}</div>
              </div>
              <div className="kv">
                <div className="k">Brow</div>
                <div className="v">{faceLatest?.browTension != null ? faceLatest.browTension.toFixed(2) : '-'}</div>
              </div>
              <div className="kv">
                <div className="k">Index</div>
                <div className="v">{faceLatest?.stressIndex != null ? Math.round(faceLatest.stressIndex) : '-'}</div>
              </div>
            </div>
            <div className="muted">
              Ini sinyal indikatif dari wajah (lokal), bukan diagnosis.
            </div>
          </div>

          <div className={`card ${analysisUpdated ? 'cardUpdated' : ''}`}>
            <div className="cardTitle">
              Topik & Kesimpulan
              {analysisUpdated && <span className="updatedBadge">Updated</span>}
            </div>
            {analysis ? (
              <>
                <div className="chips">
                  {analysis.topics?.slice(0, 8).map((t) => (
                    <span key={t} className="chip">
                      {t}
                    </span>
                  ))}
                </div>
                {analysis.chat_sentiment && (
                  <>
                    <div className="sectionTitle">Sentimen Chat</div>
                    <div className="textBlock">
                      <span className={`sentimentBadge sentiment-${analysis.chat_sentiment}`}>
                        {analysis.chat_sentiment}
                      </span>
                    </div>
                  </>
                )}
                <div className="sectionTitle">Ringkasan</div>
                <div className="textBlock">{analysis.summary}</div>
                <div className="sectionTitle">Langkah awal</div>
                <ul className="list">
                  {analysis.early_actions?.slice(0, 6).map((a, idx) => (
                    <li key={idx}>{a}</li>
                  ))}
                </ul>
                <div className="sectionTitle">Kapan cari bantuan</div>
                <ul className="list">
                  {analysis.when_to_seek_help?.slice(0, 6).map((a, idx) => (
                    <li key={idx}>{a}</li>
                  ))}
                </ul>
                <div className="muted">{analysis.disclaimer}</div>
                <button className="exportBtn" onClick={() => void handleExportPDF()}>
                  Export PDF
                </button>
              </>
            ) : (
              <div className="muted">Analisis akan muncul setelah asisten menjawab.</div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}
