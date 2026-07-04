import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { onWs } from '../lib/ws'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'

export default function Download() {
  const { t } = useI18n()
  const [urls, setUrls] = useState('')
  const [quality, setQuality] = useState('best')
  const [section, setSection] = useState('')
  const [sources, setSources] = useState<any[]>([])
  const [jobs, setJobs] = useState<Record<number, any>>({})
  const [m3u8Input, setM3u8Input] = useState<Record<number, string>>({})

  const refresh = () => api.get('/sources').then(setSources).catch(() => {})

  useEffect(() => {
    refresh()
    return onWs((m) => {
      if (m.kind === 'job' && m.type === 'download') {
        setJobs((j) => ({ ...j, [m.source_id]: m }))
        if (m.status === 'done' || m.status === 'failed' || m.status === 'needs_input') refresh()
      }
    })
  }, [])

  const start = async () => {
    const list = urls.split('\n').map((u) => u.trim()).filter(Boolean)
    if (!list.length) return
    await api.post('/sources/download', { urls: list, quality, section: section || null })
    setUrls('')
    refresh()
  }

  const submitM3u8 = async (sourceId: number) => {
    const u = m3u8Input[sourceId]?.trim()
    if (!u) return
    await api.post(`/sources/${sourceId}/manual-m3u8`, { m3u8_url: u })
    refresh()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">⬇ {t('download.title')}</h1>

      <div className="card space-y-3">
        <div>
          <label className="label">{t('download.urls')}</label>
          <textarea className="input h-24 w-full" value={urls} onChange={(e) => setUrls(e.target.value)} />
        </div>
        <div className="flex flex-wrap gap-3">
          <div>
            <label className="label">{t('download.quality')}</label>
            <select className="input" value={quality} onChange={(e) => setQuality(e.target.value)}>
              <option value="best">best</option>
              <option value="bestvideo[height<=1080]+bestaudio/best">1080p</option>
              <option value="bestvideo[height<=720]+bestaudio/best">720p</option>
            </select>
          </div>
          <div>
            <label className="label">{t('download.section')}</label>
            <input className="input" dir="ltr" placeholder="00:10:00-00:12:30" value={section}
                   onChange={(e) => setSection(e.target.value)} />
          </div>
          <button className="btn self-end" onClick={start}>⬇ {t('download.start')}</button>
        </div>
      </div>

      <div className="space-y-3">
        {sources.map((s) => {
          const job = jobs[s.id]
          return (
            <div key={s.id} className="card">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold" dir="ltr">{s.title || s.url}</p>
                  <p className="text-xs text-slate-400">{s.platform} · #{s.id}</p>
                </div>
                <StatusBadge status={s.status} />
              </div>
              {job && job.status === 'running' && (
                <div className="mt-2 h-2 overflow-hidden rounded bg-slate-700">
                  <div className="h-full bg-blue-400 transition-all" style={{ width: `${job.progress_pct}%` }} />
                </div>
              )}
              {job?.message && <p className="mt-1 text-xs text-slate-400">{job.message}</p>}
              {s.status === 'needs_input' && (
                <div className="mt-3 rounded bg-amber-500/10 p-3">
                  <p className="mb-2 text-sm text-amber-200">⏸ {s.error}</p>
                  <div className="flex gap-2">
                    <input className="input flex-1" dir="ltr" placeholder={t('download.m3u8_prompt')}
                           value={m3u8Input[s.id] || ''}
                           onChange={(e) => setM3u8Input((m) => ({ ...m, [s.id]: e.target.value }))} />
                    <button className="btn-amber" onClick={() => submitM3u8(s.id)}>
                      {t('download.m3u8_submit')}
                    </button>
                  </div>
                </div>
              )}
              {s.status === 'failed' && s.error && (
                <p className="mt-2 text-sm text-slate-300">⊗ {s.error}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
