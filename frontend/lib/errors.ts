// frontend/lib/errors.ts
// BFF error aggregation — translates HTTP error status codes to user-friendly messages.

export const ERROR_MAP: Record<number, string> = {
  503: 'Python 研究层离线，部分功能不可用',
  500: '服务内部错误，请稍后重试',
  502: '后端服务不可用',
}

export function translateError(status: number): string {
  return ERROR_MAP[status] || `请求失败 (HTTP ${status})`
}
