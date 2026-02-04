import 'dotenv/config';
import cors from 'cors';
import express from 'express';
import { z } from 'zod';
import { GoogleGenerativeAI, type GenerativeModel } from '@google/generative-ai';

const PORT = Number(process.env.PORT ?? 8787);
const CORS_ORIGIN = process.env.CORS_ORIGIN;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
  // Fail fast so it is obvious in dev.
  // eslint-disable-next-line no-console
  console.error('Missing GEMINI_API_KEY. Copy apps/api/.env.example to apps/api/.env and set GEMINI_API_KEY.');
}

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '1mb' }));

if (CORS_ORIGIN) {
  app.use(cors({ origin: CORS_ORIGIN }));
}

app.get('/api/health', (_req, res) => {
  res.json({ ok: true });
});

const ChatStreamBodySchema = z.object({
  messages: z
    .array(
      z.object({
        role: z.enum(['user', 'assistant', 'system']).default('user'),
        content: z.string().min(1)
      })
    )
    .min(1),
  faceSignals: z
    .object({
      enabled: z.boolean().optional(),
      stressIndex: z.number().min(0).max(100).optional(),
      level: z.string().optional(),
      blinkPerMin: z.number().min(0).max(120).optional(),
      jawOpenness: z.number().min(0).max(1).optional(),
      browTension: z.number().min(0).max(1).optional()
    })
    .optional()
});

function getModel(): GenerativeModel {
  if (!GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is not configured');
  }
  const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
  // You can switch model here if needed
  return genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
}

function buildSystemPrompt(faceSignals?: z.infer<typeof ChatStreamBodySchema>['faceSignals']): string {
  const faceContext = faceSignals?.enabled
    ? `\n\nKONTEKS FACE TRACKING (indikatif, bukan diagnosis):\n- stressIndex: ${faceSignals.stressIndex ?? 'n/a'} (0-100)\n- level: ${faceSignals.level ?? 'n/a'}\n- blinkPerMin: ${faceSignals.blinkPerMin ?? 'n/a'}\n- jawOpenness: ${faceSignals.jawOpenness ?? 'n/a'}\n- browTension: ${faceSignals.browTension ?? 'n/a'}\nGunakan konteks ini hanya sebagai sinyal tambahan, jangan menyimpulkan kondisi medis.`
    : '';

  return [
    'Kamu adalah asisten konsultasi dini di luar medis untuk membantu pengguna memahami stres secara umum.',
    'Aturan penting:',
    '- BUKAN diagnosis medis dan tidak menggantikan psikolog/psikiater/dokter.',
    '- Berikan saran langkah awal yang aman, praktis, dan bisa dilakukan sekarang.',
    '- Jika ada tanda bahaya (pikiran menyakiti diri, panik berat, nyeri dada, sesak, pingsan, kekerasan, atau tidak aman), sarankan segera menghubungi layanan darurat/tenaga profesional.',
    '- Tanyakan 1-3 pertanyaan klarifikasi bila informasi kurang.',
    '',
    'Outputkan jawaban dalam Bahasa Indonesia, ringkas tapi empatik.',
    '',
    'Di akhir jawaban, sertakan blok JSON tunggal bernama "analysis" dengan format:',
    '{"topics": string[], "summary": string, "stress_level": "rendah"|"sedang"|"tinggi", "early_actions": string[], "when_to_seek_help": string[], "disclaimer": string}',
    'Pastikan JSON valid dan mudah diparse.',
    faceContext
  ].join('\n');
}

function toGeminiContents(messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>) {
  // Gemini expects role user/model; we fold system into user prefix.
  const contents: Array<{ role: 'user' | 'model'; parts: Array<{ text: string }> }> = [];
  for (const m of messages) {
    if (m.role === 'assistant') {
      contents.push({ role: 'model', parts: [{ text: m.content }] });
    } else {
      contents.push({ role: 'user', parts: [{ text: m.content }] });
    }
  }
  return contents;
}

app.post('/api/chat/stream', async (req, res) => {
  try {
    const parsed = ChatStreamBodySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: 'Invalid request', details: parsed.error.flatten() });
      return;
    }

    res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');

    // A small ping helps some proxies keep the connection.
    res.write('event: ping\n');
    res.write(`data: ${JSON.stringify({ t: Date.now() })}\n\n`);

    const systemPrompt = buildSystemPrompt(parsed.data.faceSignals);
    const messages = parsed.data.messages;

    const model = getModel();

    const result = await model.generateContentStream({
      contents: toGeminiContents([{ role: 'user', content: systemPrompt }, ...messages])
    });

    for await (const chunk of result.stream) {
      const text = chunk.text();
      if (!text) continue;
      res.write('event: token\n');
      res.write(`data: ${JSON.stringify({ token: text })}\n\n`);
    }

    res.write('event: done\n');
    res.write(`data: ${JSON.stringify({ ok: true })}\n\n`);
    res.end();
  } catch (err) {
    res.write('event: error\n');
    res.write(`data: ${JSON.stringify({ message: err instanceof Error ? err.message : 'Unknown error' })}\n\n`);
    res.end();
  }
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`API listening on http://localhost:${PORT}`);
});
