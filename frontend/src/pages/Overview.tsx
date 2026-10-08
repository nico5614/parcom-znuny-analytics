import { useCallback } from 'react'
import type { DesktopApi } from '../types/bridge'
import { useResource } from '../hooks/useResource'
import { Card, MetricCard, Skeleton, Empty } from '../components/Card'
import { DataTable } from '../components/DataTable'
import { Chart } from '../charts/Chart'

export function Overview({ api, revision, theme, onTicket }: { api: DesktopApi; revision: number; theme: string; onTicket: (id: string) => void }) {
  const load = useCallback(() => api.getOverview(), [api])
  const { value: data, loading, error } = useResource(api, 'overview', load, revision)
  if (!data) return loading ? <Skeleton /> : <Empty message={error || undefined} />
  return <div className="overview-grid">
    <div className="kpi-row">{data.metrics.map(metric => <MetricCard key={metric.label} metric={metric} />)}</div>
    <Card title="Ticketentwicklung" className="volume-card" aside={<span className="metadata">Ausgewählter Zeitraum</span>}><Chart dto={data.volume} height={245} theme={theme} /></Card>
    <Card title="Servicequalität" className="service-card"><div className="service-metrics">{data.services.map(metric => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.note}</small></div>)}</div></Card>
    <div className="operational-row">{data.operational.map(metric => <MetricCard key={metric.label} metric={metric} />)}</div>
    <Card title="Agentenverteilung" className="distribution-card" aside={<span className="metadata">Aktueller Besitz</span>}><Chart dto={data.agentChart} height={190} theme={theme} /></Card>
    <Card title="Handlungsbedarf" className="action-card" aside={<span className="count-badge">{data.action.total} überfällig</span>}><DataTable dto={data.action} onTicket={onTicket} /><p className="metadata action-note">{data.waitingNote}</p></Card>
    <details className="score-details"><summary>Performance Score · Berechnung und Datengrundlage <span>{data.score.status}</span></summary><div className="score-content"><p>{data.score.issue}</p><p>Trendindex, keine SLA-Erfüllung. Fünf Bereiche zählen je 20 %. Bei aktuell ≤ vorher gilt 100 %, sonst 100 × vorher / aktuell. Verbesserungen sind bei 100 % gedeckelt. Erforderlich sind vollständige Vergleichsmonate und tatsächlich erhobene gemeinsame Snapshot-Tage.</p><div className="score-areas">{data.score.areas.map(area => <div key={area.label}><span>{area.label}</span><strong>{area.value.toLocaleString('de-CH', { maximumFractionDigits: 1 })} %</strong></div>)}</div>{data.score.breakdown.length > 0 && <table><thead><tr><th>Teilkennzahl</th><th>Vorher</th><th>Aktuell</th><th>Trendindex</th></tr></thead><tbody>{data.score.breakdown.map(row => <tr key={row.label}><td>{row.label}</td><td>{row.before}</td><td>{row.after}</td><td>{row.score}</td></tr>)}</tbody></table>}<Chart dto={data.score.history} height={180} theme={theme} /></div></details>
  </div>
}
