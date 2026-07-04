import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { onWs } from '../lib/ws'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'

export default function Live() {
  const { t } = useI18n()
  const [status, setStatus] = useState<any>(null)
  const [handle, setHandle] = useState('')
  const [error, setError] = useState('')

  const refresh = () => api.get('/live/status').then(setStatus).catch(() => {})

  useEffect(() => {
    refresh()
    const off = onWs((m) => {
      if (m.kind === 'recording' || m.kind === 'live_status') refresh()
    })
    const iv = setInterval(refresh, 15000)
    return () => { off(); clearInterval(iv) }
  }, [])

  const act = (fn: () => Promise<any>) => fn().then(refresh).catch((e) => setError(e.message))

  const addStreamer = () =>
    act(async () => {
      if (!handle.trim()) return
      await api.post('/watchlist', { handle: handle.trim(), auto_record: false })
      setHandle('')
    })

  const toggle = (s: any, field: 'auto_record' | 'auto_clip_on_end') =>
    act(() => api.put(`/streamers/${s.streamer_id}`, {
      platform: 'kick', handle: s.handle, display_name: s.display_name,
      is_watched: true, context_notes: '',
      auto_record: field === 'auto_record' ? !s.auto_record : s.auto_record,
      auto_clip_on_end: field === 'auto_clip_on_end' ? !s.auto_clip_on_end : s.auto_clip_on_end,
    }))

  const fmtBytes = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(0)} MB`)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">📡 {t('live.watchlist')}</h1>
      {error && (
        <p className="rounded bg-amber-500/20 p-2 text-sm text-amber-200">⊗ {error}
          <button className="ms-2 underline" onClick={() => setError('')}>{t('common.close')}</button>
        </p>
      )}

      <div className="flex gap-2">
        <input className="input w-80" value={handle} placeholder={t('live.add_placeholder')}
               onChange={(e) => setHandle(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && addStreamer()} />
        <button className="btn" onClick={addStreamer}>＋ {t('live.add_streamer')}</button>
        <button className="btn-secondary" onClick={() => act(() => api.post('/live/poll-now'))}>🔄</button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {status?.streamers?.map((s: any) => (
          <div key={s.streamer_id} className="card space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold">{s.display_name}</span>
              <StatusBadge status={s.live ? 'live' : 'offline'} />
            </div>
            {s.live && (
              <p className="truncate text-sm text-slate-400">{s.title} · 👀 {s.viewers} {t('live.viewers')}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {s.recording_id ? (
                <>
                  <button className="btn-secondary"
                          onClick={() => act(() => api.post(`/recordings/${s.recording_id}/stop`))}>
                    ⏹ {t('live.stop')}
                  </button>
                  <button className="btn"
                          onClick={() => act(() => api.post(`/recordings/${s.recording_id}/clip-last`, { seconds: 60 }))}>
                    ✂ {t('live.clip_last')}
                  </button>
                </>
              ) : (
                <button className="btn-amber"
                        onClick={() => act(() => api.post('/recordings/start', { streamer_id: s.streamer_id }))}>
                  ⏺ {t('live.record')}
                </button>
              )}
            </div>
            <div className="space-y-1 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={s.auto_record} onChange={() => toggle(s, 'auto_record')} />
                ⏺ {t('live.auto_record')}
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={s.auto_clip_on_end} onChange={() => toggle(s, 'auto_clip_on_end')} />
                ✨ {t('live.auto_clip')}
              </label>
            </div>
          </div>
        ))}
      </div>

      <section className="card">
        <h2 className="mb-3 font-bold">⏺ {t('dash.active_recordings')}</h2>
        {status?.active_recordings?.length ? (
          <table className="w-full text-sm">
            <tbody>
              {status.active_recordings.map((r: any) => (
                <tr key={r.recording_id} className="border-b border-slate-800">
                  <td className="py-2 font-semibold">{r.channel}</td>
                  <td><StatusBadge status="recording" /></td>
                  <td className="tabular-nums">{t('live.elapsed')}: {Math.floor(r.elapsed_sec / 60)}m</td>
                  <td className="tabular-nums">{t('live.size')}: {fmtBytes(r.size_bytes)}</td>
                  <td className="tabular-nums">{t('live.reconnects')}: {r.reconnect_count}</td>
                  <td>
                    <button className="btn-secondary"
                            onClick={() => act(() => api.post(`/recordings/${r.recording_id}/stop`))}>
                      ⏹ {t('live.stop')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-400">—</p>
        )}
      </section>
    </div>
  )
}
