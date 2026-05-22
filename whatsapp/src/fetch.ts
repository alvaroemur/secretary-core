import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  proto,
  WAMessage,
  downloadMediaMessage,
} from "@whiskeysockets/baileys";
import pino from "pino";
import { Boom } from "@hapi/boom";
import path from "path";
import fs from "fs/promises";
import {
  AUTH_DIR,
  INBOX_DIR,
  CHATS_DIR,
  MEDIA_DIR,
  CONTACTS_FILE,
  STATE_FILE,
  POLICY_FILE,
} from "./paths.js";

const logger = pino({ level: "silent" });
const LISTEN_SECONDS = parseInt(process.env.LISTEN_SECONDS ?? "120", 10);

interface Msg {
  timestamp: number;
  from: string;
  pushName: string;
  chatJid: string;
  isGroup: boolean;
  fromMe: boolean;
  text: string;
  raw?: WAMessage; // retained for whitelist audios pending download
  isAudio?: boolean;
}

function shortJid(jid: string): string {
  return jid.replace(/@(s\.whatsapp\.net|lid|g\.us)$/, "");
}

function formatSender(m: Msg, contacts: Record<string, string>): string {
  if (m.fromMe) return "**Yo**";
  if (m.isGroup) {
    if (m.from === m.chatJid) return m.pushName ? `**${m.pushName}**` : "**?**";
    const name = m.pushName || contacts[m.from] || shortJid(m.from);
    return `**${name}**`;
  }
  const name = m.pushName || contacts[m.chatJid] || contacts[m.from] || shortJid(m.chatJid);
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
  if (msg.audioMessage) {
    const dur = msg.audioMessage.seconds ?? 0;
    return `[audio:${dur}s]`;
  }
  if (msg.documentMessage) return `[doc: ${msg.documentMessage.fileName ?? "archivo"}]`;
  if (msg.stickerMessage) return "[sticker]";
  if (msg.locationMessage) return "[ubicación]";
  if (msg.contactMessage) return `[contacto: ${msg.contactMessage.displayName}]`;
  if (msg.reactionMessage) return `[reacción: ${msg.reactionMessage.text}]`;
  if (msg.pollCreationMessage) return `[encuesta: ${msg.pollCreationMessage.name}]`;
  return "";
}

function slugify(name: string, jid: string): string {
  const slug = name
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || jid.replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@lid", "");
}

