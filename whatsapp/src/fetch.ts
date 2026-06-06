import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  proto,
  WAMessage,
  WAMessageKey,
  downloadMediaMessage,
} from "@whiskeysockets/baileys";
import pino from "pino";
import { Boom } from "@hapi/boom";
import path from "path";
import fs from "fs/promises";
import {
  AUTH_DIR,
  INBOX_DIR as DEFAULT_INBOX_DIR,
  CHATS_DIR as DEFAULT_CHATS_DIR,
  MEDIA_DIR as DEFAULT_MEDIA_DIR,
  CONTACTS_FILE as DEFAULT_CONTACTS_FILE,
  STATE_FILE as DEFAULT_STATE_FILE,
  POLICY_FILE,
} from "./paths.js";

const logger = pino({ level: "silent" });

// ---------------------------------------------------------------------------
// CLI arguments
//
// Default (live) mode connects and drains everything the phone has queued for
// this device: live messages (`notify`) plus anything buffered while the device
// was offline (`append`). Instead of a fixed window it listens until the drain
// goes quiet, so a large backlog is never cut off mid-stream.
//
//   --listen <seconds>     hard cap on the listen window (default 300)
//   --quiet <seconds>      stop early after this long with no new message (15)
//   --since <iso|epoch>    only keep messages newer than this (routine compat)
//   --output <dir>         write inbox output under this dir (routine compat)
//
// On-demand history mode pages backwards through a chat we have already seen,
// anchoring on its most recent known message (persisted across runs).
//
//   --history              enable on-demand backfill via fetchMessageHistory
//   --chat <jid|number>    target a single chat; omit to backfill every chat
//                          that has a stored/seen anchor
//   --count <n>            messages to request per chat (default 50)
//
// HARD LIMIT: a linked companion device only receives each message once (live
// or offline-buffered) and gets no history re-sync on reconnect. `fetchMessage-
// History` can only page back from a message the device already knows. A chat
// the device never saw and that has left the server's offline buffer cannot be
// recovered without re-linking (see dump.ts, which clears auth on purpose).
// ---------------------------------------------------------------------------

interface Args {
  history: boolean;
  chat?: string;
  count: number;
  listenSeconds: number;
  quietSeconds: number;
  since?: number; // unix seconds
  output?: string;
}

const MIN_LISTEN_MS = 12_000; // always give the offline drain time to start

function parseArgs(argv: string[]): Args {
  const args: Args = {
    history: false,
    count: 50,
    listenSeconds: parseInt(process.env.LISTEN_SECONDS ?? "300", 10),
    quietSeconds: parseInt(process.env.QUIET_SECONDS ?? "15", 10),
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case "--history":
        args.history = true;
        break;
      case "--chat":
        args.chat = next();
        break;
      case "--count":
        args.count = parseInt(next() ?? "50", 10);
        break;
      case "--listen":
        args.listenSeconds = parseInt(next() ?? "300", 10);
        break;
      case "--quiet":
        args.quietSeconds = parseInt(next() ?? "15", 10);
        break;
      case "--since": {
        const v = next();
        if (v) args.since = parseSince(v);
        break;
      }
      case "--output":
        args.output = next();
        break;
      default:
        if (a.startsWith("--")) console.error(`Aviso: argumento desconocido ${a}`);
    }
  }
  return args;
}

// Accepts ISO-8601, "YYYY-MM-DD HH:mm", or a unix timestamp (s or ms).
// Returns unix seconds, or undefined when unparseable.
function parseSince(v: string): number | undefined {
  const trimmed = v.trim();
  if (/^\d+$/.test(trimmed)) {
    const n = parseInt(trimmed, 10);
    return n > 1e12 ? Math.floor(n / 1000) : n; // ms -> s
  }
  const ms = Date.parse(trimmed);
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

function toNum(v: number | Long | null | undefined): number {
  if (v == null) return 0;
  return typeof v === "number" ? v : Number(v);
}

// Long is only referenced structurally; declare it loosely to avoid a dep.
type Long = { toNumber(): number };

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
    // Prefer a saved/curated contact name over the volatile pushName.
    const name = contacts[m.from] || m.pushName || shortJid(m.from);
    return `**${name}**`;
  }
  const name = contacts[m.chatJid] || contacts[m.from] || m.pushName || shortJid(m.chatJid);
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

