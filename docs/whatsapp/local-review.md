# Local WhatsApp review

The CLI reads macOS WhatsApp's Core Data SQLite database using a read-only transaction. No account login or message-send integration is needed. Read access to the database and media folder, the private instance, the configured core and the isolated transcription executable must be granted to the actual scheduled runtime. Permissions in an interactive terminal do not prove scheduled access. Keep the existing routine executor; never add a parallel schedule as a fallback.

Configure `paths.whatsapp.review_config` in the private `.secretary.yml`. That path points to a private YAML with `database`, `media_root`, `chats` (exact `jid`, `slug`, `name`, evidence-backed `active_commitments`), and `transcription` (`default`, `fallback`, `providers`). Unknown identities belong in `unresolved_contacts`.

```yaml
version: 1
database: /path/to/ChatStorage.sqlite
media_root: /path/to/Message
chats: []
transcription:
  default: local
  fallback: null
  providers:
    local:
      kind: mlx
      python: /path/to/isolated-env/bin/python
      model: mlx-community/whisper-large-v3-turbo
    api:
      kind: openai-transcriptions
      base_url: https://api.openai.com/v1
      model: whisper-1
      key_env: OPENAI_API_KEY
```

Install optional dependencies in an isolated environment. On Apple Silicon, `uv pip install mlx-whisper cryptography pyyaml` installs the transcription components; `ffmpeg` is also required. Download the selected model once. Test audio quality and processing time before unattended operation. The default never changes provider on failure. Select an API with `transcribe --provider <configured-name>` only when authorized. Configured providers must use a supported adapter, not merely an OpenAI-compatible text endpoint.

Shared ignored `inbox/local-review.sqlite` contains message revision receipts and hashed audio transcript caches. Versioned summaries and `memory/reviews` are private-instance artifacts. Keep pending worktrees until delivery, and ensure ignored inbox files are not staged. Never put actual messages, JIDs, model keys or private paths in the core. All tests use synthetic data.

`probe` reports readability and latest captured message but leaves account synchronization unknown. `collect` never acknowledges review. `record` acknowledges only reviewed IDs with eligible audio transcripts. Missing transcripts prevent receipts; failed messages can be excluded while valid evidence is delivered. Authenticated CDN downloads can fail when media is expired; report the gap rather than claiming completion. WhatsApp's native app can fetch media separately, but this CLI never mutates its database or sends reupload requests.

See `playbooks/whatsapp-review/procedure.md` for integration, history limits, delivery and daily/on-demand coordination. Advanced meeting diarization is a separate workstream.
