import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../i18n'

export default function Publish() {
  const { t } = useI18n()
  const [clips, setClips] = useState<any[]>([])
  const [clipId, setClipId] = useState<number | ''>('')
  const [platform, setPlatform] = useState('youtube')
  const [meta, setMeta] = useState<any>(null)
  const [preflight, setPreflight] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/clips').then((c) => setClips(c.filter((x: any) => x.status === 'done'))).catch(() => {})
  }, [])

  const generate = async () => {
    if (!clipId) return
    setBusy(true); setMsg('')
    try {
      const [m, p] = await Promise.all([
        api.post('/publish/metadata', { clip_id: clipId, platform }),
        api.post(`/clips/${clipId}/preflight`),
      ])
      setMeta(m); setPreflight(p)
    } catch (e: any) { setMsg(`⊗ ${e.message}`) }
    setBusy(false)
  }

  const copy = (text: string) => navigator.clipboard.writeText(text)

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🚀 {t('publish.title')}</h1>
      <div className="card flex flex-wrap items-end gap-3">
        <div>
          <label className="label">{t('library.clips')}</label>
          <select className="input w-72" value={clipId}
                  onChange={(e) => setClipId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">—</option>
            {clips.map((c) => <option key={c.id} value={c.id}>#{c.id} {c.title?.slice(0, 50)}</option>)}
          </select>
        </div>
        <div>
          <label className="label">{t('publish.platform')}</label>
          <select className="input" value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="youtube">YouTube Shorts</option>
            <option value="tiktok">TikTok</option>
            <option value="reels">Instagram Reels</option>
          </select>
        </div>
        <button className="btn" onClick={generate} disabled={busy || !clipId}>
          {busy ? '⏳' : '✨'} {t('publish.generate')}
        </button>
      </div>
      {msg && <p className="text-sm text-amber-200">{msg}</p>}

      {preflight && (
        <div className="card">
          <h2 className="mb-2 font-bold">🧪 {t('publish.preflight')}</h2>
          <ul className="space-y-1 text-sm">
            {preflight.checks.map((c: any) => (
              <li key={c.name} className="flex items-center gap-2">
                <span aria-hidden>{c.ok ? '✔' : '⊗'}</span>
                <span className={c.ok ? 'text-blue-200' : 'text-amber-200'}>{c.name}: {c.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {meta && (
        <div className="card space-y-3">
          {(['title_he', 'description_he'] as const).map((field) => (
            <div key={field}>
              <div className="flex items-center justify-between">
                <label className="label">{field}</label>
                <button className="btn-secondary text-xs" onClick={() => copy(meta[field])}>
                  📋 {t('publish.copy')}
                </button>
              </div>
              <textarea className="input w-full" rows={field === 'description_he' ? 4 : 2}
                        defaultValue={meta[field]} />
            </div>
          ))}
          <div>
            <div className="flex items-center justify-between">
              <label className="label">hashtags</label>
              <button className="btn-secondary text-xs"
                      onClick={() => copy((meta.hashtags || []).join(' '))}>
                📋 {t('publish.copy')}
              </button>
            </div>
            <p className="text-sm text-blue-300">{(meta.hashtags || []).join(' ')}</p>
          </div>
        </div>
      )}
    </div>
  )
}
