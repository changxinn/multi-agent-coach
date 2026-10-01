import { describe, expect, it } from 'vitest'
import { getPageSizeOptions, Pagination } from './pagination'

describe('getPageSizeOptions', () => {
  it('returns all configured options when no maximum is supplied', () => {
    expect(getPageSizeOptions()).toEqual(Pagination.PageSizeOptions)
  })

  it('filters options above the supplied maximum', () => {
    expect(getPageSizeOptions(20)).toEqual([5, 10, 20])
  })

  it('returns no options when the maximum is below the minimum page size', () => {
    expect(getPageSizeOptions(4)).toEqual([])
  })
})