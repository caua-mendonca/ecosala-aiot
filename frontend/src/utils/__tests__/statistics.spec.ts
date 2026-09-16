import { describe, expect, it } from 'vitest'
import { computeStats } from '../statistics'

describe('computeStats', () => {
  it('calcula minimo, maximo e media de uma lista de valores', () => {
    const stats = computeStats([20, 24, 26, 30])

    expect(stats.min).toBe(20)
    expect(stats.max).toBe(30)
    expect(stats.mean).toBe(25)
  })

  it('retorna zeros para uma lista vazia', () => {
    expect(computeStats([])).toEqual({ min: 0, max: 0, mean: 0 })
  })

  it('funciona com um unico valor', () => {
    expect(computeStats([42])).toEqual({ min: 42, max: 42, mean: 42 })
  })
})
