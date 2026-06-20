// frontend/components/financial/CorrelationMatrix.tsx
'use client'
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { OLED } from '@/lib/constants'

interface Props { symbols: string[]; matrix: number[][] }

export function CorrelationMatrix({ symbols, matrix }: Props) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current || !symbols.length) return
    const svg = d3.select(ref.current); svg.selectAll('*').remove()
    const size = Math.min(ref.current.clientWidth, 300)
    const cellSize = size / symbols.length
    const cs = d3.scaleLinear<string>().domain([-1, 0, 1]).range([OLED.down, OLED.surface3, OLED.up])
    const g = svg.attr('width', size).attr('height', size).append('g')
    matrix.forEach((row, i) => row.forEach((v, j) => {
      g.append('rect').attr('x', j*cellSize).attr('y', i*cellSize).attr('width', cellSize-1).attr('height', cellSize-1).attr('fill', cs(v)).attr('rx', 2)
      g.append('text').attr('x', j*cellSize+cellSize/2).attr('y', i*cellSize+cellSize/2).attr('text-anchor','middle').attr('dy','0.35em')
        .text(v.toFixed(2)).style('font-size',`${Math.max(9,cellSize/5)}px`).style('fill', Math.abs(v)>0.5?'#fff':OLED.foregroundSecondary).style('font-family','Fira Code, monospace')
    }))
  }, [symbols, matrix])
  return <svg ref={ref} width="100%" height={300} />
}
