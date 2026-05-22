# Drive Crawler Routine

**What this routine does:** Indexes Google Drive contents gradually (~50 files per run), reads document content selectively within a token budget, generates consolidated memory files (personas, organizations, projects, key documents index), proposes Drive organization improvements, and detects sensitive files. Never moves, renames, or deletes files — only proposes changes for the user to execute.

> Designed for Claude Code scheduled tasks, but the pattern works with any AI coding agent that can read files, run shell commands, and call APIs.

## Prerequisites

- **Git** with push access to the instance repository
- **Google Drive access** via two complementary methods:
  - **Filesystem mount** (e.g., Google Drive for Desktop, rclone mount) — preferred for reading file contents at zero API token cost
  - **Drive API / MCP tool** — required for native Google files (Docs, Sheets, Slides) which don't have readable local files, and for metadata queries (list, search, permissions)
- Environment variables: `$INSTANCE`, `$CORE`, `$DRIVE_MOUNT` (path to mounted Drive, e.g., `~/Google Drive/My Drive`)

## Schedule

Daily (e.g., `0 6 * * *`). Designed for gradual processing — each run indexes ~50 files from where the last run stopped.

---

## Step 0 — Worktree setup

```bash
BRANCH="drive/crawl-$(date +%Y-%m-%d)"
WORKTREE="$INSTANCE/.claude/worktrees/drive-crawl-$$"

cd "$INSTANCE"
git fetch origin main
git worktree add "$WORKTREE" -b "$BRANCH" origin/main
cd "$WORKTREE"
```

## Step 1 — Load context

1. **State** (`$INSTANCE/drive/estado.md`) — High-value folders, excluded folders, last crawl position, statistics.
2. **Processed index** (`$INSTANCE/drive/memory/indice.jsonl`) — One line per indexed file: `{"drive_id": "...", "path": "...", "type": "...", "modified": "...", "indexed_at": "...", "content_read": true/false, "tokens_used": N}`.
3. **Memory files** — `personas.md`, `organizaciones.md`, `proyectos.md`, `documentos-clave.md` from previous runs.
4. **Wiki context** — Known entities for enriching extraction.

## Step 2 — Discover files to process

### 2a. Change detection

Two strategies, used together:

**Strategy A — Modification time scan (for mounted files):**
```bash
# Find files modified since last run
find "$DRIVE_MOUNT" -type f -newer "$WORKTREE/drive/.last_crawl_marker" \
  -not -path "*/Trash/*" \
  -not -path "*/.shortcut-targets-by-id/*" \
  | head -50
```

**Strategy B — API listing (for native Google files and metadata):**
```
List files where modifiedTime > last_run_timestamp
Order by modifiedTime ascending
Page size: 50
```

### 2b. Gradual root crawl

If fewer than 50 files were found via change detection, fill the remaining budget by continuing the breadth-first crawl from the root:

```
Resume from: <last_crawl_position from estado.md>
Process folders in order: high-value first (from estado.md), then alphabetical
Skip: excluded folders (from estado.md)
Budget: 50 - (files already found via change detection)
```

This ensures the entire Drive gets indexed eventually, even if there are no recent changes.

### 2c. Prioritization

Within the budget of ~50 files per run, prioritize:
1. Files in high-value folders (configured in estado.md)
2. Recently modified files (last 7 days)
3. Files not yet indexed at all
4. Files indexed long ago (>30 days) that may have changed

## Step 3 — Classify and read files

For each file in the processing batch:

### 3a. Type-based filtering

| File Type | Action | Method |
|---|---|---|
| **Google Docs** | Read full content | API (export as text) |
| **Google Sheets** | Read sheet names + first 50 rows per sheet | API (export as CSV) |
| **Google Slides** | Read slide text content | API (export as text) |
| **PDF** | Read content (with page limit) | Filesystem mount + PDF reader |
| **Word (.docx)** | Read full content | Filesystem mount |
| **Excel (.xlsx)** | Read sheet names + preview | Filesystem mount |
| **Plain text / Markdown / CSV** | Read full content | Filesystem mount |
| **Images (.jpg, .png)** | Metadata only (filename, folder, date) | No content read |
| **Video (.mp4, .mov)** | Metadata only | No content read |
| **Audio (.mp3, .m4a)** | Metadata only | No content read |
| **Archives (.zip, .rar)** | Metadata only (list contents if possible) | No content read |
| **Code files (.py, .js, .ts)** | Read content if in project folder | Filesystem mount |
| **Other** | Metadata only | — |

