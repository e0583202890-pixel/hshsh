import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, mediaUrl } from '../lib/api'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'
import RectDraw, { Rect } from '../components/RectDraw'

const TABS = ['trim', 'vertical', 'captions', 'branding', 'audio', 'effects', 'export'] as const
type Tab = typeof TABS[number]

export default function Editor() {
  const { t } = useI18n()
  const { clipId } = useParams()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [clip, setClip] = useState<any>(null)
  const [source, setSource] = useState<any>(null)
  const [tab, setTab] = useState<Tab>('trim')
  const [inSec, setInSec] = useState(0)
  const [outSec, setOutSec] = useState(0)
  const [mode, setMode] = useState('facecam_stack')
  const [facecam, setFacecam] = useState<Rect | null>(null)
  const [gameplay, setGameplay] = useState<Rect | null>(null)
  const [drawTarget, setDrawTarget] = useState<'facecam' | 'gameplay'>('facecam')
  const [transcript, setTranscript] = useState<any>(null)
  const [hook, setHook] = useState('')
  const [presets, setPresets] = useState<any[]>([])
  const [brandkits, setBrandkits] = useState<any[]>([])
  const [aspects, setAspects] = useState<string[]>(['9:16'])
  const [audioOpts, setAudioOpts] = useState({ loudnorm: true, remove_silence: false, ducking: true })
  const [fx, setFx] = useState({ punch_in: false, intensity: 0.15 })
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/presets').then(setPresets).catch(() => {})
    api.get('/brandkits').then(setBrandkits).catch(() => {})
    if (clipId) {
      api.get(`/clips/${clipId}`).then((c) => {
        setClip(c)
        setInSec(c.start_sec); setOutSec(c.end_sec)
        setMode(c.vertical_mode); setHook(c.hook_text || '')
        if (c.transcript_json) setTranscript(JSON.parse(c.transcript_json))
        api.get(`/sources/${c.source_id}`).then(setSource).catch(() => {})
      }).catch((e) => setMsg(e.message))
    }
  }, [clipId])

  const videoSrc = useMemo(() => mediaUrl(source?.file_path), [source])
  const vw = source?.width || 1920
  const vh = source?.height || 1080

  const save = async (fn: () => Promise<any>, okMsg = '✔') => {
    try { await fn(); setMsg(okMsg) } catch (e: any) { setMsg(`⊗ ${e.message}`) }
  }

  const saveTrim = () => save(async () => {
    // Trim is stored on the clip via create/update; here we PATCH via vertical params refresh
    if (!clip) return
    await api.post(`/clips/${clip.id}/vertical`, { mode, params: verticalParams() })
  })

  const verticalParams = () => {
    const params: any = { audio: audioOpts, effects: fx }
    if (mode === 'facecam_stack' && facecam) {
      params.facecam_rect = facecam
      params.gameplay_rect = gameplay || { x: 0, y: 0, w: vw, h: vh }
    }
    return params
  }

  const saveLayoutToStreamer = () => save(async () => {
    if (!source?.streamer_id || !facecam) return
    await api.put(`/streamers/${source.streamer_id}/layout`, {
      facecam_rect: facecam, gameplay_rect: gameplay || { x: 0, y: 0, w: vw, h: vh },
    })
  }, `✔ ${t('streamers.layout_saved')}`)

  const suggestFacecam = () => save(async () => {
    if (!source?.streamer_id) return
    const res = await api.post(`/streamers/${source.streamer_id}/suggest-facecam?source_id=${source.id}`)
    if (res.rect) setFacecam(res.rect)
  })

  const genCaptions = () => save(async () => {
    const res = await api.post(`/clips/${clip.id}/captions`, { burn: true })
    setTranscript(res.transcript)
  })

  const saveTranscript = () => save(() =>
    api.patch(`/clips/${clip.id}/transcript`, { segments: transcript.segments }))

  const exportNow = () => save(async () => {
    await api.post(`/clips/${clip.id}/vertical`, { mode, params: verticalParams() })
    await api.post(`/clips/${clip.id}/brand`, { hook_text: hook })
    await api.post(`/clips/${clip.id}/export`, { aspect_ratios: aspects })
  }, '✔ ' + t('editor.add_to_queue'))

  const preset = presets.find((p) => p.id === clip?.preset_id) || presets.find((p) => p.is_default)
  const overMax = preset && outSec - inSec > preset.max_duration_sec

  if (!clip) {
    return <p className="text-slate-400">{msg || t('common.loading')} — {t('dash.edit_clip')}: /library</p>
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold">🎬 {clip.title || `Clip #${clip.id}`}</h1>
          <StatusBadge status={clip.status} />
        </div>
        <div className="relative">
          <video ref={videoRef} className="w-full rounded bg-black" src={videoSrc} controls />
          {tab === 'vertical' && mode === 'facecam_stack' && (
            <RectDraw
              videoWidth={vw} videoHeight={vh}
              rect={drawTarget === 'facecam' ? facecam : gameplay}
              color={drawTarget === 'facecam' ? '#22d3ee' : '#f59e0b'}
              label={drawTarget === 'facecam' ? 'facecam' : 'gameplay'}
              onChange={(r) => (drawTarget === 'facecam' ? setFacecam(r) : setGameplay(r))}
            />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button className="btn-secondary" onClick={() => setInSec(videoRef.current?.currentTime || 0)}>
            ⟦ {t('editor.mark_in')}
          </button>
          <button className="btn-secondary" onClick={() => setOutSec(videoRef.current?.currentTime || 0)}>
            {t('editor.mark_out')} ⟧
          </button>
          <span className="tabular-nums text-slate-400" dir="ltr">
            {inSec.toFixed(1)}s → {outSec.toFixed(1)}s ({(outSec - inSec).toFixed(1)}s)
          </span>
          {overMax && (
            <span className="rounded bg-amber-500/20 px-2 py-0.5 text-amber-200">
              🕐 {t('editor.duration_warning')} ({preset.max_duration_sec}s)
            </span>
          )}
        </div>
        {msg && <p className="text-sm text-blue-300">{msg}</p>}
      </div>

      <aside className="card h-fit space-y-4">
        <nav className="flex flex-wrap gap-1">
          {TABS.map((tb) => (
            <button key={tb}
                    className={`rounded px-2 py-1 text-xs font-semibold ${tab === tb ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}`}
                    onClick={() => setTab(tb)}>
              {t(`editor.${tb}`)}
            </button>
          ))}
        </nav>

        {tab === 'trim' && (
          <div className="space-y-2">
            <button className="btn w-full justify-center" onClick={saveTrim}>💾 {t('common.save')}</button>
          </div>
        )}

        {tab === 'vertical' && (
          <div className="space-y-3">
            <select className="input w-full" value={mode} onChange={(e) => setMode(e.target.value)}>
              {['facecam_stack', 'blur_fill', 'auto_reframe', 'center_crop', 'letterbox'].map((m) => (
                <option key={m} value={m}>{t(`editor.mode.${m}`)}</option>
              ))}
            </select>
            {mode === 'facecam_stack' && (
              <>
                <div className="flex gap-2">
                  <button className={drawTarget === 'facecam' ? 'btn' : 'btn-secondary'}
                          onClick={() => setDrawTarget('facecam')}>📷 {t('editor.draw_facecam')}</button>
                  <button className={drawTarget === 'gameplay' ? 'btn' : 'btn-secondary'}
                          onClick={() => setDrawTarget('gameplay')}>🎮</button>
                </div>
                <button className="btn-secondary w-full justify-center" onClick={suggestFacecam}>
                  ✨ {t('editor.suggest_facecam')}
                </button>
                <button className="btn w-full justify-center" onClick={saveLayoutToStreamer}
                        disabled={!facecam || !source?.streamer_id}>
                  💾 {t('editor.save_layout')}
                </button>
              </>
            )}
          </div>
        )}

        {tab === 'captions' && (
          <div className="space-y-3">
            <button className="btn w-full justify-center" onClick={genCaptions}>
              📝 {t('editor.generate_captions')}
            </button>
            {transcript?.segments && (
              <>
                <p className="text-xs text-slate-400">{t('editor.transcript_edit')}</p>
                <div className="max-h-72 space-y-1 overflow-y-auto">
                  {transcript.segments.map((seg: any, i: number) => (
                    <div key={i} className="flex items-center gap-1">
                      <span className="w-14 shrink-0 text-xs tabular-nums text-slate-500" dir="ltr">
                        {seg.start.toFixed(1)}s
                      </span>
                      <input className="input w-full text-xs" value={seg.text}
                             onChange={(e) => {
                               const next = { ...transcript }
                               next.segments[i] = { ...seg, text: e.target.value }
                               setTranscript(next)
                             }} />
                    </div>
                  ))}
                </div>
                <button className="btn-secondary w-full justify-center" onClick={saveTranscript}>
                  💾 {t('common.save')}
                </button>
              </>
            )}
          </div>
        )}

        {tab === 'branding' && (
          <div className="space-y-3">
            <div>
              <label className="label">{t('editor.hook_text')}</label>
              <input className="input w-full" value={hook} onChange={(e) => setHook(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('brand.title')}</label>
              <select className="input w-full" value={clip.brandkit_id || ''}
                      onChange={(e) => api.post(`/clips/${clip.id}/brand`, { brandkit_id: Number(e.target.value) })}>
                {brandkits.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            {clip.hook_variants_json && JSON.parse(clip.hook_variants_json).length > 0 && (
              <div className="space-y-1">
                <label className="label">A/B</label>
                {JSON.parse(clip.hook_variants_json).map((v: string, i: number) => (
                  <button key={i} className="btn-secondary w-full justify-start text-xs"
                          onClick={() => setHook(v)}>🪝 {v}</button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'audio' && (
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={audioOpts.loudnorm}
                     onChange={(e) => setAudioOpts({ ...audioOpts, loudnorm: e.target.checked })} />
              🔊 {t('editor.loudnorm')}
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={audioOpts.ducking}
                     onChange={(e) => setAudioOpts({ ...audioOpts, ducking: e.target.checked })} />
              🎵 {t('editor.music')}
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={audioOpts.remove_silence}
                     onChange={(e) => setAudioOpts({ ...audioOpts, remove_silence: e.target.checked })} />
              ✂ {t('editor.remove_silence')}
            </label>
            <button className="btn w-full justify-center"
                    onClick={() => save(() => api.post(`/clips/${clip.id}/audio`, audioOpts))}>
              💾 {t('common.save')}
            </button>
          </div>
        )}

        {tab === 'effects' && (
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={fx.punch_in}
                     onChange={(e) => setFx({ ...fx, punch_in: e.target.checked })} />
              🔍 {t('editor.punch_in')}
            </label>
            <input type="range" min={0.05} max={0.3} step={0.05} value={fx.intensity}
                   onChange={(e) => setFx({ ...fx, intensity: Number(e.target.value) })}
                   className="w-full" disabled={!fx.punch_in} />
            <button className="btn w-full justify-center"
                    onClick={() => save(() => api.post(`/clips/${clip.id}/effects`, fx))}>
              💾 {t('common.save')}
            </button>
          </div>
        )}

        {tab === 'export' && (
          <div className="space-y-3 text-sm">
            <div className="space-y-1">
              {['9:16', '1:1', '16:9'].map((a) => (
                <label key={a} className="flex items-center gap-2">
                  <input type="checkbox" checked={aspects.includes(a)}
                         onChange={(e) => setAspects(e.target.checked
                           ? [...aspects, a] : aspects.filter((x) => x !== a))} />
                  <span dir="ltr">{a}</span>
                </label>
              ))}
            </div>
            <button className="btn w-full justify-center" onClick={exportNow}>
              🚀 {t('editor.export_now')}
            </button>
          </div>
        )}
      </aside>
    </div>
  )
}
