export type WsMessage = {
  kind: 'job' | 'recording' | 'live_status'
  [key: string]: any
}

type Listener = (msg: WsMessage) => void
const listeners = new Set<Listener>()
let socket: WebSocket | null = null

export function connectWs() {
  if (socket && socket.readyState <= WebSocket.OPEN) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${proto}://${location.host}/ws`)
  socket.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      listeners.forEach((l) => l(msg))
    } catch { /* ignore malformed frames */ }
  }
  socket.onclose = () => setTimeout(connectWs, 3000)
  const ping = setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
    else clearInterval(ping)
  }, 25000)
}

export function onWs(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
