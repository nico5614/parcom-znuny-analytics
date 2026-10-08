import { useEffect, useState } from 'react'
import type { DesktopApi, Result } from '../types/bridge'

const caches = new WeakMap<DesktopApi, Map<string, unknown>>()
export function clearResources(api: DesktopApi) { caches.delete(api) }
export function useResource<T>(api: DesktopApi, key: string, load: () => Promise<Result<T>>, revision: number) {
  let cache = caches.get(api)
  if (!cache) { cache = new Map(); caches.set(api, cache) }
  const cacheKey = `${revision}:${key}`
  const [result, setResult] = useState<{ key: string; value?: T; error: string; loading: boolean }>(() => ({ key: cacheKey, value: cache.get(cacheKey) as T | undefined, error: '', loading: !cache.has(cacheKey) }))
  useEffect(() => {
    let active = true
    const cached = cache!.get(cacheKey) as T | undefined
    setResult(previous => ({ key: cacheKey, value: cached !== undefined ? cached : previous.key.endsWith(`:${key}`) ? previous.value : undefined, error: '', loading: cached === undefined }))
    if (cached === undefined) load().then(reply => {
      if (reply.ok) {
        cache!.set(cacheKey, reply.data)
        while (cache!.size > 64) cache!.delete(cache!.keys().next().value!)
      }
      if (active) setResult({ key: cacheKey, value: reply.ok ? reply.data : undefined, error: reply.ok ? '' : reply.error.message, loading: false })
    }).catch(() => { if (active) setResult({ key: cacheKey, error: 'Die Desktop-Verbindung wurde unterbrochen.', loading: false }) })
    return () => { active = false }
  }, [api, key, cacheKey, load, cache])
  return result.key === cacheKey ? result : { key: cacheKey, value: cache.has(cacheKey) ? cache.get(cacheKey) as T : result.key.endsWith(`:${key}`) ? result.value : undefined, error: '', loading: !cache.has(cacheKey) }
}
