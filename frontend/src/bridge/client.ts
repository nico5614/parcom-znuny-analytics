import type { DesktopApi } from '../types/bridge'

export function desktop(): Promise<DesktopApi> {
  if (typeof window.pywebview?.api?.getAppInfo === 'function') return Promise.resolve(window.pywebview.api)
  return new Promise((resolve, reject) => {
    const onReady = () => {
      clearTimeout(timeout)
      window.removeEventListener('pywebviewready', onReady)
      if (typeof window.pywebview?.api?.getAppInfo === 'function') resolve(window.pywebview.api)
      else reject(new Error('Die Desktop-Verbindung ist nicht verfügbar.'))
    }
    const timeout = setTimeout(() => {
      window.removeEventListener('pywebviewready', onReady)
      reject(new Error('Bitte starten Sie ParCom Analytics als Desktop-Anwendung.'))
    }, 12000)
    window.addEventListener('pywebviewready', onReady)
  })
}
