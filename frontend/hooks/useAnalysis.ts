import useSWRMutation from 'swr/mutation'

const poster = (url: string, { arg }: { arg: { type: string; params?: Record<string, any> } }) => {
  const isGet = arg.type === 'drawdown'
  let fetchUrl = `/api/analysis/${arg.type}`

  if (isGet && arg.params) {
    const qs = new URLSearchParams()
    Object.entries(arg.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, String(v))
    })
    const qsStr = qs.toString()
    if (qsStr) fetchUrl += `?${qsStr}`
  }

  return fetch(fetchUrl, {
    method: isGet ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: isGet ? undefined : JSON.stringify(arg.params)
  }).then(r => r.json())
}

export function useAnalysis() { return useSWRMutation('/api/analysis', poster) }
