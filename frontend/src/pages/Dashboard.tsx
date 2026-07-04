import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { onWs } from '../lib/ws'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'
import ViralityScore from '../components/ViralityScore'

export default function Dashboard() {
  const { t } = useI18n()
  const [health, setHealth] = useState<any>(null)
  const [liveStatus, setLiveStatus] = useState<any>(null)
  const [clips, setClips] = useState<any[]>([])
  const [storage, setStorage] = useState<any>(null)

  const refresh = () => {
    api.get('/health').then(setHealth).catch(() => {})
    api.get('/live/status').then(setLiveStatus).catch(() => {})
    api.get('/clips').then((c) => setClips(c.slice(0, 8))).catch(() => {})
    api.get('/storage').then(setStorage).catch(() => {})
  }

  useEffect(() => {
    refresh()
    return onWs(() => refresh())
  }, [])

  const fmtBytes = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(0)} MB`)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <Link to="/live" className="btn-amber text-base">⏺ {t('dash.record_live')}</Link>
        <Link to="/autoclip" className="btn text-base">✨ {t('dash.autoclip_vod')}</Link>
        <Link to="/library" className="btn-secondary text-base">🎬 {t('dash.edit_clip')}</Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-3 font-bold">📡 {t('dash.who_is_live')}</h2>
          {liveStatus?.streamers?.length ? (
            <ul className="space-y-2">
              {liveStatus.streamers.map((s: any) => (
                <li key={s.streamer_id} className="flex items-center justify-between">
                  <span className="font-semibold">{s.display_name}</span>
                  <StatusBadge status={s.live ? 'live' : 'offline'} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">{t('live.no_streamers')}</p>
          )}
        </section>

        <section className="card">
          <h2 className="mb-3 font-bold">⏺ {t('dash.active_recordings')}</h2>
          {liveStatus?.active_recordings?.length ? (
            <ul className="space-y-2 text-sm">
              {liveStatus.active_recordings.map((r: any) => (
                <li key={r.recording_id} className="flex items-center justify-between">
                  <span>{r.channel}</span>
                  <span className="flex items-center gap-2">
                    <StatusBadge status="recording" />
                    <span className="tabular-nums text-slate-400">
                      {Math.floor(r.elapsed_sec / 60)}m · {fmtBytes(r.size_bytes)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">—</p>
          )}
        </section>

        <section className="card">
          <h2 className="mb-3 font-bold">🎞 {t('dash.recent_clips')}</h2>
          <ul className="space-y-2">
            {clips.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2">
                <Link to={`/editor/${c.id}`} className="truncate text-sm hover:text-blue-300">
                  {c.title || `Clip #${c.id}`}
                </Link>
                <span className="flex items-center gap-2">
                  <ViralityScore score={c.virality_score} tier={c.virality_tier} />
                  <StatusBadge status={c.status} />
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="mb-3 font-bold">💾 {t('dash.storage')}</h2>
          {storage && (
            <div className="space-y-1 text-sm">
              <p>📀 {t('dash.free_space')}: <b>{storage.free_gb} GB</b></p>
              {Object.entries(storage.dirs).map(([k, v]: any) => (
                <p key={k} className="text-slate-400">📁 {k}: {fmtBytes(v)}</p>
              ))}
            </div>
          )}
          <h2 className="mb-2 mt-4 font-bold">🩺 {t('dash.health')}</h2>
          {health && (
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(health.checks).map(([name, c]: any) => (
                <span key={name}
                      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 ${c.ok ? 'bg-blue-500/10 text-blue-200' : 'bg-amber-500/20 text-amber-200'}`}
                      title={c.hint}>
                  <span aria-hidden>{c.ok ? '✔' : '⊗'}</span>{name}
                </span>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
