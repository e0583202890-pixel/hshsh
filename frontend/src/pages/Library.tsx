import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, mediaUrl } from '../lib/api'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'
import ViralityScore from '../components/ViralityScore'

export default function Library() {
  const { t } = useI18n()
  const [tab, setTab] = useState<'sources' | 'recordings' | 'clips'>('clips')
  const [sources, setSources] = useState<any[]>([])
  const [recordings, setRecordings] = useState<any[]>([])
  const [clips, setClips] = useState<any[]>([])
  const [q, setQ] = useState('')

  const refresh = () => {
    api.get('/sources').then(setSources).catch(() => {})
    api.get('/recordings').then(setRecordings).catch(() => {})
    api.get('/clips').then(setClips).catch(() => {})
  }
  useEffect(() => { refresh() }, [])

  const del = async (kind: string, id: number) => {
    if (!confirm(t('library.delete_confirm'))) return
    await api.del(`/${kind}/${id}`)
    refresh()
  }

  const match = (s: string | null | undefined) => !q || (s || '').toLowerCase().includes(q.toLowerCase())

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">📚 {t('library.title')}</h1>
      <div className="flex flex-wrap items-center gap-2">
        {(['clips', 'sources', 'recordings'] as const).map((tb) => (
          <button key={tb}
                  className={tab === tb ? 'btn' : 'btn-secondary'}
                  onClick={() => setTab(tb)}>
            {t(`library.${tb}`)}
          </button>
        ))}
        <input className="input ms-auto w-64" placeholder={`🔍 ${t('library.search')}`}
               value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {tab === 'clips' && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {clips.filter((c) => match(c.title)).map((c) => (
            <div key={c.id} className="card space-y-2">
              {c.file_path && (
                <video className="w-full rounded bg-black" src={mediaUrl(c.file_path)} controls preload="metadata" />
              )}
              <div className="flex items-center justify-between">
                <ViralityScore score={c.virality_score} tier={c.virality_tier} />
                <StatusBadge status={c.status} />
              </div>
              <p className="truncate font-semibold">{c.title || `Clip #${c.id}`}</p>
              <p className="text-xs text-slate-400" dir="ltr">
                {c.duration_sec?.toFixed(0)}s {c.has_captions ? '· 📝 CC' : ''} {c.caption_lang ? `(${c.caption_lang})` : ''}
              </p>
              <div className="flex gap-2">
                <Link to={`/editor/${c.id}`} className="btn-secondary">🎬</Link>
                <button className="btn-secondary"
                        onClick={() => api.post(`/clips/${c.id}/export`, { aspect_ratios: ['9:16'] })}>⬆</button>
                <button className="btn-secondary" onClick={() => del('clips', c.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'sources' && (
        <div className="space-y-2">
          {sources.filter((s) => match(s.title)).map((s) => (
            <div key={s.id} className="card flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-semibold">#{s.id} {s.title}</p>
                <p className="text-xs text-slate-400" dir="ltr">
                  {s.platform} · {s.origin} · {s.duration_sec ? `${Math.floor(s.duration_sec / 60)}m` : '?'}
                  {s.width ? ` · ${s.width}x${s.height}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={s.status} />
                <button className="btn-secondary" onClick={() => del('sources', s.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'recordings' && (
        <div className="space-y-2">
          {recordings.map((r) => (
            <div key={r.id} className="card flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold">#{r.id} {r.file_path?.split(/[\\/]/).pop() || '—'}</p>
                <p className="text-xs text-slate-400" dir="ltr">
                  {r.duration_sec ? `${Math.floor(r.duration_sec / 60)}m` : ''} ·
                  segments: {r.segment_count} · reconnects: {r.reconnect_count}
                  {r.had_chat ? ' · 💬 chat' : ''}
                </p>
                {r.error && <p className="text-xs text-slate-300">⊗ {r.error}</p>}
              </div>
              <StatusBadge status={r.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
