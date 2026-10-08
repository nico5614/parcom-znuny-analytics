import { useCallback, useState } from 'react'
import type { DesktopApi } from '../types/bridge'
import { useResource } from '../hooks/useResource'
import { Card, Empty, MetricCard, Skeleton } from '../components/Card'
import { Chart } from '../charts/Chart'
import { DataTable } from '../components/DataTable'

export const analyses = ['Neue Tickets', 'Geschlossene Tickets', 'Offene Tickets', 'Eskalationen', 'Reaktionszeit', 'Lösungszeit', 'Wartende Tickets']
export function Analyses({ api, revision, theme, onTicket }: { api: DesktopApi; revision: number; theme: string; onTicket: (id: string) => void }) {
  const [kpi, setKpi] = useState(1)
  const [type, setType] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const load = useCallback(() => api.getAnalysis(kpi, type, page), [api, kpi, type, page])
  const { value: data, loading, error } = useResource(api, `analysis:${kpi}:${type}:${page}`, load, revision)
  return <div className="analysis-page"><div className="analysis-selector" role="tablist" aria-label="Kennzahl auswählen">{analyses.map((label, index) => <button key={label} role="tab" aria-selected={kpi === index + 1} onClick={() => { setKpi(index + 1); setPage(0) }}><span>{String(index + 1).padStart(2, '0')}</span>{label}</button>)}</div>
    {!data ? loading ? <Skeleton /> : <Empty message={error || undefined} /> : <><div className="analysis-heading"><div><h2>{data.title}</h2><p>{data.description}</p></div><label className="inline-select">Tickettyp<select aria-label="Tickettyp" value={type || ''} onChange={event => { setType(event.target.value || null); setPage(0) }}><option value="">Alle Tickettypen</option>{data.types.map(value => <option key={value}>{value}</option>)}</select></label></div>
      <div className="analysis-metrics">{data.metrics.map(metric => <MetricCard key={metric.label} metric={metric} />)}</div>
      <div className="analysis-grid"><Card title={data.chart.title} className="analysis-current"><Chart dto={data.chart} theme={theme} height={265} /><p className="chart-note">{data.note}</p></Card><Card title="Tickettypen" className="analysis-types"><Chart dto={data.typeChart} theme={theme} height={265} /><p className="chart-note">Verteilung aller Tickets dieser Kennzahl.</p></Card>
        <Card title="Historische Entwicklung" className="analysis-history"><Chart dto={data.history} theme={theme} height={210} /><p className="chart-note">{data.historyNote}</p></Card><Card title="Vergleich" className="analysis-comparison"><DataTable dto={data.comparison} /><p className="chart-note">Fehlende Vergleichswerte werden als «–» dargestellt.</p></Card>
        <Card title={data.tableTitle} className="analysis-details" aside={<span className="count-badge">{data.table.total} Tickets</span>}><p className="chart-note detail-note">{data.highlightNote}</p><DataTable dto={data.table} onTicket={onTicket} onPage={setPage} /></Card>
      </div></>}
  </div>
}
