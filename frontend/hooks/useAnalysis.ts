import useSWRMutation from 'swr/mutation'
const poster = (url: string, { arg }: { arg: { type: string; params: any } }) =>
  fetch(`/api/analysis/${arg.type}`, {
    method: arg.type === 'drawdown' ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: arg.type === 'drawdown' ? undefined : JSON.stringify(arg.params)
  }).then(r => r.json())
export function useAnalysis() { return useSWRMutation('/api/analysis', poster) }
