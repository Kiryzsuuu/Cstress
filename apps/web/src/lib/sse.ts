export type SseEvent = {
  event: string
  data: any
}

export async function fetchSse(
  url: string,
  init: RequestInit,
  onEvent: (evt: SseEvent) => void,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    throw new Error(`Network error: ${msg}`)
  }
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')

  let buffer = ''
  let currentEvent = 'message'

  const emit = (raw: string) => {
    // Parse a single SSE message block
    const lines = raw.split(/\r?\n/)
    let dataLines: string[] = []
    currentEvent = 'message'

    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }

    const dataStr = dataLines.join('\n')
    let data: any = dataStr
    try {
      data = dataStr ? JSON.parse(dataStr) : null
    } catch {
      // keep as string
    }

    onEvent({ event: currentEvent, data })
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const trimmed = chunk.trim()
      if (trimmed) emit(trimmed)
    }
  }
}
