# Optional Gmail job-order intake

The default RoleLens stack does not connect to Gmail. To try the inherited email intake workflow with your own test mailbox:

1. Create a Google OAuth client of type **Web application**, enable the Gmail API, configure its consent screen, and add your account as a test user if required.
2. Register the redirect URI `http://localhost:8080/auth/callback` exactly.
3. Put the downloaded client configuration at `backend/storage/credentials.json`. This directory is ignored by Git and excluded from the backend image.
4. Set `GMAIL_ENABLED=true` in the root `.env` and run `docker compose up -d backend`.
5. Open **Integrations → Connect Gmail** and complete Google's consent screen. Only proceed with a mailbox you intend to use for this experiment.
6. Use **Test fetch** to inspect message availability, then **Process latest** to create reviewable drafts. Review fields and duplicate notices before saving a job order; dismiss unwanted drafts.

The client requests `gmail.modify` access because the intake pipeline reads messages/attachments and marks processed messages as read. Processing defaults to `is:unread newer_than:1d`, up to ten messages per run. Message attachments and OAuth tokens are stored under `backend/storage/`, mounted into the backend at runtime. Nothing polls automatically.

**Disconnect** deletes the local token. You can also revoke application access in your Google account. Turn `GMAIL_ENABLED=false` to disable all Gmail and OAuth callback endpoints again.

For native Vite development, use callback `http://localhost:5173/auth/callback`, set matching backend settings, and register it with Google. The API retains both `/auth/callback` and `/api/auth/callback` aliases; the documented callback is the former.

Gmail setup is an optional local experiment. The inherited integration is not a production multi-user OAuth service. Do not expose this unauthenticated demo publicly with a connected mailbox. Free-tier Gemini data terms also apply when email content is sent for live AI extraction.
