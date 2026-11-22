const DEFAULT_FRACTION_DIGITS = 1

export function formatNumber(
  value: number,
  fractionDigits: number = DEFAULT_FRACTION_DIGITS,
): string {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}
