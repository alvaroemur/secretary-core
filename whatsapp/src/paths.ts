// Resolución centralizada de paths para los scripts del módulo whatsapp.
//
// Convención (ver `.secretary.yml` de cada instancia):
//   - El engine vive en secretary-core/whatsapp/src/ (este archivo).
//   - Los datos (auth, inbox, politica, ...) viven en la instancia,
//     bajo `whatsapp/` relativo a la raíz de la instancia.
//   - La instancia se identifica con la env var `SECRETARY_INSTANCE`,
//     apuntando a su raíz (ej. `~/my-secretary`).
//
// Si la env var no está seteada, fallback a paths relativos al script
// (comportamiento legacy: data co-ubicada con el código). Útil para
// repos standalone y para retro-compatibilidad con setups antiguos.

import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const DATA_ROOT = process.env.SECRETARY_INSTANCE
  ? path.resolve(
      process.env.SECRETARY_INSTANCE.replace(/^~/, process.env.HOME ?? "~"),
      "whatsapp"
    )
  : path.resolve(__dirname, "..");

export const AUTH_DIR = path.join(DATA_ROOT, "auth");
export const INBOX_DIR = path.join(DATA_ROOT, "inbox");
export const CHATS_DIR = path.join(INBOX_DIR, "chats");
export const MEDIA_DIR = path.join(INBOX_DIR, "media");
export const CONTACTS_FILE = path.join(INBOX_DIR, "contacts.json");
export const STATE_FILE = path.join(INBOX_DIR, ".last-fetch");
export const POLICY_FILE = path.join(DATA_ROOT, "politica.md");
