import { useEffect, useMemo, useRef, useState } from 'react'

export type FaceTelemetry = {
  enabled: boolean
  ok: boolean
  ts?: number
  blinkPerMin?: number | null
  blinkPer10s?: number | null
  jawOpenness?: number | null
  browTension?: number | null
  stressIndex?: number | null
  level?: string | null
  error?: string | null
}

type Status = 'disabled' | 'connecting' | 'connected' | 'error'

export function useFaceSignals(opts: { enabled: boolean; url: string }) {
  const [status, setStatus] = useState<Status>(opts.enabled ? 'connecting' : 'disabled')
  const [latest, setLatest] = useState<FaceTelemetry | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number | null>(null)

  const enabled = opts.enabled
  const url = opts.url

  const connect = () => {
    if (!enabled) return

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as FaceTelemetry
        setLatest(data)
      } catch {
        // ignore
      }
    }
    ws.onerror = () => setStatus('error')
    ws.onclose = () => {
      wsRef.current = null
      if (!enabled) return
      setStatus('error')
      // simple reconnect backoff
      if (retryRef.current) window.clearTimeout(retryRef.current)
      retryRef.current = window.setTimeout(connect, 800)
    }
  }

  useEffect(() => {
    if (!enabled) {
      setStatus('disabled')
      setLatest(null)
      if (retryRef.current) window.clearTimeout(retryRef.current)
      retryRef.current = null
      wsRef.current?.close()
      wsRef.current = null
      return
    }

    connect()

    return () => {
      if (retryRef.current) window.clearTimeout(retryRef.current)
      retryRef.current = null
      wsRef.current?.close()
      wsRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url])

  const safeLatest = useMemo(() => latest, [latest])
  return { status, latest: safeLatest }
}
