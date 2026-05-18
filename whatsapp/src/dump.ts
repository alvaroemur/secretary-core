import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  proto,
} from "@whiskeysockets/baileys";
import pino from "pino";
import { Boom } from "@hapi/boom";
import QRCode from "qrcode";
import { exec } from "child_process";
import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.resolve(__dirname, "../auth");
const INBOX_DIR = path.resolve(__dirname, "../inbox");
const QR_PATH = path.resolve(__dirname, "../qr.png");

interface Msg {
  timestamp: number;
  from: string;
  pushName: string;
  chatJid: string;
  isGroup: boolean;
  fromMe: boolean;
  text: string;
}

function shortJid(jid: string): string {
  return jid.replace(/@(s\.whatsapp\.net|lid|g\.us)$/, "");
}

function formatSender(m: Msg, contactNames: Map<string, { pushName: string; count: number }>): string {
  if (m.fromMe) return "**Yo**";
  if (m.isGroup) {
    // If participant unknown (history sync gap), don't fall back to group-jid lookup (it returns the group name)
    if (m.from === m.chatJid) return m.pushName ? `**${m.pushName}**` : "**?**";
    const name = m.pushName || contactNames.get(m.from)?.pushName || shortJid(m.from);
    return `**${name}**`;
  }
  // 1-on-1 (no fromMe)
  const name = m.pushName || contactNames.get(m.chatJid)?.pushName || contactNames.get(m.from)?.pushName || shortJid(m.chatJid);
  return `**${name}**`;
}

function extractText(msg: proto.IMessage | null | undefined): string {
  if (!msg) return "";
  if (msg.conversation) return msg.conversation;
  if (msg.extendedTextMessage?.text) return msg.extendedTextMessage.text;
  if (msg.imageMessage?.caption) return `[imagen] ${msg.imageMessage.caption}`;
  if (msg.imageMessage) return "[imagen]";
  if (msg.videoMessage?.caption) return `[video] ${msg.videoMessage.caption}`;
  if (msg.videoMessage) return "[video]";
  if (msg.audioMessage) return "[audio]";
  if (msg.documentMessage) return `[doc: ${msg.documentMessage.fileName ?? "archivo"}]`;
  if (msg.stickerMessage) return "[sticker]";
  if (msg.locationMessage) return "[ubicación]";
  if (msg.contactMessage) return `[contacto: ${msg.contactMessage.displayName}]`;
  if (msg.reactionMessage) return `[reacción: ${msg.reactionMessage.text}]`;
  if (msg.pollCreationMessage) return `[encuesta: ${msg.pollCreationMessage.name}]`;
  return "";
}

const chatNames = new Map<string, string>();
const contactNames = new Map<string, { pushName: string; count: number }>();
const allMsgs: Msg[] = [];
let chunks = 0;
let lastSaveCount = 0;

function trackContact(jid: string, pushName: string) {
  if (!pushName || !jid) return;
  const normalized = jid.replace("@s.whatsapp.net", "").replace("@lid", "");
  const existing = contactNames.get(jid);
  if (!existing || pushName.length > existing.pushName.length) {
    contactNames.set(jid, { pushName, count: (existing?.count ?? 0) + 1 });
  } else {
    existing.count++;
  }
}

function handleHistory(chats: any[], messages: any[], contacts?: any[]) {
  chunks++;
  for (const c of chats) {
    if (c.id && c.name) chatNames.set(c.id, c.name);
  }
  if (contacts) {
    for (const c of contacts) {
      if (c.id && (c.name || c.notify || c.verifiedName)) {
        const name = c.name || c.notify || c.verifiedName;
        trackContact(c.id, name);
      }
    }
  }
  for (const raw of messages) {
    const jid = raw.key?.remoteJid;
    if (!jid || jid === "status@broadcast") continue;
    const text = extractText(raw.message);
    if (!text) continue;
    const from = raw.key.participant ?? raw.participant ?? jid;
    const pushName = raw.pushName ?? "";
    trackContact(from, pushName);
    // For 1-on-1 chats, also track the chat JID itself
    if (!jid.endsWith("@g.us") && !raw.key.fromMe && pushName) {
      trackContact(jid, pushName);
    }
    allMsgs.push({
      timestamp: typeof raw.messageTimestamp === "number"
        ? raw.messageTimestamp : Number(raw.messageTimestamp ?? 0),
      from, pushName, chatJid: jid,
      isGroup: jid.endsWith("@g.us"),
      fromMe: !!raw.key.fromMe,
      text,
    });
  }
  console.log(`  [sync ${chunks}] +${messages.length} msgs, total: ${allMsgs.length}`);
}

function resolveName(jid: string): string {
  return chatNames.get(jid) ?? contactNames.get(jid)?.pushName ?? jid;
}

