import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  downloadMediaMessage,
  WAMessage,
} from "@whiskeysockets/baileys";
import pino from "pino";
import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.resolve(__dirname, "../auth");
const OUT_DIR = path.resolve(__dirname, "../media");

const logger = pino({ level: "silent" });

const args = process.argv.slice(2);
let TARGET_JID = "";
let WAIT_SECONDS = 90;
let MAX_AUDIOS = 5;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--jid") TARGET_JID = args[++i];
  else if (args[i] === "--wait") WAIT_SECONDS = parseInt(args[++i], 10);
  else if (args[i] === "--max") MAX_AUDIOS = parseInt(args[++i], 10);
}
if (!TARGET_JID) {
  console.error("Uso: tsx download-media.ts --jid <jid> [--wait 90] [--max 5]");
  process.exit(1);
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version,
    logger,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    printQRInTerminal: false,
    syncFullHistory: true,
    markOnlineOnConnect: false,
  });
  sock.ev.on("creds.update", saveCreds);

  const audios = new Map<string, WAMessage>();

  const collectAudios = (msgs: WAMessage[], src: string) => {
    for (const m of msgs) {
      if (m.key.remoteJid !== TARGET_JID) continue;
      const audio = m.message?.audioMessage;
      if (!audio) continue;
      const id = m.key.id ?? `${m.messageTimestamp}`;
      if (audios.has(id)) continue;
      audios.set(id, m);
      const ts = Number(m.messageTimestamp);
      console.log(
        `[${src}] AUDIO ${id} ts=${new Date(ts * 1000).toISOString()} dur=${audio.seconds}s`
      );
    }
  };

  sock.ev.on("messaging-history.set", ({ messages }) =>
    collectAudios(messages, "history")
  );
  sock.ev.on("messages.upsert", ({ messages }) =>
    collectAudios(messages, "upsert")
  );

  await new Promise<void>((resolve, reject) => {
    sock.ev.on("connection.update", (u) => {
      if (u.connection === "open") resolve();
      if (u.connection === "close") reject(new Error("conexión cerrada"));
    });
    setTimeout(() => reject(new Error("timeout conectando")), 30000);
  });

  console.log(`Conectado. Esperando history sync ${WAIT_SECONDS}s...`);
  await new Promise((r) => setTimeout(r, WAIT_SECONDS * 1000));

  console.log(`\n=== ${audios.size} audios encontrados ===`);
  const sorted = [...audios.values()].sort(
    (a, b) => Number(b.messageTimestamp) - Number(a.messageTimestamp)
  );

  for (const m of sorted.slice(0, MAX_AUDIOS)) {
    const ts = Number(m.messageTimestamp);
    const dateStr = new Date(ts * 1000).toISOString().slice(0, 10);
    const outPath = path.join(OUT_DIR, `${TARGET_JID.split("@")[0]}-${dateStr}-${m.key.id}.ogg`);
    try {
      const buf = await downloadMediaMessage(
        m,
        "buffer",
        {},
        { logger, reuploadRequest: sock.updateMediaMessage }
      );
      await fs.writeFile(outPath, buf as Buffer);
      console.log(`✅ ${outPath} (${(buf as Buffer).length} bytes)`);
    } catch (e: any) {
      console.error(`❌ ${m.key.id} (${new Date(ts * 1000).toISOString()}): ${e.message}`);
    }
  }

  await sock.end(undefined);
  process.exit(0);
}

main().catch((e) => {
  console.error("error:", e?.message ?? e);
  process.exit(1);
});
