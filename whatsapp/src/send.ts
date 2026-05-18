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
let text = "";
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--jid") jid = args[++i];
  else if (args[i] === "--text") text = args[++i];
}
if (!jid || !text) {
  console.error("Uso: tsx send.ts --jid <jid> --text <mensaje>");
  process.exit(1);
}

async function main() {
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
  });
  sock.ev.on("creds.update", saveCreds);

  await new Promise<void>((resolve, reject) => {
    sock.ev.on("connection.update", (u) => {
      if (u.connection === "open") resolve();
      if (u.connection === "close") reject(new Error("conexión cerrada antes de abrir"));
    });
    setTimeout(() => reject(new Error("timeout esperando conexión")), 30000);
  });

  const result = await sock.sendMessage(jid, { text });
  console.log(JSON.stringify({ ok: true, jid, msgId: result?.key?.id ?? null }));
  await sock.end(undefined);
  process.exit(0);
}

main().catch((e) => {
  console.error("error:", e?.message ?? e);
  process.exit(1);
});
