# Getting started (from zero)

If you've only used ChatGPT, Claude.ai, or similar chatbots and have never heard of "AI coding agents" — this page is for you.

## What's different here?

Regular chatbots (ChatGPT, Claude.ai) are like texting a smart friend — you ask questions, they answer. That's it.

**AI coding agents** are different: they can actually *do things* on your computer. They read files, run commands, create folders, connect to your email, and work autonomously. Think of it as giving the AI hands, not just a mouth.

**secretary** uses this to build a personal assistant that processes your email, chats, meetings, and files — automatically, every day, while you sleep.

## What you need

1. A computer (Mac, Windows, or Linux)
2. A free account on one of the tools below
3. ~30 minutes for initial setup (the AI walks you through it)

## Pick your tool (free options)

### Option A — Cursor (recommended for beginners)

[Cursor](https://cursor.com) is a code editor with a built-in AI agent. It has a free tier.

1. Download Cursor from [cursor.com](https://cursor.com)
2. Install and open it
3. Open a terminal inside Cursor (menu: Terminal → New Terminal)
4. Clone the repo:
   ```
   git clone https://github.com/alvaroemur/secretary-core.git
   cd secretary-core
   ```
5. Open the AI chat panel (Cmd+L on Mac, Ctrl+L on Windows)
6. Paste the setup prompt from the [README](../README.md#quick-start--paste-this-into-your-ai-coding-agent)

The AI will read the repo, ask you questions about your setup, and configure everything step by step.

### Option B — Claude Code (most powerful)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is Anthropic's CLI agent. It's what secretary was built with. Requires a paid plan (Pro, Max, or API).

1. Install: `npm install -g @anthropic-ai/claude-code`
2. Run: `claude` and authenticate
3. Clone and enter the repo:
   ```
   git clone https://github.com/alvaroemur/secretary-core.git
   cd secretary-core
   ```
4. Paste the setup prompt from the [README](../README.md#quick-start--paste-this-into-your-ai-coding-agent)

Claude Code is the only tool that supports **scheduled tasks** (routines that run automatically every day). The others require manual runs or external scheduling.

### Option C — Windsurf

[Windsurf](https://windsurf.com) is another AI-powered editor with a free tier. Same flow as Cursor: install, open terminal, clone repo, paste prompt into the AI chat.

### Option D — ChatGPT (limited)

If you only have ChatGPT, you can still read the routine templates and adapt the ideas manually. But ChatGPT can't run commands on your computer or access your files, so it can't set up or run secretary automatically. Consider it a starting point to understand the system before moving to one of the tools above.

## What happens after setup?

Once configured, your AI assistant will:

- **Every morning**: review your email, create draft replies, clean your inbox, and open a report you can read on GitHub
- **Every evening**: process your WhatsApp chats, meeting transcriptions, and Drive files
- **Every night**: consolidate everything into your personal wiki — a private, searchable knowledge base about your contacts, projects, and topics

You review the reports as Pull Requests on GitHub (the AI will explain this during setup). You stay in control — nothing is sent or deleted without your approval.

## FAQ

**Is my data safe?**
Your data stays on your computer and in your private GitHub repository. The AI processes it locally. secretary-core (this repo) is just the engine — it contains no personal data.

**Do I need to know how to code?**
No. The AI agent handles the technical setup. You just answer questions about your preferences (which email to process, which WhatsApp chats matter, what language you prefer).

**What if I get stuck?**
Open an issue on [GitHub](https://github.com/alvaroemur/secretary-core/issues) describing where you got stuck. Include what tool you're using and what error you see.

**Can I use this in Spanish / Portuguese / other languages?**
Yes. The engine is in English but your instance (policies, wiki, routine prompts) can be in any language. Tell the AI your preference during setup.
