import useSWRMutation from 'swr/mutation'
const poster = (url: string, { arg }: { arg: any }) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(arg) }).then(r => r.json())
export function useScreener() { return useSWRMutation('/api/screener', poster) }
