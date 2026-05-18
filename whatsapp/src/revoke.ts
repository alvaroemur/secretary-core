import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from "@whiskeysockets/baileys";
import pino from "pino";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.resolve(__dirname, "../auth");
const logger = pino({ level: "silent" });

const args = process.argv.slice(2);
let jid = "";
let msgId = "";
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--jid") jid = args[++i];
  else if (args[i] === "--id") msgId = args[++i];
}
if (!jid || !msgId) {
  console.error("Uso: tsx revoke.ts --jid <jid> --id <msgId>");
  process.exit(1);
}

async function main() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version, logger,
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    printQRInTerminal: false,
  });
  sock.ev.on("creds.update", saveCreds);
  await new Promise<void>((resolve, reject) => {
    sock.ev.on("connection.update", (u) => {
      if (u.connection === "open") resolve();
      if (u.connection === "close") reject(new Error("conexión cerrada"));
    });
    setTimeout(() => reject(new Error("timeout")), 30000);
  });

  const key = { remoteJid: jid, fromMe: true, id: msgId };
  const result = await sock.sendMessage(jid, { delete: key });
  console.log(JSON.stringify({ ok: true, revoked: msgId, resultId: result?.key?.id ?? null }));
  await sock.end(undefined);
  process.exit(0);
}

main().catch((e) => { console.error("error:", e?.message ?? e); process.exit(1); });
