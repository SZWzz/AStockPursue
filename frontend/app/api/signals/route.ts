import { NextRequest } from 'next/server'
import { bffProxy } from '@/lib/bff-proxy'

export async function GET(req: NextRequest) { return bffProxy(req, 'GET') }
