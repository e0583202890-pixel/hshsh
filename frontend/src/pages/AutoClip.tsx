import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, mediaUrl } from '../lib/api'
import { onWs } from '../lib/ws'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'
import ViralityScore from '../components/ViralityScore'

export default function AutoClip() {
  const { t } = useI18n()
  const [sources, setSources] = useState<any[]>([])
  const [sourceId, setSourceId] = useState<number | ''>('')
  const [url, setUrl] = useState('')
  const [n, setN] = useState(10)
  const [exclusions, setExclusions] = useState('')
  const [clips, setClips] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  const refresh = () => {
    api.get('/sources').then((s) => setSources(s.filter((x: any) => x.status === 'done'))).catch(() => {})
    if (sourceId) api.get(`/clips?source_id=${sourceId}`).then(setClips).catch(() => {})
    else api.get('/clips').then(setClips).catch(() => {})
  }

  useEffect(() => {
    refresh()
    return onWs((m) => { if (m.kind === 'job') refresh() })
  }, [sourceId])

  const run = async () => {
    setMsg('')
    try {
      const body: any = { n, exclusions: exclusions ? exclusions.split(',').map((s) => s.trim()) : [] }
      if (sourceId) body.source_id = sourceId
      else if (url) body.url = url
      else return
      const res = await api.post('/autoclip', body)
      setMsg(res.note || `Job #${res.job_id ?? res.download_job_id} started`)
    } catch (e: any) { setMsg(e.message) }
  }

  const sorted = [...clips].sort((a, b) => (b.virality_score ?? 0) - (a.virality_score ?? 0))

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">✨ {t('autoclip.title')}</h1>

      <div className="card grid gap-3 md:grid-cols-2">
        <div>
          <label className="label">{t('autoclip.source')}</label>
          <select className="input w-full" value={sourceId}
                  onChange={(e) => setSourceId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">—</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>#{s.id} {s.title?.slice(0, 60)}</option>
            ))}
          </select>
          <input className="input mt-2 w-full" placeholder={t('autoclip.paste_url')}
                 value={url} onChange={(e) => setUrl(e.target.value)} disabled={!!sourceId} />
        </div>
        <div className="space-y-2">
          <div>
            <label className="label">{t('autoclip.n_clips')}</label>
            <input className="input w-24" type="number" min={1} max={30} value={n}
                   onChange={(e) => setN(Number(e.target.value))} />
          </div>
          <div>
            <label className="label">{t('autoclip.exclusions')}</label>
            <input className="input w-full" value={exclusions}
                   onChange={(e) => setExclusions(e.target.value)} />
          </div>
          <button className="btn" onClick={run}>▶ {t('autoclip.run')}</button>
          {msg && <p className="text-sm text-amber-200">{msg}</p>}
        </div>
      </div>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-bold">🗂 {t('autoclip.review_grid')}</h2>
          <p className="text-xs text-slate-400">ℹ {t('autoclip.score_note')}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sorted.map((c) => (
            <div key={c.id} className="card space-y-2">
              {c.file_path && (
                <video className="w-full rounded bg-black" src={mediaUrl(c.file_path)} controls preload="metadata" />
              )}
              <div className="flex items-center justify-between">
                <ViralityScore score={c.virality_score} tier={c.virality_tier} />
                <StatusBadge status={c.status} />
              </div>
              <p className="font-semibold">{c.title || `Clip #${c.id}`}</p>
              {c.hook_text && <p className="text-sm text-blue-300">🪝 {c.hook_text}</p>}
              {c.virality_reason && <p className="text-xs text-slate-400">{c.virality_reason}</p>}
              {c.signals_json && JSON.parse(c.signals_json).length > 0 && (
                <p className="text-xs">
                  {t('autoclip.signals')}: {JSON.parse(c.signals_json).map((s: string) => (
                    <span key={s} className="me-1 rounded bg-slate-700 px-1">
                      {{ audio_hype: '🔊', chat_spike: '💬', scene_change: '🎬', face_reaction: '😲' }[s] ?? '•'} {s}
                    </span>
                  ))}
                </p>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                <button className="btn" onClick={() => api.post(`/clips/${c.id}/export`, { aspect_ratios: ['9:16'] })}>
                  ⬆ {t('autoclip.export')}
                </button>
                <Link to={`/editor/${c.id}`} className="btn-secondary">🎬 {t('autoclip.open_editor')}</Link>
                <button className="btn-secondary" onClick={() => api.post(`/clips/${c.id}/regenerate`).then(refresh)}>
                  🔄 {t('autoclip.regenerate')}
                </button>
                <button className="btn-secondary" onClick={() => api.del(`/clips/${c.id}`).then(refresh)}>
                  🗑 {t('autoclip.discard')}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
