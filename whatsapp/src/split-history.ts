import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const INBOX_DIR = path.resolve(__dirname, "../inbox");
const HISTORY_FILE = path.join(INBOX_DIR, "history-2026-05-08.md");
const CONTACTS_FILE = path.join(INBOX_DIR, "contacts.json");
const CHATS_DIR = path.join(INBOX_DIR, "chats");

function slugify(name: string, jid: string): string {
  const slug = name
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || jid.replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@lid", "");
}

async function main() {
  const raw = await fs.readFile(HISTORY_FILE, "utf-8");
  const contacts: Record<string, string> = JSON.parse(await fs.readFile(CONTACTS_FILE, "utf-8"));
  await fs.mkdir(CHATS_DIR, { recursive: true });

  const lines = raw.split("\n");
  const today = new Date().toISOString().slice(0, 10);

  let currentName = "";
  let currentJid = "";
  let currentLines: string[] = [];
  let chatCount = 0;
  let msgCount = 0;

  async function flushChat() {
    if (!currentName || currentLines.length === 0) return;

    const isGroup = currentJid.endsWith("@g.us");
    const tipo = isGroup ? "grupo" : currentJid.endsWith("@lid") ? "lid" : "chat";
    const slug = slugify(currentName, currentJid);

    let md = `---\nnombre: "${currentName}"\njid: "${currentJid}"\ntipo: ${tipo}\nmensajes: ${currentLines.length}\nfecha_dump: ${today}\n---\n\n`;
    md += `# ${currentName}\n\n`;
    md += currentLines.join("\n") + "\n";

    await fs.writeFile(path.join(CHATS_DIR, `${slug}.md`), md);
    chatCount++;
    msgCount += currentLines.length;
  }

  // Try to resolve JID header to a name using contacts.json
  function resolveName(header: string): { name: string; jid: string } {
    // If header is a JID (number@...), look up in contacts
    if (header.match(/^\d+@(s\.whatsapp\.net|lid)$/) || header.match(/^\d+@g\.us$/)) {
      const name = contacts[header];
      return { name: name || header, jid: header };
    }
    // Header is already a name — find its JID in contacts (reverse lookup)
    const jidEntry = Object.entries(contacts).find(([_, n]) => n === header);
    return { name: header, jid: jidEntry?.[0] ?? "" };
  }

  for (const line of lines) {
    const headerMatch = line.match(/^## (.+)$/);
    if (headerMatch) {
      await flushChat();
      const { name, jid } = resolveName(headerMatch[1]);
      currentName = name;
      currentJid = jid;
      currentLines = [];
      continue;
    }

    if (line.startsWith("- `")) {
      currentLines.push(line);
    }
  }
  await flushChat();

  console.log(`${chatCount} chats escritos en inbox/chats/ (${msgCount} mensajes)`);
}

main().catch(console.error);