async function loadContacts(): Promise<Record<string, string>> {
  try {
    return JSON.parse(await fs.readFile(CONTACTS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

async function loadWhitelist(): Promise<{ slugs: Set<string>; jids: Set<string> }> {
  const slugs = new Set<string>();
  const jids = new Set<string>();
  try {
    const content = await fs.readFile(POLICY_FILE, "utf-8");
    // Sections: parse from "## Whitelist" until "## Bloqueados"
    const start = content.indexOf("## Whitelist");
    const end = content.indexOf("## Bloqueados");
    const section = start >= 0 && end > start ? content.slice(start, end) : content;
    const slugRe = /`([a-z0-9-]+)\.md`/g;
    let m: RegExpExecArray | null;
    while ((m = slugRe.exec(section)) !== null) slugs.add(m[1]);
    const jidRe = /`(\d{8,})`/g;
    while ((m = jidRe.exec(section)) !== null) jids.add(m[1] + "@s.whatsapp.net");
  } catch {}
  return { slugs, jids };
}

async function main() {
  await fs.mkdir(CHATS_DIR, { recursive: true });
  await fs.mkdir(MEDIA_DIR, { recursive: true });

  const contacts = await loadContacts();
  const whitelist = await loadWhitelist();
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
    version,
    browser: ["Secretary", "Desktop", "1.0.0"],
    syncFullHistory: false,
    logger,
  });

  sock.ev.on("creds.update", saveCreds);

  const newMessages = new Map<string, Msg[]>();
  const updatedChats = new Set<string>();
  let newContactCount = 0;

  function resolveName(jid: string): string {
    return contacts[jid] ?? jid;
  }

  function isWhitelisted(jid: string): boolean {
    if (whitelist.jids.has(jid)) return true;
    const slug = slugify(resolveName(jid), jid);
    return whitelist.slugs.has(slug);
  }

  function handleMessage(raw: WAMessage) {
    const jid = raw.key?.remoteJid;
    if (!jid || jid === "status@broadcast") return;

    const text = extractText(raw.message);
    if (!text) return;

    const from = raw.key.participant ?? (raw as any).participant ?? jid;
    const pushName = raw.pushName ?? "";

    if (pushName && !contacts[from]) {
      contacts[from] = pushName;
      newContactCount++;
    }
    if (pushName && !jid.endsWith("@g.us") && !raw.key.fromMe && !contacts[jid]) {
      contacts[jid] = pushName;
      newContactCount++;
    }

    const isAudio = !!raw.message?.audioMessage;
    const msg: Msg = {
      timestamp: typeof raw.messageTimestamp === "number"
        ? raw.messageTimestamp : Number(raw.messageTimestamp ?? 0),
      from, pushName, chatJid: jid,
      isGroup: jid.endsWith("@g.us"),
      fromMe: !!raw.key.fromMe,
      text,
      isAudio,
      raw: isAudio ? raw : undefined,
    };

    if (!newMessages.has(jid)) newMessages.set(jid, []);
    newMessages.get(jid)!.push(msg);
    updatedChats.add(jid);
  }

  sock.ev.on("messages.upsert", ({ messages, type }) => {
    // 'notify' = mensaje en vivo; 'append' = mensajes que llegaron mientras
    // el socket estaba offline (incluye envíos desde el celular del propio usuario)
    if (type !== "notify" && type !== "append") return;
    for (const raw of messages) handleMessage(raw);
  });

  sock.ev.on("messaging-history.set", (data: any) => {
    for (const c of (data.contacts ?? [])) {
      if (c.id && (c.name || c.notify || c.verifiedName)) {
        const name = c.name || c.notify || c.verifiedName;
        if (!contacts[c.id]) newContactCount++;
        contacts[c.id] = name;
      }
    }
    for (const raw of data.messages) handleMessage(raw);
  });

  const connected = new Promise<void>((resolve, reject) => {
    sock.ev.on("connection.update", (u) => {
      if (u.connection === "open") resolve();
      if (u.connection === "close") {
        const code = (u.lastDisconnect?.error as Boom)?.output?.statusCode;
        if (code === DisconnectReason.loggedOut) {
          reject(new Error("Sesión expirada. Ejecuta npm run login."));
        }
      }
    });
  });

  await connected;
  console.log(`Conectado. Escuchando ${LISTEN_SECONDS}s...`);

  await new Promise((r) => setTimeout(r, LISTEN_SECONDS * 1000));

  // Download audios for whitelisted chats
  let audiosDownloaded = 0;
  let audiosFailed = 0;
  for (const [jid, msgs] of newMessages) {
    if (!isWhitelisted(jid)) continue;
    const slug = slugify(resolveName(jid), jid);
    for (const m of msgs) {
      if (!m.isAudio || !m.raw) continue;
      const d = new Date(m.timestamp * 1000);
      const stamp = d.toISOString().slice(0, 16).replace(/[:T]/g, "-");
      const msgId = m.raw.key?.id ?? `${m.timestamp}`;
      const dirSlug = path.join(MEDIA_DIR, slug);
      await fs.mkdir(dirSlug, { recursive: true });
      const outPath = path.join(dirSlug, `${stamp}-${msgId}.ogg`);
      const relPath = path.relative(INBOX_DIR, outPath);
      try {
        const buf = await downloadMediaMessage(
          m.raw, "buffer", {},
          { logger, reuploadRequest: sock.updateMediaMessage }
        );
        await fs.writeFile(outPath, buf as Buffer);
        const dur = m.raw.message?.audioMessage?.seconds ?? 0;
        m.text = `[audio: ${relPath}, dur=${dur}s]`;
        audiosDownloaded++;
      } catch (e: any) {
        audiosFailed++;
        const dur = m.raw.message?.audioMessage?.seconds ?? 0;
        m.text = `[audio: descarga falló (${e.message ?? e}), dur=${dur}s]`;
      }
      delete m.raw;
    }
  }

  // Append new messages to per-chat files
  const today = new Date().toISOString().slice(0, 10);

  for (const [jid, msgs] of newMessages) {
    const name = resolveName(jid);
    const slug = slugify(name, jid);
    const filepath = path.join(CHATS_DIR, `${slug}.md`);
    const tipo = jid.endsWith("@g.us") ? "grupo" : "chat";

    msgs.sort((a, b) => a.timestamp - b.timestamp);

    let existing = "";
    try {
      existing = await fs.readFile(filepath, "utf-8");
    } catch {}

    function formatLine(m: Msg): string {
      const d = new Date(m.timestamp * 1000);
      const day = d.toISOString().slice(0, 10);
      const time = d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false });
      const sender = formatSender(m, contacts);
      return `- \`${day} ${time}\` ${sender}: ${m.text}\n`;
    }

    if (existing) {
      let append = "\n";
      for (const m of msgs) append += formatLine(m);
      await fs.writeFile(filepath, existing.trimEnd() + append);
    } else {
      let md = `---\nnombre: "${name}"\njid: "${jid}"\ntipo: ${tipo}\nmensajes: ${msgs.length}\nfecha_dump: ${today}\n---\n\n# ${name}\n\n`;
      for (const m of msgs) md += formatLine(m);
      await fs.writeFile(filepath, md);
    }
  }

  // Save updated contacts
  await fs.writeFile(CONTACTS_FILE, JSON.stringify(contacts, null, 2));

  // Save fetch state
  const totalMsgs = [...newMessages.values()].reduce((n, msgs) => n + msgs.length, 0);
  await fs.writeFile(STATE_FILE, JSON.stringify({
    timestamp: new Date().toISOString(),
    messagesCaptured: totalMsgs,
    chatsUpdated: updatedChats.size,
    newContacts: newContactCount,
    audiosDownloaded,
    audiosFailed,
  }, null, 2));

  console.log(`${totalMsgs} mensajes nuevos en ${updatedChats.size} chats. ${newContactCount} contactos nuevos. ${audiosDownloaded} audios descargados (whitelist), ${audiosFailed} fallidos.`);

  sock.end(undefined);
  process.exit(0);
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
