import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../i18n'

export default function Settings() {
  const { t, lang, setLang } = useI18n()
  const [settings, setSettings] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [form, setForm] = useState<any>({})
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/settings').then((s) => { setSettings(s); setForm(s) }).catch(() => {})
    api.get('/health').then(setHealth).catch(() => {})
  }, [])

  const save = async () => {
    try {
      await api.put('/settings', {
        live_poll_interval_sec: form.live_poll_interval_sec,
        disk_min_free_gb: form.disk_min_free_gb,
        whisper_model: form.whisper_model,
        anthropic_model: form.anthropic_model,
        openrouter_model: form.openrouter_model,
        auto_purge_sources: form.auto_purge_sources,
        ui_language: lang,
      })
      setMsg('✔')
    } catch (e: any) { setMsg(`⊗ ${e.message}`) }
  }

  if (!settings) return <p className="text-slate-400">{t('common.loading')}</p>

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-bold">⚙ {t('settings.title')}</h1>

      <div className="card space-y-3">
        <h2 className="font-bold">🧰 {t('settings.paths')}</h2>
        <div className="flex flex-wrap gap-2 text-xs">
          {health && Object.entries(health.checks).map(([name, c]: any) => (
            <span key={name}
                  className={`inline-flex items-center gap-1 rounded px-2 py-1 ${c.ok ? 'bg-blue-500/10 text-blue-200' : 'bg-amber-500/20 text-amber-200'}`}>
              <span aria-hidden>{c.ok ? '✔' : '⊗'}</span>
              {name}: {c.ok ? t('settings.detected') : t('settings.not_found')}
              {!c.ok && c.hint && <span className="text-slate-400"> — {c.hint}</span>}
            </span>
          ))}
        </div>
      </div>

      <div className="card grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">{t('settings.whisper_model')}</label>
          <select className="input w-full" value={form.whisper_model || 'small'}
                  onChange={(e) => setForm({ ...form, whisper_model: e.target.value })}>
            {['tiny', 'small', 'medium', 'large-v3'].map((m) => <option key={m}>{m}</option>)}
          </select>
          <p className="mt-1 text-xs text-slate-400">large-v3 = best Hebrew, heavy GPU</p>
        </div>
        <div>
          <label className="label">
            🤖 LLM {settings.llm_provider !== 'none' ? `(${settings.llm_provider})` : ''}
          </label>
          {settings.openrouter_key_set ? (
            <input className="input w-full" dir="ltr" value={form.openrouter_model || ''}
                   placeholder="deepseek/deepseek-chat"
                   onChange={(e) => setForm({ ...form, openrouter_model: e.target.value })} />
          ) : (
            <input className="input w-full" dir="ltr" value={form.anthropic_model || ''}
                   onChange={(e) => setForm({ ...form, anthropic_model: e.target.value })} />
          )}
          <p className="mt-1 text-xs text-slate-400">
            {settings.llm_provider === 'openrouter'
              ? `✔ OpenRouter · ${settings.llm_model}`
              : settings.llm_provider === 'anthropic'
              ? `✔ Anthropic · ${settings.llm_model}`
              : '⊗ .env OPENROUTER_API_KEY or ANTHROPIC_API_KEY'}
          </p>
          {settings.openrouter_key_set && (
            <div className="mt-1 flex flex-wrap gap-1">
              {['deepseek/deepseek-chat', 'qwen/qwen-2.5-72b-instruct', 'z-ai/glm-4.5-air',
                'anthropic/claude-3.5-sonnet'].map((mdl) => (
                <button key={mdl} type="button"
                        className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-slate-700"
                        dir="ltr" onClick={() => setForm({ ...form, openrouter_model: mdl })}>
                  {mdl.split('/')[1]}
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          <label className="label">{t('settings.poll_interval')}</label>
          <input className="input w-full" type="number" min={30} value={form.live_poll_interval_sec || 300}
                 onChange={(e) => setForm({ ...form, live_poll_interval_sec: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">{t('settings.disk_min')}</label>
          <input className="input w-full" type="number" min={1} value={form.disk_min_free_gb || 5}
                 onChange={(e) => setForm({ ...form, disk_min_free_gb: Number(e.target.value) })} />
        </div>
        <div>
          <label className="label">{t('settings.language')}</label>
          <select className="input w-full" value={lang} onChange={(e) => setLang(e.target.value as any)}>
            <option value="he">עברית</option>
            <option value="en">English</option>
          </select>
        </div>
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input type="checkbox" checked={!!form.auto_purge_sources}
                 onChange={(e) => setForm({ ...form, auto_purge_sources: e.target.checked })} />
          🧹 Auto-purge raw sources after clipping
        </label>
      </div>

      <button className="btn" onClick={save}>💾 {t('settings.save')}</button>
      {msg && <span className="ms-3 text-blue-300">{msg}</span>}
    </div>
  )
}
