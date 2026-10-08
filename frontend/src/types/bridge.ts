export interface AppInfo {
  name: string
  version: string
  python: string
  renderer: string
  packaged: boolean
}
export interface DesktopEvent { kind: 'probe'; message: string; sequence: number }
export type Result<T> = { ok: true; data: T } | { ok: false; error: { kind: string; message: string } }
export interface Session { username: string }
export interface DesktopApi {
  getState(): Promise<DataState>
  getPeriod(): Promise<Period>
  resolvePeriod(selection: PeriodSelection): Promise<Result<Period>>
  getPreferences(): Promise<Preferences>
  setPreferences(theme: 'dark' | 'light', reducedMotion: boolean): Promise<Result<null>>
  continueOffline(): Promise<Result<Session>>
  getOverview(): Promise<Result<Overview | null>>
  getAnalysis(kpi: number, ticketType: string | null, page: number): Promise<Result<Analysis | null>>
  getAgents(agentId: string | null, page: number): Promise<Result<Agents | null>>
  setTeam(selected: string[]): Promise<Result<DataState>>
  getAgentOverride?(id: string): Promise<Result<{ name?: string; code?: string }>>
  setAgentDisplayName?(id: string, name: string): Promise<Result<AgentIdentity>>
  setAgentAbbreviation?(id: string, code: string): Promise<Result<AgentIdentity>>
  resetAgentOverride?(id: string): Promise<Result<AgentIdentity>>
  getExportOptions(): Promise<{ id: string; label: string; types: string[] }[]>
  exportPdf(target: string, ticketType: string | null): Promise<Result<{ cancelled: boolean; filename: string | null }>>
  getTicketDetails(ticketId: string): Promise<Result<TicketDetails | null>>
  openTicket(ticketId: string): Promise<Result<null>>
  refresh(selection: PeriodSelection): Promise<Result<DataState>>
  checkChanges(): Promise<DataState>
  login(username: string, password: string): Promise<Result<Session>>
  logout(): Promise<Result<null>>
  getAppInfo(): Promise<AppInfo>
  probe(): Promise<{ sequence: number; sentAt: string }>
  confirmProbe(sequence: number): Promise<boolean>
}
export interface Preferences { theme: 'dark' | 'light'; reducedMotion: boolean }
export interface DataState { connection: 'online' | 'cached' | 'offline'; busy: boolean; newData: boolean; revision: number; capturedAt: string | null; hasCache: boolean; warning: string; lastSuccessfulConnection?: string | null }
export interface Period { start: string; end: string; startInput: string; endInput: string; label: string; preset: string | null; presets: string[] }
export type PeriodSelection = { preset: string } | { preset: null; start: string; end: string }
export interface Comparison {
  value?: number | null; numericValue?: number | null; previous?: number | null
  delta?: number | null; deltaPercent?: number | null; deltaAvailable?: boolean
  trend?: 'improvement' | 'deterioration' | 'neutral'; metricType?: 'flow' | 'snapshot'
  contextLabel?: string; snapshotAt?: string; snapshotIsNow?: boolean
  unit?: 'count' | 'minutes' | 'percent'; valueAvailable?: boolean
}
export interface Metric extends Omit<Comparison, 'value'> { label: string; value: string; note: string; tone: string; primary?: boolean }
export interface ChartDto { title: string; kind: 'line' | 'bar' | 'doughnut'; labels: string[]; unitLabel?: string; datasets: { label: string; values: (number | null)[]; color: string; winnerIndices?: number[] }[] }
export interface TableDto { columns: { key: string; label: string }[]; rows: { key: string; ticketId?: string | null; cells: string[]; tone: string; maximum?: boolean }[]; total: number; page: number; pageSize: number }
export interface Overview { comparisons?: Record<string, Comparison>; metrics: Metric[]; operational: Metric[]; services: Metric[]; volume: ChartDto; agentChart: ChartDto; action: TableDto; waitingNote: string; score: { issue: string; status: string; areas: { label: string; value: number }[]; breakdown: { label: string; before: string; after: string; score: string }[]; history: ChartDto } }
export interface Analysis { title: string; description: string; metrics: Metric[]; chart: ChartDto; history: ChartDto; historyNote: string; comparison: TableDto; types: string[]; typeChart: ChartDto; note: string; highlightNote: string; tableTitle: string; table: TableDto }
export interface TicketDetails { id: string; number: string; title: string; fields: { label: string; value: string }[] }
export interface AgentIdentity { id: string; login: string; name: string; code: string }
export interface AgentRow { id: string; label?: string; displayName?: string; abbreviation?: string; rank?: number | null; isPeriodWinner?: boolean; Geschlossen: number | null; Erstantworten: number | null; 'Aktuell im Besitz': number | null; 'Davon gesperrt': number | null; 'Reaktionszeit (Min.)': number | null; medianResponseMinutes?: number | null; meanResponseMinutes?: number | null; responseComparison?: Comparison; meanResponseComparison?: Comparison }
export interface Agents { historyLoaded: boolean; registry: AgentIdentity[]; selected: string[]; metrics: Metric[]; rows: AgentRow[]; periodWinner?: AgentRow | null; periodWinners?: AgentRow[]; winnerAvailable?: boolean; note: string; rankingNote: string; chart: ChartDto; table: TableDto }
declare global {
  interface Window { pywebview?: { api: DesktopApi } }
  interface WindowEventMap { 'parcom:desktop': CustomEvent<DesktopEvent> }
}