async function loadContacts(file: string): Promise<Record<string, string>> {
  try {
    return JSON.parse(await fs.readFile(file, "utf-8"));
  } catch {
    return {};
  }
}

interface Whitelist {
  slugs: Set<string>;
  numbers: Set<string>; // bare phone numbers (digits only, no suffix)
  lids: Set<string>; // full `<id>@lid` jids
}

// Parse the policy whitelist. Identities show up in three backticked forms:
//   `<slug>.md`                 -> file slug
//   `<digits>`                  -> phone number
//   `<digits>@s.whatsapp.net`   -> phone number
//   `<digits>@lid`              -> privacy-mode LID jid
// We keep numbers and LIDs separately so matching can normalize either side.
async function loadWhitelist(): Promise<Whitelist> {
  const slugs = new Set<string>();
  const numbers = new Set<string>();
  const lids = new Set<string>();
  try {
    const content = await fs.readFile(POLICY_FILE, "utf-8");
    const start = content.indexOf("## Whitelist");
    const end = content.indexOf("## Bloqueados");
    const section = start >= 0 && end > start ? content.slice(start, end) : content;
    const tokenRe = /`([^`]+)`/g;
    let m: RegExpExecArray | null;
    while ((m = tokenRe.exec(section)) !== null) {
      const tok = m[1];
      if (/^[a-z0-9-]+\.md$/.test(tok)) {
        slugs.add(tok.replace(/\.md$/, ""));
      } else if (/@lid$/.test(tok)) {
        lids.add(tok);
      } else if (/@s\.whatsapp\.net$/.test(tok)) {
        numbers.add(tok.split("@")[0].split(":")[0]);
      } else if (/^\d{8,}$/.test(tok)) {
        numbers.add(tok);
      }
    }
  } catch {}
  return { slugs, numbers, lids };
}

function jidToNumber(jid: string): string | null {
  if (jid.endsWith("@s.whatsapp.net")) return jid.split("@")[0].split(":")[0];
  return null; // @lid carries an opaque id, not a phone number
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  // Resolve output paths. `--output` redirects inbox writes (routine worktree);
  // auth and policy always come from the live instance via paths.ts.
  const INBOX_DIR = args.output ? path.resolve(args.output) : DEFAULT_INBOX_DIR;
  const CHATS_DIR = args.output ? path.join(INBOX_DIR, "chats") : DEFAULT_CHATS_DIR;
  const MEDIA_DIR = args.output ? path.join(INBOX_DIR, "media") : DEFAULT_MEDIA_DIR;
  const CONTACTS_FILE = args.output ? path.join(INBOX_DIR, "contacts.json") : DEFAULT_CONTACTS_FILE;
  const STATE_FILE = args.output ? path.join(INBOX_DIR, ".last-fetch") : DEFAULT_STATE_FILE;
  // Anchors persist the latest known message per chat so on-demand history can
  // page back through chats seen on previous runs. Kept next to the live inbox
  // (not --output) so it survives ephemeral routine worktrees.
  const ANCHORS_FILE = path.join(DEFAULT_INBOX_DIR, ".anchors.json");

  await fs.mkdir(CHATS_DIR, { recursive: true });
  await fs.mkdir(MEDIA_DIR, { recursive: true });

  const contacts = await loadContacts(CONTACTS_FILE);
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

  // Latest known message per chat, used as the anchor for on-demand history.
  // Seeded from disk so on-demand can page chats seen on earlier runs.
  const anchors = new Map<string, { key: WAMessageKey; ts: number }>();
  try {
    const stored: Record<string, { key: WAMessageKey; ts: number }> =
      JSON.parse(await fs.readFile(ANCHORS_FILE, "utf-8"));
    for (const [jid, a] of Object.entries(stored)) anchors.set(jid, a);
  } catch {}
  let onDemandBatches = 0;
  let lastMsgAt = 0; // wall-clock ms of the most recent captured message

  function resolveName(jid: string): string {
    return contacts[jid] ?? jid;
  }

  // LID/PN matching is async (the mapping store hits the auth keystore), so we
  // memoize per-jid. Returns the bare phone number for a jid when resolvable.
  const numberCache = new Map<string, string | null>();
  async function chatNumber(jid: string): Promise<string | null> {
    if (numberCache.has(jid)) return numberCache.get(jid)!;
    let num = jidToNumber(jid);
    if (num == null && jid.endsWith("@lid")) {
      try {
        const pn = await sock.signalRepository.lidMapping.getPNForLID(jid);
        if (pn) num = pn.split("@")[0].split(":")[0];
      } catch {}
    }
    numberCache.set(jid, num);
    return num;
  }

  // Pre-resolve the LID for each whitelisted phone number, so a chat arriving
  // as `<id>@lid` matches even when the reverse (LID->PN) mapping isn't cached.
  const whitelistLids = new Set<string>(whitelist.lids);
  async function expandWhitelistLids() {
    for (const num of whitelist.numbers) {
      try {
        const lid = await sock.signalRepository.lidMapping.getLIDForPN(`${num}@s.whatsapp.net`);
        if (lid) whitelistLids.add(lid);
      } catch {}
    }
  }

  async function isWhitelisted(jid: string): Promise<boolean> {
    if (whitelistLids.has(jid)) return true;
    const num = await chatNumber(jid);
    if (num && whitelist.numbers.has(num)) return true;
    const slug = slugify(resolveName(jid), jid);
    return whitelist.slugs.has(slug);
  }

  function recordAnchor(raw: WAMessage) {
    const jid = raw.key?.remoteJid;
    if (!jid || !raw.key?.id) return;
    const ts = toNum(raw.messageTimestamp as number | Long | null | undefined);
    const prev = anchors.get(jid);
    if (!prev || ts > prev.ts) anchors.set(jid, { key: raw.key, ts });
  }

  function handleMessage(raw: WAMessage) {
    const jid = raw.key?.remoteJid;
    if (!jid || jid === "status@broadcast") return;

    recordAnchor(raw);

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

    const ts = toNum(raw.messageTimestamp as number | Long | null | undefined);
    if (args.since && ts < args.since) return; // drop messages older than --since

    const isAudio = !!raw.message?.audioMessage;
    const msg: Msg = {
      timestamp: ts,
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
    lastMsgAt = Date.now();
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
    // Each chat carries its most recent message — the anchor for on-demand pulls.
    for (const chat of (data.chats ?? [])) {
      const last = chat.messages?.[0]?.message as WAMessage | undefined;
      if (last?.key?.id && chat.id) {
        const ts = toNum(last.messageTimestamp as number | Long | null | undefined);
        const prev = anchors.get(chat.id);
        if (!prev || ts > prev.ts) anchors.set(chat.id, { key: last.key, ts });
      }
    }
    const isOnDemand = data.syncType === proto.HistorySync.HistorySyncType.ON_DEMAND;
    if (isOnDemand) onDemandBatches++;
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
  await expandWhitelistLids();

  if (args.history) {
    await runHistoryMode(args, sock, anchors, () => onDemandBatches);
  } else {
    // Drain until quiet: keep listening while messages still arrive, stop once
    // the stream goes silent for --quiet seconds, capped at --listen seconds.
    const startedAt = Date.now();
    const maxMs = args.listenSeconds * 1000;
    const quietMs = args.quietSeconds * 1000;
    console.log(`Conectado. Drenando (máx ${args.listenSeconds}s, corte por silencio ${args.quietSeconds}s)...`);
    while (true) {
      await new Promise((r) => setTimeout(r, 1000));
      const elapsed = Date.now() - startedAt;
      if (elapsed >= maxMs) break;
      if (elapsed < MIN_LISTEN_MS) continue; // let the drain start
      const idleFor = lastMsgAt === 0 ? elapsed : Date.now() - lastMsgAt;
      if (idleFor >= quietMs) break;
    }
  }

  // Download audios for whitelisted chats
  let audiosDownloaded = 0;
  let audiosFailed = 0;
  for (const [jid, msgs] of newMessages) {
    if (!(await isWhitelisted(jid))) continue;
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

  // Persist anchors (latest message per chat) for future on-demand paging.
  try {
    await fs.mkdir(path.dirname(ANCHORS_FILE), { recursive: true });
    await fs.writeFile(ANCHORS_FILE, JSON.stringify(Object.fromEntries(anchors), null, 2));
  } catch {}

  // Save fetch state
  const totalMsgs = [...newMessages.values()].reduce((n, msgs) => n + msgs.length, 0);
  await fs.writeFile(STATE_FILE, JSON.stringify({
    timestamp: new Date().toISOString(),
    mode: args.history ? "history" : "live",
    messagesCaptured: totalMsgs,
    chatsUpdated: updatedChats.size,
    newContacts: newContactCount,
    audiosDownloaded,
    audiosFailed,
  }, null, 2));

  const modeLabel = args.history ? "historial on-demand" : "vivo";
  console.log(`[${modeLabel}] ${totalMsgs} mensajes en ${updatedChats.size} chats. ${newContactCount} contactos nuevos. ${audiosDownloaded} audios descargados (whitelist), ${audiosFailed} fallidos.`);

  sock.end(undefined);
  process.exit(0);
}

// On-demand backfill: anchor on each target chat's most recent known message
// and ask the server for `count` messages preceding it. Results arrive async
// via `messaging-history.set` (syncType ON_DEMAND), so we settle, fire the
// requests, then wait for the batches to land.
async function runHistoryMode(
  args: Args,
  sock: ReturnType<typeof makeWASocket>,
  anchors: Map<string, { key: WAMessageKey; ts: number }>,
  onDemandBatches: () => number,
) {
  console.log("Conectado. Asentando anclas (persistidas + en vivo)...");
  // Brief settle: catch any live message that refines an anchor. The on-connect
  // history sync does NOT fire for an established device, so anchors come from
  // the persisted store loaded at startup plus anything that arrives live.
  await new Promise((r) => setTimeout(r, 5000));

  let targets: string[];
  if (args.chat) {
    targets = await resolveChatTargets(args.chat, sock, anchors);
    if (targets.length === 0) {
      console.error(`No tengo ancla para "${args.chat}" — ese chat aún no fue visto en vivo.`);
      console.error(`Las anclas se crean cuando el chat envía/recibe un mensaje estando el monitor conectado.`);
      console.error(`Anclas disponibles (${anchors.size}):`);
      for (const jid of [...anchors.keys()].slice(0, 40)) console.error(`  ${jid}`);
      return;
    }
  } else {
    targets = [...anchors.keys()].filter((j) => j !== "status@broadcast");
  }

  const count = Math.min(args.count, 50); // server caps on-demand queries at 50
  console.log(`Solicitando historial de ${targets.length} chat(s), ${count} msgs c/u...`);
  let requested = 0;
  for (const jid of targets) {
    const a = anchors.get(jid);
    if (!a) {
      console.error(`  sin ancla para ${jid}, omitido`);
      continue;
    }
    try {
      // messageTimestamp is in seconds; Baileys forwards it as-is (see README).
      const sessionId = await sock.fetchMessageHistory(count, a.key, a.ts);
      console.log(`  pedido ${jid} (sesión ${sessionId})`);
      requested++;
    } catch (e: any) {
      console.error(`  fallo al pedir ${jid}: ${e.message ?? e}`);
    }
  }

  if (requested === 0) return;

  // Wait for ON_DEMAND batches, stopping early once they stop arriving.
  const deadline = Date.now() + 45_000;
  let lastSeen = onDemandBatches();
  let quietSince = Date.now();
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 1500));
    const now = onDemandBatches();
    if (now > lastSeen) {
      lastSeen = now;
      quietSince = Date.now();
    } else if (lastSeen > 0 && Date.now() - quietSince > 6000) {
      break; // batches arrived and went quiet
    }
  }
  console.log(`Recibidos ${lastSeen} lote(s) de historial on-demand.`);
}

// Resolve a --chat argument (jid or bare number) to actual chat jids that have
// an anchor. A number can map to either `<num>@s.whatsapp.net` or a LID.
async function resolveChatTargets(
  arg: string,
  sock: ReturnType<typeof makeWASocket>,
  anchors: Map<string, { key: WAMessageKey; ts: number }>,
): Promise<string[]> {
  if (arg.includes("@")) {
    return anchors.has(arg) ? [arg] : [];
  }
  const candidates = new Set<string>();
  const pnJid = `${arg}@s.whatsapp.net`;
  if (anchors.has(pnJid)) candidates.add(pnJid);
  try {
    const lid = await sock.signalRepository.lidMapping.getLIDForPN(pnJid);
    if (lid && anchors.has(lid)) candidates.add(lid);
  } catch {}
  // Fallback: scan anchored LIDs for one whose PN matches the number.
  if (candidates.size === 0) {
    for (const jid of anchors.keys()) {
      if (!jid.endsWith("@lid")) continue;
      try {
        const pn = await sock.signalRepository.lidMapping.getPNForLID(jid);
        if (pn && pn.split("@")[0].split(":")[0] === arg) candidates.add(jid);
      } catch {}
    }
  }
  return [...candidates];
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
