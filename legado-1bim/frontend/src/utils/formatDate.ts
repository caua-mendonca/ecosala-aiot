export function formatDateTimeShort(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDateTimeFull(isoTimestamp: string): string {
  return new Date(isoTimestamp).toLocaleString('pt-BR')
}
