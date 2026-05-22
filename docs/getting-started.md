# 👋 Hey — so you want to try this AI assistant thing?

Hey, it's Álvaro! I'm sharing this with you because it's been genuinely useful for me — but I want to be upfront: there are as many solutions as there are smart people in the world, and ultimately using AI is about personalizing it to *your* needs. What works for me might not be your style, and that's totally fine.

That said, if you've heard about "AI agents" but don't really know what they are or how to start — this repo ("repository", basically a folder with code) is a **quick-start kit**. You grab it, point your AI tool at it, and it configures itself to do a bunch of things for you, like reading your email, tracking your meetings, organizing your Drive, and building a personal wiki. 🤖✨

> 🧑‍💻 **Technical user?** Don't keep reading 🫣 hehe. Skip straight to the [README](../README.md) — it has the architecture, the core/instance split, and a copy-paste prompt to get going.

---

## First, a quick "wait, what?" 🤔

You know how ChatGPT works: you type, it replies. It's a conversation. Great for questions, but it can't *do* anything outside that chat window.

There's a newer kind of AI tool — **AI agents** — that can actually do things on your computer. Open files, create folders, connect to your Gmail, run programs. It's like the difference between *talking about* organizing your desk and *having someone actually organize it*. 🪄

**secretary** is a system that uses these agents to be your personal assistant. You set it up once, and then every day it:

- 📧 Reads your email and cleans your inbox
- 💬 Processes your WhatsApp conversations
- 🎙️ Summarizes your meetings
- Organizes your Google Drive
- Builds a private personal wiki with everything it learns

You stay in control — it reports everything it did and asks before taking big actions.

## OK, what do I need? 📋

Just three things:

1. 💻 A computer (Mac, Windows, or Linux)
2. 🛠️ One of the free tools listed below
3. ⏱️ About 30 minutes — the AI does the heavy lifting, you just answer its questions

## Choose your tool 🧰

### Cursor — free, best for beginners ⭐

[Cursor](https://cursor.com) is an app with a built-in AI that can do things on your computer. It has a free tier that's enough to get started.

**Steps:**

1. Go to [cursor.com](https://cursor.com) and download it
2. Install and open it
3. Open the AI chat: press **Cmd+L** (Mac) or **Ctrl+L** (Windows)
4. Paste this message:

> Clone https://github.com/alvaroemur/secretary-core and help me set it up as my personal assistant. Read the README.md first, then walk me through creating my instance, picking channels, and scheduling the routines. Ask me questions as you go.

That's it. The AI takes care of downloading the project, reading it, and walking you through setup step by step. It'll ask you things like "what's your email?" and "which WhatsApp chats do you want to track?" — just answer naturally. 💬

### Windsurf — also free 🏄

[Windsurf](https://windsurf.com) works the same way as Cursor. Download, install, open the AI chat, and paste the same message from above. Pick whichever one you like more.

### Claude Code — paid, but the most powerful 💪

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is what secretary was actually built with. It's a command-line tool (more technical). Requires a Claude Pro or Max subscription.

The big advantage: it supports **scheduled tasks** — the routines run automatically every day without you doing anything. With Cursor/Windsurf, you'd need to trigger them manually or set up external scheduling.

### What about ChatGPT? 🤷

ChatGPT can't access your computer, so it can't set up or run secretary. But you can still read the [routine templates](../routines/) to understand the system and get ideas. If you like what you see, grab one of the tools above to actually run it.

## What does it look like in practice? 🌅

Once everything is set up, your typical day looks like this:

☀️ **You wake up** — secretary already reviewed your email overnight. There's a report waiting on GitHub with a summary: important messages, draft replies it prepared for you, what it archived, follow-ups it suggests. You skim it, tweak a draft or two, send.

🌙 **End of day** — it processed your WhatsApp chats and meetings. New contacts and projects get added to your private wiki automatically. Action items are tracked.

📚 **Over time** — your wiki grows into a personal knowledge base. "Who was that person I met at the conference?" "What did we decide in that meeting?" "When did I last talk to this client?" All searchable, all connected.

## Common questions ❓

**Do I need to know how to code?**
Nope! The AI agent handles all the technical parts. You just tell it about yourself and your preferences. 🙌

**Is my data private?** 🔒
Yes. Everything stays on your computer and in your private GitHub repository. This repo (secretary-core) is just the blueprint — it has zero personal data.

**Can I use it in Spanish / Portuguese / any language?** 🌍
Yes! The engine is in English, but during setup the AI will ask your preference and adapt everything — your policies, wiki, prompts, reports — to your language.

**What if I get stuck?** 🆘
Drop a message in [GitHub Issues](https://github.com/alvaroemur/secretary-core/issues) describing what happened. Include what tool you're using and what you see on screen. Someone will help.

**What if I want to start small?** 🐣
Totally fine. You can activate just email and nothing else. Or just WhatsApp. Add more channels whenever you're ready — the system is modular.
