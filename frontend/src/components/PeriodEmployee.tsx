import type { AgentRow } from '../types/bridge'
import { Icon } from './Icon'
import { compactTime, MetricTrend } from './MetricTrend'

export function PeriodEmployee({ winners, available }: { winners?: AgentRow[]; available?: boolean }) {
  return <div className="period-employees">{winners?.filter(row => row.isPeriodWinner).map(row => <article key={row.id}>
    <div className="employee-heading"><Icon name="crown" /><span className="agent-avatar">{row.abbreviation || row.label}</span><strong>{row.displayName || row.label}</strong></div>
    <dl><div><dt>Geschlossene Tickets</dt><dd>{row.Geschlossen ?? '–'}</dd></div><div><dt>Median Reaktionszeit</dt><dd>{row.medianResponseMinutes != null ? compactTime(row.medianResponseMinutes) : '–'}</dd></div><div><dt>Erstantworten</dt><dd>{row.Erstantworten ?? '–'}</dd></div></dl>
    {row.meanResponseMinutes != null && <details className="mean-detail"><summary>Durchschnitt anzeigen</summary><p>Durchschnitt: {compactTime(row.meanResponseMinutes)}</p></details>}
    {row.responseComparison && <MetricTrend metric={{ label: 'Reaktionszeit', note: '', tone: '', ...row.responseComparison, value: '' }} />}
  </article>)}{!winners?.some(row => row.isPeriodWinner) && <p className="chart-note">{available ? 'Keine menschlichen Abschlüsse im Zeitraum.' : 'Historie noch nicht verfügbar.'}</p>}<p className="ranking-explanation">Informelle Anerkennung der Abschlüsse im Zeitraum. Keine Bewertung der Arbeitsqualität. Bei Gleichstand werden alle Gewinner angezeigt.</p></div>
}
