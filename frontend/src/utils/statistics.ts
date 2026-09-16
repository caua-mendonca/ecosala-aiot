export interface Stats {
  min: number
  max: number
  mean: number
}

export function computeStats(values: number[]): Stats {
  if (values.length === 0) {
    return { min: 0, max: 0, mean: 0 }
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length

  return { min, max, mean }
}
