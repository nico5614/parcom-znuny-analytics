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
export interface DataState { connection: 'online' | 'cached' | 'offline'; busy: boolean; newData: boolean; revision: number; capturedAt: string | null; hasCache: boolean; warning: string }
export interface Period { start: string; end: string; startInput: string; endInput: string; label: string; preset: string | null; presets: string[] }
export type PeriodSelection = { preset: string } | { preset: null; start: string; end: string }
export interface Metric { label: string; value: string; note: string; tone: string }
export interface ChartDto { title: string; kind: 'line' | 'bar' | 'doughnut'; labels: string[]; datasets: { label: string; values: (number | null)[]; color: string }[] }
export interface TableDto { columns: { key: string; label: string }[]; rows: { key: string; ticketId?: string | null; cells: string[]; tone: string }[]; total: number; page: number; pageSize: number }
export interface Overview { metrics: Metric[]; operational: Metric[]; services: Metric[]; volume: ChartDto; agentChart: ChartDto; action: TableDto; waitingNote: string; score: { issue: string; status: string; areas: { label: string; value: number }[]; breakdown: { label: string; before: string; after: string; score: string }[]; history: ChartDto } }
export interface Analysis { title: string; description: string; metrics: Metric[]; chart: ChartDto; history: ChartDto; historyNote: string; comparison: TableDto; types: string[]; typeChart: ChartDto; note: string; highlightNote: string; tableTitle: string; table: TableDto }
export interface TicketDetails { id: string; number: string; title: string; fields: { label: string; value: string }[] }
declare global {
  interface Window { pywebview?: { api: DesktopApi } }
  interface WindowEventMap { 'parcom:desktop': CustomEvent<DesktopEvent> }
}
