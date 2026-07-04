import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../i18n'

export default function Streamers() {
  const { t } = useI18n()
  const [streamers, setStreamers] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  const refresh = () => api.get('/streamers').then(setStreamers).catch(() => {})
  useEffect(() => { refresh() }, [])

  const update = async (s: any, patch: Partial<any>) => {
    try {
      await api.put(`/streamers/${s.id}`, {
        platform: s.platform, handle: s.handle,
        display_name: s.display_name, is_watched: s.is_watched,
        context_notes: s.context_notes, auto_record: s.auto_record,
        auto_clip_on_end: s.auto_clip_on_end,
        default_vertical_mode: s.default_vertical_mode,
        default_brandkit_id: s.default_brandkit_id,
        ...patch,
      })
      setMsg('✔')
      refresh()
    } catch (e: any) { setMsg(`⊗ ${e.message}`) }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">🎮 {t('streamers.title')}</h1>
      {msg && <p className="text-sm text-blue-300">{msg}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {streamers.map((s) => (
          <div key={s.id} className="card space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-lg font-bold">{s.display_name || s.handle}</p>
                <p className="text-xs text-slate-400" dir="ltr">kick.com/{s.handle}</p>
              </div>
              <span className={`rounded px-2 py-0.5 text-xs ${s.facecam_rect_json ? 'bg-blue-500/20 text-blue-200' : 'bg-slate-700 text-slate-400'}`}>
                {s.facecam_rect_json ? `✔ ${t('streamers.layout_saved')}` : `📐 ${t('streamers.no_layout')}`}
              </span>
            </div>
            <div>
              <label className="label">{t('streamers.context_notes')}</label>
              <textarea className="input h-20 w-full" defaultValue={s.context_notes}
                        onBlur={(e) => e.target.value !== s.context_notes && update(s, { context_notes: e.target.value })} />
            </div>
            <div>
              <label className="label">{t('streamers.default_mode')}</label>
              <select className="input w-full" value={s.default_vertical_mode}
                      onChange={(e) => update(s, { default_vertical_mode: e.target.value })}>
                {['facecam_stack', 'blur_fill', 'auto_reframe', 'center_crop', 'letterbox'].map((m) => (
                  <option key={m} value={m}>{t(`editor.mode.${m}`)}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={s.auto_record}
                       onChange={() => update(s, { auto_record: !s.auto_record })} />
                ⏺ {t('live.auto_record')}
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={s.auto_clip_on_end}
                       onChange={() => update(s, { auto_clip_on_end: !s.auto_clip_on_end })} />
                ✨ {t('live.auto_clip')}
              </label>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