async function saveResults() {
  if (allMsgs.length === 0 || allMsgs.length === lastSaveCount) return;
  lastSaveCount = allMsgs.length;

  await fs.mkdir(INBOX_DIR, { recursive: true });

  // Save contacts.json
  const contactsObj: Record<string, string> = {};
  for (const [jid, { pushName }] of contactNames) {
    contactsObj[jid] = pushName;
  }
  await fs.writeFile(path.join(INBOX_DIR, "contacts.json"), JSON.stringify(contactsObj, null, 2));

  // Save chat list with resolved names
  const chatListPath = path.join(INBOX_DIR, "chats.md");
  let chatMd = "# Chats de WhatsApp\n\n";
  const allJids = new Set([...chatNames.keys(), ...contactNames.keys()]);
  const entries = [...allJids].map((jid) => [jid, resolveName(jid)] as const);
  const sorted = entries.sort((a, b) => a[1].localeCompare(b[1]));
  for (const [jid, name] of sorted) {
    const tipo = jid.endsWith("@g.us") ? "grupo" : jid.endsWith("@lid") ? "lid" : "chat";
    chatMd += `- [${tipo}] **${name}** — \`${jid}\`\n`;
  }
  await fs.writeFile(chatListPath, chatMd);

  const byChat = new Map<string, Msg[]>();
  for (const m of allMsgs) {
    if (!byChat.has(m.chatJid)) byChat.set(m.chatJid, []);
    byChat.get(m.chatJid)!.push(m);
  }

  // Save one file per chat
  const chatsDir = path.join(INBOX_DIR, "chats");
  await fs.mkdir(chatsDir, { recursive: true });

  const today = new Date().toISOString().slice(0, 10);

  for (const [jid, msgs] of byChat) {
    const name = resolveName(jid);
    msgs.sort((a, b) => a.timestamp - b.timestamp);

    const slug = name
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      || jid.replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@lid", "");

    const tipo = jid.endsWith("@g.us") ? "grupo" : "chat";
    let md = `---\nnombre: "${name}"\njid: "${jid}"\ntipo: ${tipo}\nmensajes: ${msgs.length}\nfecha_dump: ${today}\n---\n\n`;
    md += `# ${name}\n\n`;

    for (const m of msgs) {
      const d = new Date(m.timestamp * 1000);
      const day = d.toISOString().slice(0, 10);
      const time = d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false });
      const sender = formatSender(m, contactNames);
      md += `- \`${day} ${time}\` ${sender}: ${m.text}\n`;
    }

    await fs.writeFile(path.join(chatsDir, `${slug}.md`), md);
  }

  console.log(`  💾 Guardado: ${allMsgs.length} msgs → ${byChat.size} archivos en inbox/chats/, ${contactNames.size} contactos`);
}

async function main() {
  await fs.mkdir(INBOX_DIR, { recursive: true });

  // Clear auth to force re-link
  try {
    const files = await fs.readdir(AUTH_DIR);
    for (const f of files) await fs.rm(path.join(AUTH_DIR, f), { recursive: true });
  } catch {}
  await fs.mkdir(AUTH_DIR, { recursive: true });
  console.log("Auth limpiado. Necesitas escanear QR.\n");

  // Save on Ctrl+C
  process.on("SIGINT", async () => {
    console.log("\n\nInterrumpido. Guardando lo capturado...");
    await saveResults();
    process.exit(0);
  });

  // Auto-save every 30 seconds
  const saveInterval = setInterval(() => saveResults(), 30_000);

  const { version } = await fetchLatestBaileysVersion();
  let connected = false;
  let noNewDataCount = 0;

  async function createSocket() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const logger = pino({ level: "silent" });

    const sock = makeWASocket({
      auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
      version,
      browser: ["Secretary", "Desktop", "1.0.0"],
      syncFullHistory: true,
      logger,
    });

    sock.ev.on("creds.update", saveCreds);
    sock.ev.on("messaging-history.set", (data: any) => {
      handleHistory(data.chats, data.messages, data.contacts);
      noNewDataCount = 0;
    });

    sock.ev.on("connection.update", async (u) => {
      if (u.qr) {
        await QRCode.toFile(QR_PATH, u.qr, { scale: 8 });
        console.log("📱 QR listo — abriendo imagen. Escanéalo.");
        exec(`open "${QR_PATH}"`);
      }

      if (u.connection === "open") {
        if (!connected) {
          connected = true;
          console.log("✅ Conectado. Capturando historial (Ctrl+C para terminar)...");
        } else {
          console.log("  ↻ Reconectado.");
        }
      }

      if (u.connection === "close") {
        const code = (u.lastDisconnect?.error as Boom)?.output?.statusCode;

        if (code === DisconnectReason.loggedOut) {
          console.log("Sesión rechazada. Guardando...");
          await saveResults();
          clearInterval(saveInterval);
          process.exit(1);
        }

        noNewDataCount++;

        // If 5+ reconnects with no new data, sync is probably done
        if (noNewDataCount >= 5 && allMsgs.length > 0) {
          console.log("\nSync parece completo (sin datos nuevos en últimas reconexiones).");
          await saveResults();
          clearInterval(saveInterval);
          process.exit(0);
        }

        await new Promise((r) => setTimeout(r, 3000));
        createSocket();
      }
    });
  }

  await createSocket();
}

main().catch(console.error);
