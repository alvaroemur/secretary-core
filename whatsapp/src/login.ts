import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} from "@whiskeysockets/baileys";
import pino from "pino";
import { Boom } from "@hapi/boom";
import QRCode from "qrcode";
import { exec } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import { AUTH_DIR } from "./paths.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const QR_PATH = path.resolve(__dirname, "../qr.png");

const logger = pino({ level: "silent" });

async function login() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  console.log("Versión del protocolo WA:", version.join("."));

  const sock = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    version,
    browser: ["Secretary", "Desktop", "1.0.0"],
    logger,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      await QRCode.toFile(QR_PATH, qr, { scale: 8 });
      console.log("📱 QR guardado — abriendo en Preview. Escanéalo con WhatsApp.");
      exec(`open "${QR_PATH}"`);
    }

    if (connection === "open") {
      console.log("✅ Conectado a WhatsApp como dispositivo vinculado");
      console.log("   Credenciales guardadas en:", AUTH_DIR);
      console.log("\n   Ya puedes cerrar con Ctrl+C. Las credenciales persisten.\n");
    }

    if (connection === "close") {
      const error = lastDisconnect?.error as Boom;
      const statusCode = error?.output?.statusCode;

      if (statusCode === DisconnectReason.loggedOut) {
        console.log("Sesión cerrada por WhatsApp. Ejecuta de nuevo para vincular.");
      } else {
        console.log("Conexión cerrada (código", statusCode + "). Reintentando en 3s...");
        setTimeout(() => login(), 3000);
      }
    }
  });
}

login().catch(console.error);
