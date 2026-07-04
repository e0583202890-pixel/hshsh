import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../i18n'

export default function BrandKits() {
  const { t } = useI18n()
  const [kits, setKits] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  const refresh = () => api.get('/brandkits').then(setKits).catch(() => {})
  useEffect(() => { refresh() }, [])

  const update = async (kit: any, patch: any) => {
    try {
      await api.put(`/brandkits/${kit.id}`, { ...kit, ...patch })
      setMsg('✔')
      refresh()
    } catch (e: any) { setMsg(`⊗ ${e.message}`) }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🎨 {t('brand.title')}</h1>
      {msg && <p className="text-sm text-blue-300">{msg}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {kits.map((k) => (
          <div key={k.id} className="card space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-lg font-bold">{k.name}</p>
              {k.is_default && (
                <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs text-blue-200">
                  ★ {t('brand.default')}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label">{t('brand.handle')}</label>
                <input className="input w-full" dir="ltr" defaultValue={k.handle_watermark_text}
                       onBlur={(e) => e.target.value !== k.handle_watermark_text &&
                         update(k, { handle_watermark_text: e.target.value })} />
              </div>
              <div>
                <label className="label">{t('brand.font')}</label>
                <input className="input w-full" dir="ltr" defaultValue={k.font}
                       onBlur={(e) => e.target.value !== k.font && update(k, { font: e.target.value })} />
              </div>
              <div>
                <label className="label">Primary</label>
                <input className="input w-full" type="color" defaultValue={k.primary_color}
                       onBlur={(e) => update(k, { primary_color: e.target.value })} />
              </div>
              <div>
                <label className="label">Accent</label>
                <input className="input w-full" type="color" defaultValue={k.accent_color}
                       onBlur={(e) => update(k, { accent_color: e.target.value })} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
