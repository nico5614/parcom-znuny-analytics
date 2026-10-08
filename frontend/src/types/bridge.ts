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
  login(username: string, password: string): Promise<Result<Session>>
  logout(): Promise<Result<null>>
  getAppInfo(): Promise<AppInfo>
  probe(): Promise<{ sequence: number; sentAt: string }>
  confirmProbe(sequence: number): Promise<boolean>
}
declare global {
  interface Window { pywebview?: { api: DesktopApi } }
  interface WindowEventMap { 'parcom:desktop': CustomEvent<DesktopEvent> }
}
