import type { Comparison, Metric } from '../types/bridge'

export function compactTime(minutes: number) {
  const rounded = Math.round(Math.abs(minutes))
  const hours = Math.floor(rounded / 60), remainder = rounded % 60
  return hours ? `${hours} h${remainder ? ` ${remainder} min` : ''}` : `${remainder} min`
}
export function MetricTrend({ metric }: { metric: Metric }) {
  if (!metric.deltaAvailable || metric.delta == null || !Number.isFinite(metric.delta)) return null
  const unit = metric.unit || (metric.value.endsWith('%') ? 'percent' : 'count')
  const amount = unit === 'minutes' ? compactTime(metric.delta) : `${Math.abs(metric.delta).toLocaleString('de-CH', { maximumFractionDigits: 1 })} ${unit === 'percent' ? '%' : 'Tickets'}`
  const sign = metric.delta > 0 ? '+' : metric.delta < 0 ? '−' : '±'
  const arrow = metric.delta > 0 ? '▲' : metric.delta < 0 ? '▼' : '→'
  const meaning = metric.trend === 'improvement' ? 'Verbesserung' : metric.trend === 'deterioration' ? 'Verschlechterung' : 'Unverändert'
  return <span key={`${metric.delta}:${metric.snapshotAt || ''}`} className={`metric-trend ${metric.trend || 'neutral'}`} title={`Vergleich: ${meaning}`} aria-label={`${meaning}: ${sign}${amount}`}><span aria-hidden="true">{arrow}</span> {sign}{amount}</span>
}
export function meanDetail(metric: Metric, comparisons?: Record<string, Comparison>) {
  const mean = comparisons?.[metric.label.replace('Median', 'Durchschnitt')]?.value
  return metric.label.startsWith('Median ') && mean != null && Number.isFinite(mean) ? `Durchschnitt: ${compactTime(mean)}` : undefined
}
