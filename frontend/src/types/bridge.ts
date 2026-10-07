export interface AppInfo {
  name: string
  version: string
  python: string
  renderer: string
  packaged: boolean
}
export interface DesktopEvent { kind: 'probe'; message: string; sequence: number }
export interface DesktopApi {
  getAppInfo(): Promise<AppInfo>
  probe(): Promise<{ sequence: number; sentAt: string }>
  confirmProbe(sequence: number): Promise<boolean>
}
declare global {
  interface Window { pywebview?: { api: DesktopApi } }
  interface WindowEventMap { 'parcom:desktop': CustomEvent<DesktopEvent> }
}
