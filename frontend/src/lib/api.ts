const BASE = '/api'

async function req<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  get: <T = any>(path: string) => req<T>('GET', path),
  post: <T = any>(path: string, body?: unknown) => req<T>('POST', path, body),
  put: <T = any>(path: string, body?: unknown) => req<T>('PUT', path, body),
  patch: <T = any>(path: string, body?: unknown) => req<T>('PATCH', path, body),
  del: <T = any>(path: string) => req<T>('DELETE', path),
}

export function mediaUrl(filePath: string | null | undefined): string {
  if (!filePath) return ''
  // Backend serves the data/ directory under /media; map absolute paths.
  const idx = filePath.replace(/\\/g, '/').lastIndexOf('/data/')
  if (idx >= 0) return '/media' + filePath.replace(/\\/g, '/').slice(idx + 5)
  return ''
}
