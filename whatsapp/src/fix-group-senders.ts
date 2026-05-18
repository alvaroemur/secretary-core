import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHATS_DIR = path.resolve(__dirname, "../inbox/chats");

async function main() {
  const files = await fs.readdir(CHATS_DIR);
  let fixed = 0;
  let totalReplacements = 0;

  for (const file of files) {
    if (!file.endsWith(".md")) continue;
    const fp = path.join(CHATS_DIR, file);
    const content = await fs.readFile(fp, "utf-8");

    const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (!fmMatch) continue;
    const fm = fmMatch[1];
    const tipoMatch = fm.match(/tipo:\s*(\S+)/);
    const nombreMatch = fm.match(/nombre:\s*"([^"]+)"/);
    if (!tipoMatch || !nombreMatch) continue;
    if (tipoMatch[1] !== "grupo") continue;

    const nombre = nombreMatch[1];
    // Escape regex special chars
    const esc = nombre.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(`(\\- \`[^\`]+\` )\\*\\*${esc}\\*\\*:`, "g");
    let count = 0;
    const updated = content.replace(re, (_m, prefix) => {
      count++;
      return `${prefix}**?**:`;
    });

    if (count > 0) {
      await fs.writeFile(fp, updated);
      fixed++;
      totalReplacements += count;
    }
  }

  console.log(`Fixed ${fixed} group files, ${totalReplacements} sender replacements`);
}

main().catch(console.error);
