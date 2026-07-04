import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { onWs } from '../lib/ws'
import { useI18n } from '../i18n'
import StatusBadge from '../components/StatusBadge'

export default function Queue() {
  const { t } = useI18n()
  const [jobs, setJobs] = useState<any[]>([])

  const refresh = () => api.get('/jobs').then(setJobs).catch(() => {})
  useEffect(() => {
    refresh()
    return onWs((m) => { if (m.kind === 'job') refresh() })
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">🗂 {t('queue.title')}</h1>
      {!jobs.length && <p className="text-slate-400">{t('queue.no_jobs')}</p>}
      <div className="space-y-2">
        {jobs.map((j) => (
          <div key={j.id} className="card">
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="font-semibold">#{j.id} · {j.type}</span>
                {j.message && <span className="ms-2 text-sm text-slate-400">{j.message}</span>}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={j.status} />
                {(j.status === 'queued' || j.status === 'running') && (
                  <button className="btn-secondary" onClick={() => api.post(`/jobs/${j.id}/cancel`).then(refresh)}>
                    ∅ {t('queue.cancel')}
                  </button>
                )}
                {(j.status === 'failed' || j.status === 'cancelled') && (
                  <button className="btn-secondary" onClick={() => api.post(`/jobs/${j.id}/retry`).then(refresh)}>
                    🔄 {t('queue.retry')}
                  </button>
                )}
              </div>
            </div>
            {j.status === 'running' && (
              <div className="mt-2 h-2 overflow-hidden rounded bg-slate-700">
                <div className="h-full bg-blue-400 transition-all" style={{ width: `${j.progress_pct}%` }} />
              </div>
            )}
            {j.error && <p className="mt-2 text-sm text-slate-300">⊗ {j.error}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
