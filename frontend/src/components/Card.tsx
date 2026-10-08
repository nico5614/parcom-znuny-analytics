import type { ReactNode } from 'react'
import type { Metric } from '../types/bridge'
import { MetricTrend } from './MetricTrend'
export function Card({ title, children, className = '', aside }: { title?: string; children: ReactNode; className?: string; aside?: ReactNode }) {
  return <section className={`card ${className}`}>{title && <header className="card-header"><h2>{title}</h2>{aside}</header>}<div className="card-body">{children}</div></section>
}
export function MetricCard({ metric }: { metric: Metric }) {
  return <section className={`card metric-card ${metric.tone} ${metric.primary === false ? 'secondary-metric' : ''}`}><p>{metric.label}</p><strong title={metric.value} className={metric.value.length > 12 ? 'long-value' : ''}>{metric.value}</strong><span>{metric.contextLabel || metric.note}</span><MetricTrend metric={metric} /></section>
}
export function Skeleton({ rows = false }: { rows?: boolean }) {
  return <div role="status" aria-label="Znuny-Daten werden geladen …" className={rows ? 'skeleton-table' : 'skeleton-dashboard'}>{Array.from({ length: rows ? 5 : 8 }, (_, i) => <div key={i} className="skeleton"><span /><span /></div>)}</div>
}
export function Empty({ message = 'Noch kein Datenstand geladen.' }: { message?: string }) {
  return <div className="empty-state"><span className="empty-symbol">↗</span><h2>{message}</h2><p>Mit Znuny verbinden und den Datenstand aktualisieren.</p></div>
}
