import { useEffect, useRef } from 'react'
import { Chart as ChartJS, LineController, BarController, DoughnutController, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Filler, Legend, Tooltip, type ChartConfiguration, type ChartType, type Plugin, type ScriptableContext } from 'chart.js'
import type { ChartDto } from '../types/bridge'
import { useAnimations } from '../hooks/animations'

ChartJS.register(LineController, BarController, DoughnutController, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Filler, Legend, Tooltip)
export function chartData(dto: ChartDto) {
  return { labels: dto.labels, datasets: dto.datasets.map(dataset => { const maximum = peakIndex(dataset.values); return ({ label: dataset.label, data: dataset.values, borderColor: dataset.color,
    backgroundColor: dto.kind === 'doughnut' ? ['#FF5C6C', '#4C8DFF', '#FFB84D'] : dto.kind === 'bar' ? dataset.values.map((_, index) => `${dataset.color}${dataset.winnerIndices?.includes(index) ? 'FF' : index === maximum ? 'CC' : '50'}`) : `${dataset.color}30`,
    borderWidth: dto.kind === 'line' ? 2 : 0, pointRadius: dataset.values.map((_, index) => dto.kind === 'line' && index === maximum ? 4 : dto.labels.length > 20 ? 0 : 2), pointHoverRadius: 6, pointBackgroundColor: dataset.color, tension: .3, fill: dto.kind === 'line', borderRadius: dto.kind === 'bar' ? 3 : 0, maxBarThickness: 36, spanGaps: false }) }) }
}
export function peakIndex(values: (number | null)[]) {
  let best = -1
  values.forEach((value, index) => { if (value != null && Number.isFinite(value) && (best < 0 || value > values[best]!)) best = index })
  return best
}
export function chartHighlights(source: ChartDto | (() => ChartDto)): Plugin {
  return { id: 'parcomHighlights', afterDatasetsDraw(chart) {
    const dto = typeof source === 'function' ? source() : source
    const { ctx, chartArea } = chart
    dto.datasets.forEach((dataset, datasetIndex) => {
      const meta = chart.getDatasetMeta(datasetIndex)
      if (!chart.isDatasetVisible(datasetIndex)) return
      if (dto.kind === 'line') {
        const point = meta.data[peakIndex(dataset.values)]
        if (!point) return
        const { x } = point.getProps(['x'], false)
        if (!Number.isFinite(x)) return
        ctx.save(); ctx.strokeStyle = dataset.color; ctx.globalAlpha = .3; ctx.lineWidth = 1; ctx.setLineDash([3, 4])
        ctx.beginPath(); ctx.moveTo(x, chartArea.top); ctx.lineTo(x, chartArea.bottom); ctx.stroke(); ctx.restore()
      } else if (dto.kind === 'bar') dataset.winnerIndices?.forEach(index => {
        const bar = meta.data[index]
        if (!bar) return
        const { x, y } = bar.getProps(['x', 'y'], false)
        ctx.save(); ctx.strokeStyle = '#d5a53c'; ctx.lineWidth = 1.5; ctx.beginPath()
        ctx.moveTo(x-6, y-9); ctx.lineTo(x-3, y-6); ctx.lineTo(x, y-12); ctx.lineTo(x+3, y-6); ctx.lineTo(x+6, y-9); ctx.lineTo(x+5, y-3); ctx.lineTo(x-5, y-3); ctx.closePath(); ctx.stroke(); ctx.restore()
      })
    })
  } }
}
export function animationOptions(kind: ChartDto['kind'], count: number, enabled: boolean): ChartConfiguration['options'] {
  if (!enabled) return { animation: { duration: 0 } }
  if (kind !== 'line') return { animation: { duration: 650, easing: 'easeOutCubic', ...(kind === 'doughnut' ? { animateRotate: true, animateScale: false } : {}) } }
  const step = 700 / Math.max(1, count)
  return { animation: { duration: 700 }, animations: {
    x: { type: 'number', easing: 'linear', duration: step, from: NaN, delay: (context: ScriptableContext<ChartType>) => context.type === 'data' ? context.dataIndex * step : 0 },
    y: { type: 'number', easing: 'linear', duration: step, from: (context: ScriptableContext<ChartType>) => context.type !== 'data' || context.dataIndex === 0 ? context.chart.scales.y.getPixelForValue(0) : context.chart.getDatasetMeta(context.datasetIndex).data[context.dataIndex-1]?.getProps(['y'], true).y ?? context.chart.scales.y.getPixelForValue(0),
      delay: (context: ScriptableContext<ChartType>) => context.type === 'data' ? context.dataIndex * step : 0 }
  } }
}
export function Chart({ dto, height = 240, theme = 'dark' }: { dto: ChartDto; height?: number; theme?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const chart = useRef<ChartJS>(null)
  const kind = useRef<ChartDto['kind']>(null)
  const signature = useRef('')
  const highlightSource = useRef(dto)
  highlightSource.current = dto
  const animations = useAnimations()
  useEffect(() => {
    if (!canvas.current) return
    const color = theme === 'light' ? '#64748b' : '#8e9cac'
    const grid = theme === 'light' ? '#e7ebf0' : '#20324765'
    const options: ChartConfiguration['options'] = {
      responsive: true, maintainAspectRatio: false, ...animationOptions(dto.kind, dto.labels.length, animations),
      plugins: { legend: { position: 'top', align: 'start', labels: { color, usePointStyle: true, pointStyle: 'circle', boxWidth: 6, boxHeight: 6, padding: 20, font: { family: 'Segoe UI', size: 11 } } }, tooltip: { mode: 'index', intersect: false, backgroundColor: '#101c29', borderColor: '#203247', borderWidth: 1, padding: 12, callbacks: { label: context => `${context.dataIndex === peakIndex(dto.datasets[context.datasetIndex].values) ? 'Spitze · ' : ''}${context.dataset.label}: ${context.formattedValue}` } } },
      ...(dto.kind === 'doughnut' ? { cutout: '72%' } : { scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color, maxTicksLimit: 8, maxRotation: 0, font: { size: 11 } } }, y: { beginAtZero: true, title: { display: Boolean(dto.unitLabel), text: dto.unitLabel || '', color, font: { size: 10 } }, grid: { color }, border: { display: false }, ticks: { color, precision: 0, maxTicksLimit: 5, font: { size: 11 } } } } }),
    }
    if (options.scales?.x?.ticks) options.scales.x.ticks.callback = function(value) { const label = this.getLabelForValue(Number(value)); return label.length > 26 ? label.slice(0, 25) + '…' : label }
    if (options.scales?.y?.grid) options.scales.y.grid.color = grid
    const nextSignature = JSON.stringify(dto)
    if (chart.current && kind.current === dto.kind) {
      chart.current.data = chartData(dto)
      chart.current.options = options
      if (animations && signature.current !== nextSignature) { chart.current.stop(); chart.current.update('none'); chart.current.reset(); chart.current.update() }
      else chart.current.update('none')
    } else {
      chart.current?.destroy()
      chart.current = new ChartJS(canvas.current, { type: dto.kind, data: chartData(dto), options, plugins: [chartHighlights(() => highlightSource.current)] } as ChartConfiguration)
      kind.current = dto.kind
    }
    signature.current = nextSignature
  }, [dto, theme, animations])
  useEffect(() => () => { chart.current?.destroy(); chart.current = null }, [])
  return <div className="chart-wrap" style={{ height }}><canvas ref={canvas} role="img" aria-label={dto.title} /><span className="sr-only">{dto.datasets.map(dataset => { const index = peakIndex(dataset.values); return `${dataset.label}: ${dataset.values.join(', ')}. ${index >= 0 ? `Spitze: ${dto.labels[index]}, ${dataset.values[index]}` : ''}` }).join('; ')}</span></div>
}
