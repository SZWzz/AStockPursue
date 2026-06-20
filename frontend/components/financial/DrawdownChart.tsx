// frontend/components/financial/DrawdownChart.tsx
'use client'

import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { OLED } from '@/lib/constants'

interface DD { time: string; drawdown: number }

export function DrawdownChart({ data }: { data: DD[] }) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !data.length) return
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()

    const margin = { top: 10, right: 10, bottom: 20, left: 40 }
    const width = ref.current.clientWidth - margin.left - margin.right
    const height = 200 - margin.top - margin.bottom

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const x = d3.scalePoint().domain(data.map(d => d.time)).range([0, width])
    const y = d3.scaleLinear().domain([d3.min(data, d => d.drawdown) || -1, 0]).range([height, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(d3.format('.0%')))
      .selectAll('text').attr('fill', OLED.foregroundMuted).style('font-size', '10px')
    g.selectAll('.domain, .tick line').attr('stroke', OLED.borderSubtle)

    const area = d3.area<DD>().x(d => x(d.time)!).y0(y(0)).y1(d => y(d.drawdown))
    g.append('path').datum(data).attr('fill', OLED.down).attr('fill-opacity', 0.2).attr('d', area)
    g.append('path').datum(data).attr('fill', 'none').attr('stroke', OLED.down).attr('stroke-width', 1.5).attr('d', area)
  }, [data])

  return <svg ref={ref} width="100%" height={200} />
}
