import 'jsr:@supabase/functions-js/edge-runtime.d.ts'

// Supabase's built-in gte-small model keeps embeddings independent of the
// Groq diary-answer model and sends only user-written title/body text.
const session = new Supabase.ai.Session('gte-small')

Deno.serve(async (request) => {
  if (request.method !== 'POST') {
    return Response.json({ error: 'Only POST is supported' }, { status: 405 })
  }

  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 })
  }
  const input = typeof payload === 'object' && payload !== null
    ? (payload as { input?: unknown }).input
    : null
  if (typeof input !== 'string' || input.trim().length === 0 || input.length > 8000) {
    return Response.json({ error: 'input must be 1–8000 characters' }, { status: 422 })
  }

  const embedding = await session.run(input.trim(), {
    mean_pool: true,
    normalize: true,
  })
  return Response.json({ model: 'Supabase/gte-small', dimensions: embedding.length, embedding })
})
