import { describe, expect, it, vi } from 'vitest'
import type { ChartDto } from '../types/bridge'
import { animationOptions, chartData, chartHighlights, peakIndex } from './Chart'

const dto: ChartDto = { title: 'Tickets', kind: 'line', labels: ['A', 'B', 'C'], datasets: [
  { label: 'Neu', values: [1, 9, 3], color: '#0054B1' }, { label: 'Geschlossen', values: [7, 2, null], color: '#037C35' } ] }
describe('chart emphasis and animation policy', () => {
  it('marks each series own maximum and ignores missing values', () => {
    expect(peakIndex([null, NaN, 0, 2])).toBe(3)
    expect(peakIndex([null, NaN])).toBe(-1)
    expect(chartData(dto).datasets.map(dataset => dataset.pointRadius)).toEqual([[2, 4, 2], [4, 2, 2]])
  })
  it('emphasizes the highest bar without recoloring the whole series', () => {
    expect(chartData({ ...dto, kind: 'bar' }).datasets[0].backgroundColor).toEqual(['#0054B150', '#0054B1CC', '#0054B150'])
  })
  it('draws a dashed guide at each series peak coordinate', () => {
    const ctx = { save: vi.fn(), restore: vi.fn(), setLineDash: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn() }
    const chart = { ctx, chartArea: { top: 0, bottom: 100 }, isDatasetVisible: () => true, getDatasetMeta: () => ({ data: [10, 20, 30].map(x => ({ getProps: () => ({ x }) })) }) }
    chartHighlights(dto).afterDatasetsDraw!(chart as never, {} as never, {} as never, {} as never)
    expect(ctx.setLineDash).toHaveBeenCalledWith([3, 4])
    expect(ctx.moveTo.mock.calls).toEqual([[20, 0], [10, 0]])
  })
  it('uses zero duration when animations are disabled and native options otherwise', () => {
    expect(animationOptions('line', 3, false)?.animation).toEqual({ duration: 0 })
    expect(animationOptions('bar', 3, true)?.animation).toMatchObject({ duration: 650 })
    expect(animationOptions('line', 3, true)?.animations?.x).toMatchObject({ from: NaN })
  })
  it('only draws a crown when backend-supplied winner indices exist', () => {
    const chart = { ctx: { save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), closePath: vi.fn(), stroke: vi.fn() }, chartArea: {}, isDatasetVisible: () => true, getDatasetMeta: () => ({ data: [{ getProps: () => ({ x: 20, y: 30 }) }] }) }
    chartHighlights({ ...dto, kind: 'bar' }).afterDatasetsDraw!(chart as never, {} as never, {} as never, {} as never)
    expect(chart.ctx.stroke).not.toHaveBeenCalled()
    chartHighlights({ ...dto, kind: 'bar', datasets: [{ ...dto.datasets[0], winnerIndices: [0] }] }).afterDatasetsDraw!(chart as never, {} as never, {} as never, {} as never)
    expect(chart.ctx.stroke).toHaveBeenCalledOnce()
  })
})
