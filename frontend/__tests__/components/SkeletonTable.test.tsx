import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { SkeletonTable } from '@/components/ui/SkeletonTable'

describe('SkeletonTable', () => {
  it('renders with default rows and cols', () => {
    const { container } = render(<SkeletonTable />)
    // Should render 5 row wrappers
    const rows = container.querySelectorAll('.flex.gap-3')
    expect(rows.length).toBeGreaterThanOrEqual(1)
  })

  it('renders custom rows and cols', () => {
    const { container } = render(<SkeletonTable rows={3} cols={2} />)
    const rows = container.querySelectorAll('.flex.gap-3')
    expect(rows.length).toBe(3)
    // Each row should have 2 skeleton cells
    const firstRow = rows[0]
    expect(firstRow.children.length).toBe(2)
  })

  it('renders with custom className', () => {
    const { container } = render(<SkeletonTable rows={1} cols={1} />)
    const skeleton = container.querySelector('.animate-pulse')
    expect(skeleton).toBeTruthy()
  })
})
