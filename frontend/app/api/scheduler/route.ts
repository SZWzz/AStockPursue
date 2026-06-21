import { NextRequest } from 'next/server'
import { bffProxy } from '@/lib/bff-proxy'

export async function GET(req: NextRequest)    { return bffProxy(req, 'GET') }
export async function POST(req: NextRequest)   { return bffProxy(req, 'POST') }
export async function PUT(req: NextRequest)    { return bffProxy(req, 'PUT') }
export async function DELETE(req: NextRequest) { return bffProxy(req, 'DELETE') }
