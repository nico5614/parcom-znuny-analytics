import { useEffect, useRef } from 'react'
import { Chart as ChartJS, LineController, BarController, DoughnutController, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Filler, Legend, Tooltip, type ChartConfiguration } from 'chart.js'
import type { ChartDto } from '../types/bridge'

ChartJS.register(LineController, BarController, DoughnutController, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Filler, Legend, Tooltip)
export function chartData(dto: ChartDto) {
  return { labels: dto.labels, datasets: dto.datasets.map(dataset => ({ label: dataset.label, data: dataset.values, borderColor: dataset.color, backgroundColor: dto.kind === 'doughnut' ? ['#FF5C6C', '#4C8DFF', '#FFB84D'] : `${dataset.color}30`, borderWidth: dto.kind === 'line' ? 2 : 0, pointRadius: dto.labels.length > 20 ? 0 : 2, pointHoverRadius: 5, tension: .3, fill: dto.kind === 'line', borderRadius: dto.kind === 'bar' ? 3 : 0, maxBarThickness: 36, spanGaps: false })) }
}
export function Chart({ dto, height = 240, theme = 'dark' }: { dto: ChartDto; height?: number; theme?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const chart = useRef<ChartJS>(null)
  const kind = useRef<ChartDto['kind']>(null)
  useEffect(() => {
    if (!canvas.current) return
    const color = theme === 'light' ? '#64748b' : '#8e9cac'
    const grid = theme === 'light' ? '#e7ebf0' : '#20324765'
    const options: ChartConfiguration['options'] = {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { position: 'top', align: 'start', labels: { color, usePointStyle: true, pointStyle: 'circle', boxWidth: 6, boxHeight: 6, padding: 20, font: { family: 'Segoe UI', size: 11 } } }, tooltip: { mode: 'index', intersect: false, backgroundColor: '#101c29', borderColor: '#203247', borderWidth: 1, padding: 12 } },
      ...(dto.kind === 'doughnut' ? { cutout: '72%' } : { scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color, maxTicksLimit: 8, maxRotation: 0, font: { size: 11 } } }, y: { beginAtZero: true, title: { display: Boolean(dto.unitLabel), text: dto.unitLabel || '', color, font: { size: 10 } }, grid: { color }, border: { display: false }, ticks: { color, precision: 0, maxTicksLimit: 5, font: { size: 11 } } } } }),
    }
    if (options.scales?.x?.ticks) options.scales.x.ticks.callback = function(value) { const label = this.getLabelForValue(Number(value)); return label.length > 26 ? label.slice(0, 25) + '…' : label }
    if (options.scales?.y?.grid) options.scales.y.grid.color = grid
    if (chart.current && kind.current === dto.kind) {
      chart.current.data = chartData(dto)
      chart.current.options = options
      chart.current.update('none')
    } else {
      chart.current?.destroy()
      chart.current = new ChartJS(canvas.current, { type: dto.kind, data: chartData(dto), options } as ChartConfiguration)
      kind.current = dto.kind
    }
  }, [dto, theme])
  useEffect(() => () => { chart.current?.destroy(); chart.current = null }, [])
  return <div className="chart-wrap" style={{ height }}><canvas ref={canvas} role="img" aria-label={dto.title} /><span className="sr-only">{dto.datasets.map(dataset => `${dataset.label}: ${dataset.values.join(', ')}`).join('; ')}</span></div>
}