### 3b. Token budget

Each run has a token budget (configurable, default: ~200K tokens of content reading). Track tokens consumed:

```
tokens_remaining = TOKEN_BUDGET
for each file:
  estimated_tokens = file_size_bytes / 4  # rough estimate
  if estimated_tokens > tokens_remaining:
    index metadata only, mark content_read: false
    continue
  read content
  tokens_remaining -= actual_tokens_used
```

Large files (>50K tokens) are read partially: first 10K tokens + last 2K tokens, with a note that the middle was skipped.

### 3c. Sensitive file detection

Flag files that appear to contain sensitive data based on:
- **Filename patterns**: `*password*`, `*credential*`, `*secret*`, `*token*`, `*.env`, `*private*key*`
- **Content patterns** (if read): API keys, SSNs, credit card numbers, passwords in plain text
- **File types in unexpected locations**: `.env` files, `.pem` files, key stores

For sensitive files:
- Record **metadata only** (name, path, modified date)
- Do NOT store content in memory files
- Flag in the report: "Sensitive file detected — review recommended"
- Add to a `sensitive-files.md` list with last-seen dates

## Step 4 — Extract entities from content

For files whose content was read:

### 4a. People
- Names mentioned in documents (meeting notes, correspondence, project plans)
- Contact information found in files
- Role/organization associations

### 4b. Organizations
- Companies, NGOs, government agencies mentioned
- Client/partner relationships evident from documents

### 4c. Projects
- Active project folders with recent activity
- Project documentation (proposals, reports, budgets)
- Status indicators (draft, final, archived, etc.)

### 4d. Key documents index
Flag important documents for the user:
- Contracts and legal agreements
- Financial statements and budgets
- Strategic plans and proposals
- Certifications and credentials
- Important correspondence (letters, formal emails saved as docs)

## Step 5 — Generate Drive organization proposals

Analyze the crawled portion of Drive and propose improvements. These are PROPOSALS only — the routine never executes them.

### 5a. Loose files at root
```markdown
## Loose files at Drive root (consider organizing)
- invoice-2025-03.pdf — suggest: move to Finances/2025/
- project-notes.docx — suggest: move to Projects/<name>/
```

### 5b. Duplicates
```markdown
## Potential duplicates
- "Report Final.pdf" (in Projects/) and "Report Final (1).pdf" (in Downloads/)
  — same size, 2 days apart — likely duplicate
```

### 5c. Naming inconsistencies
```markdown
## Naming inconsistencies
- Folder "2025 Projects" uses spaces, but "2024-Projects" uses hyphens
- Mix of English and Spanish folder names in same hierarchy
```

### 5d. Empty or near-empty folders
```markdown
## Empty folders (consider removing)
- Old Project X/Drafts/ — empty, parent folder inactive since 2024
```

**CRITICAL:** The routine NEVER moves, renames, or deletes any file or folder. It only writes proposals to the report. The user decides and acts manually.

## Step 6 — Update memory files

### 6a. Append to consolidated files

- `memory/personas.md` — New people found in documents, with `pendiente_wiki: false` by default
- `memory/organizaciones.md` — New organizations
- `memory/proyectos.md` — Active projects identified from folder structure and recent documents
- `memory/documentos-clave.md` — Index of key documents with path, type, last modified, brief description

### 6b. Update state

In `estado.md`:
- Update "Last crawl" timestamp and position
- Update statistics (total indexed, pending, tokens used this run)
- Refresh "High-value folders" if new interesting folders discovered
- Update "Excluded folders" if new ones should be added
- List any sensitive files detected

### 6c. Update index

Append new entries to `memory/indice.jsonl`:

```json
{"drive_id": "abc123", "path": "/Projects/Acme/proposal.docx", "type": "docx", "size_bytes": 45000, "modified": "2026-05-20T14:30:00Z", "indexed_at": "2026-05-22T06:15:00Z", "content_read": true, "tokens_used": 11250, "entities_found": 3, "is_sensitive": false}
```

