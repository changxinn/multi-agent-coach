import { describe, expect, it } from 'vitest'
import { compatibilityStatusColor } from './compatibilityStatus'

describe('compatibilityStatusColor', () => {
  it.each([
    ['approved', 'green'],
    ['rejected', 'red'],
    ['review_required', 'gold'],
    ['pending', 'blue'],
  ])('maps %s reviews to %s tags', (status, color) => {
    expect(compatibilityStatusColor(status)).toBe(color)
  })
})