import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const base = 'https://astockpursue.com'
  return ['', '/market', '/backtest', '/trading', '/strategy-lab', '/broker', '/screener', '/factors', '/agent', '/settings'].map((path) => ({
    url: `${base}${path}`,
    lastModified: new Date(),
    changeFrequency: 'weekly' as const,
    priority: path === '' ? 1 : 0.8,
  }))
}