## Step 7 — Commit and open PR

```bash
cd "$WORKTREE"
git add drive/
git commit -m "docs(drive): crawl $(date +%Y-%m-%d)"
git push origin "$BRANCH"

gh pr create \
  --title "docs(drive): crawl $(date +%Y-%m-%d)" \
  --body "$(cat <<'REPORT'
# Drive Crawl Report — YYYY-MM-DD

## Processing Summary
- Files scanned: N (M new, K updated)
- Content read: N files (X tokens used of Y budget)
- Metadata only: N files
- Sensitive files detected: N

## Key Documents Found
- [path/to/important-doc.pdf] — [brief description]

## Entities Extracted
- Personas: N new
- Organizations: N new
- Projects: N active

## Organization Proposals
[proposals from Step 5]

## Sensitive Files (review recommended)
- [path] — detected: [pattern that triggered]

## Crawl Progress
- Total Drive files estimated: ~N
- Indexed so far: N (X%)
- Next crawl position: [folder path]

## Excluded folders (configured)
- [list from estado.md]
REPORT
)" \
  --base main \
  --label "routine:drive"
```

## Step 8 — Cleanup

```bash
cd "$INSTANCE"
git worktree remove "$WORKTREE" --force
```

---

## Access methods in detail

### Filesystem mount (preferred for reading)

When Google Drive for Desktop (or rclone) is active, the Drive appears as a local folder. This is ideal because:
- **Zero API tokens** — reading a file is a local filesystem read
- **Fast** — no network latency per file
- **Simple** — standard file I/O, no auth handling

Limitations:
- Native Google files (Docs, Sheets, Slides) appear as `.gdoc`, `.gsheet`, `.gslides` shortcut files — they cannot be read directly
- The mount must be active when the routine runs

### API / MCP tool (required for native files)

Use the Drive API or a Drive MCP tool for:
- Listing files and folders (metadata queries)
- Reading native Google files (export as text/CSV)
- Getting file permissions and sharing info
- Searching by content or metadata

This costs API tokens but is the only way to read native Google files.

### Recommended approach

```
For each file:
  IF file is native Google (Docs/Sheets/Slides):
    → read via API (export)
  ELIF filesystem mount is available AND file exists locally:
    → read via filesystem (zero tokens)
  ELSE:
    → read via API (download)
```

---

## Customization

1. **Drive mount path**: Set `$DRIVE_MOUNT` to wherever your Drive is mounted. Common paths: `~/Google Drive/My Drive` (macOS), `/mnt/gdrive` (Linux with rclone).
2. **Files per run**: The default of ~50 files/day means a Drive with 5,000 files takes ~100 days to fully index. Adjust based on your Drive size and token budget.
3. **Token budget**: Default 200K tokens per run. Increase if you have large documents or decrease if running on a tight budget.
4. **High-value folders**: Seed `estado.md` with your most important folders (work projects, legal documents, financial records). These get crawled first.
5. **Excluded folders**: Add folders that should never be crawled (e.g., backups of other services, media libraries, folders covered by other routines like the Tactiq transcription folder).
6. **Sensitive file patterns**: Add patterns specific to your situation (e.g., `*tax-return*`, `*medical*`, company-specific credential filenames).
7. **File type handling**: Add or remove types from the classification table in Step 3. If you work with specialized file types (CAD, design files, scientific data), add metadata-only handling for them.
8. **Organization proposals**: If you prefer not to receive cleanup suggestions, remove Step 5. If you want more aggressive proposals, lower the thresholds.
9. **PR labels**: Create `routine:drive` label (`gh label create routine:drive --color FBCA04`).
10. **Multiple Drives**: If you have access to multiple Google Drives (personal + shared drives + workspace), configure each as a separate crawl target with its own priority and exclusion list.
11. **Key document criteria**: Customize what counts as a "key document" for your workflow. A lawyer might flag contracts and court filings; an engineer might flag specifications and architecture docs.
12. **Overlap with other routines**: The meetings-processor routine may cover the Tactiq transcription folder. The mail routine may reference Drive links. Exclude folders already covered by other routines to avoid duplicate processing, and cross-reference Drive entity findings with meeting/mail memory files to enrich rather than duplicate.
