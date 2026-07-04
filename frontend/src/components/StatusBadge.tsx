import { useI18n } from '../i18n'

/**
 * COLOR ACCESSIBILITY: every status = icon + text label, never hue alone.
 * Palette: blue / amber / slate / gray. "Recording"/"live" accents are always
 * paired with an icon and a word.
 */
const ICONS: Record<string, string> = {
  queued: '🕐',
  recording: '⏺',
  remuxing: '🔄',
  running: '⏳',
  live: '📡',
  offline: '💤',
  done: '✔',
  failed: '⊗',
  needs_input: '⏸',
  cancelled: '∅',
  building: '🛠',
  draft: '📝',
  downloading: '⬇',
}

const STYLES: Record<string, string> = {
  queued: 'bg-slate-700 text-slate-200',
  recording: 'bg-amber-500/20 text-amber-300 border border-amber-400',
  remuxing: 'bg-blue-500/20 text-blue-300',
  running: 'bg-blue-500/20 text-blue-300',
  live: 'bg-amber-500/20 text-amber-300 border border-amber-400',
  offline: 'bg-slate-800 text-slate-400',
  done: 'bg-blue-500/10 text-blue-200 border border-blue-500/40',
  failed: 'bg-slate-600 text-slate-100 border border-slate-400',
  needs_input: 'bg-amber-500/20 text-amber-200 border border-amber-500/50',
  cancelled: 'bg-slate-800 text-slate-400',
  building: 'bg-blue-500/20 text-blue-300',
  draft: 'bg-slate-700 text-slate-300',
  downloading: 'bg-blue-500/20 text-blue-300',
}

export default function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n()
  const key = status?.toLowerCase() || 'queued'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold ${STYLES[key] ?? STYLES.queued}`}
      role="status"
    >
      <span aria-hidden>{ICONS[key] ?? '•'}</span>
      <span>{t(`status.${key}`)}</span>
    </span>
  )
}
