import { useI18n } from '../i18n'

/**
 * Virality = number + filled bar + tier label + icon.
 * Never a red->green gradient (operator has protanomaly).
 */
const TIER_ICON: Record<string, string> = { High: '🔥', Medium: '➖', Low: '🧊' }

export default function ViralityScore({ score, tier }: { score?: number | null; tier?: string | null }) {
  const { t } = useI18n()
  if (score == null) return null
  const tierKey = tier || (score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low')
  return (
    <div className="flex items-center gap-2" title={`${score}/100`}>
      <span className="text-lg font-bold tabular-nums">{score}</span>
      <div className="h-2 w-24 overflow-hidden rounded bg-slate-700" role="meter"
           aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full bg-blue-400" style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-slate-300">
        <span aria-hidden>{TIER_ICON[tierKey] ?? '➖'}</span> {t(`tier.${tierKey}`)}
      </span>
    </div>
  )
}
