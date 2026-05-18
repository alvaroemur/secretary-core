import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from "url";
import { createReadStream, statSync } from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const INBOX_DIR = path.resolve(__dirname, "../inbox");
const MEDIA_DIR = path.join(INBOX_DIR, "media");
const TRANSCRIPTS_DIR = path.join(INBOX_DIR, "transcripts");

const args = process.argv.slice(2);
let inputPath = "";
let lang = "es";
let model = "whisper-1";
let allMissing = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "-i") inputPath = args[++i];
  else if (args[i] === "-l") lang = args[++i];
  else if (args[i] === "--model") model = args[++i];
  else if (args[i] === "--all-missing") allMissing = true;
}

const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) {
  console.error("Falta OPENAI_API_KEY en el entorno.");
  process.exit(1);
}

async function transcribeFile(audioPath: string): Promise<string> {
  const fileStats = statSync(audioPath);
  const filename = path.basename(audioPath);
  const stream = createReadStream(audioPath);
  const chunks: Buffer[] = [];
  for await (const c of stream) chunks.push(c as Buffer);
  const fileBuf = Buffer.concat(chunks);

  const form = new FormData();
  form.append("file", new Blob([fileBuf], { type: "audio/ogg" }), filename);
  form.append("model", model);
  form.append("language", lang);

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Whisper API ${res.status}: ${txt}`);
  }
  const json = (await res.json()) as { text: string };
  return json.text;
}

function transcriptPathFor(audioPath: string): string {
  const rel = path.relative(MEDIA_DIR, audioPath);
  return path.join(TRANSCRIPTS_DIR, rel.replace(/\.ogg$/, ".txt"));
}

async function processOne(audioPath: string): Promise<void> {
  const outPath = transcriptPathFor(audioPath);
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  console.log(`→ ${path.relative(INBOX_DIR, audioPath)}`);
  const text = await transcribeFile(audioPath);
  await fs.writeFile(outPath, text + "\n");
  console.log(`  ✅ ${path.relative(INBOX_DIR, outPath)} (${text.length} chars)`);
}

async function findMissing(): Promise<string[]> {
  const out: string[] = [];
  async function walk(dir: string) {
    let entries: string[] = [];
    try { entries = await fs.readdir(dir); } catch { return; }
    for (const e of entries) {
      const p = path.join(dir, e);
      const st = await fs.stat(p);
      if (st.isDirectory()) await walk(p);
      else if (p.endsWith(".ogg")) {
        const tp = transcriptPathFor(p);
        try { await fs.access(tp); } catch { out.push(p); }
      }
    }
  }
  await walk(MEDIA_DIR);
  return out;
}

async function main() {
  if (allMissing) {
    const missing = await findMissing();
    console.log(`${missing.length} audios sin transcribir.`);
    for (const p of missing) {
      try { await processOne(p); }
      catch (e: any) { console.error(`  ❌ ${e.message}`); }
    }
    return;
  }
  if (!inputPath) {
    console.error("Uso: tsx transcribe.ts -i <ruta.ogg> [-l es] [--model whisper-1]\n       tsx transcribe.ts --all-missing");
    process.exit(1);
  }
  await processOne(path.resolve(inputPath));
}

main().catch((e) => { console.error(e?.message ?? e); process.exit(1); });
