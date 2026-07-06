# HomeBase — Project Notes

Personal life dashboard for Ashley (non-programmer). Built July 2026 with Claude.
**If you're an AI assistant reading this: this file is the full system map. Everything below is accurate as of 2026-07-06.**

## What it is

A single-file web app that puts daily/weekly/monthly views, recurring tasks,
checklists, and tagged notes in one place, plus auto-imported calendar events.
Checked-off items gray out with strikethrough — they never disappear (deliberate
design choice, don't change it).

- **Live app:** https://ashley-melander.github.io/homebase/ (also installed on
  Ashley's iPhone home screen via Safari "Add to Home Screen")
- **Timezone:** America/Chicago

## Architecture (two repos)

### 1. `homebase` (public) — the app shell, no personal data
| File | Purpose |
|---|---|
| `index.html` | The entire app: HTML + CSS + JS in one file. Hosted via GitHub Pages (deploy from `main`, root). |
| `fetch_feeds.py` | Feed-fetcher script. Run by the hourly Action in homebase-data (curled at runtime from this repo's raw URL). |
| `digest.py` | Morning-digest builder. Same runtime-curl pattern. |
| `icon.png` | iPhone home-screen icon. |

### 2. `homebase-data` (PRIVATE) — all personal data
| File | Purpose |
|---|---|
| `data.json` | Ashley's items/lists/notes/check-offs. Written by the app via GitHub Contents API. |
| `calendar.json` | Calendar events + (future) ClickUp tasks. Written hourly by the robot. |
| `.github/workflows/refresh.yml` | Hourly (cron `23 * * * *` UTC) feed refresh. |
| `.github/workflows/morning-digest.yml` | Daily digest at `0 14 * * *` UTC (9am CDT / 8am CST — GitHub cron is UTC-only, so it shifts an hour in winter). |
| Actions secrets | `GOOGLE_ICS_URL`, `APPLE_ICS_URL` (holds MULTIPLE comma-separated links), `OUTLOOK_ICS_URL` (empty — see limitations), `CLICKUP_TOKEN` (empty — see limitations). |

## How sync works

- App stores everything in browser `localStorage` (key `homebase-v1`), and
  mirrors it to `data.json` in homebase-data via the GitHub Contents API.
- Auth: a **fine-grained PAT** (name "HomeBase sync", no expiration, scoped to
  homebase-data only, Contents read/write). Pasted once per device into the
  app's "Set up sync" panel; stored in that browser's localStorage (key
  `homebase-sync`), deliberately NOT included in Export files.
- Conflict policy: newest `updatedAt` wins. Push debounced 1.5s after edits;
  pull on load and on tab refocus (throttled 30s).
- `calendar.json` is read-only to the app; the robot owns it.

## The digest email

`morning-digest.yml` builds a markdown summary (events, todos incl. recurring
expansion, overdue) and posts it as a GitHub **issue** (immediately closed to
keep the repo tidy). GitHub's notification system delivers it as email.
Requires "Watching → Email" enabled in github.com/settings/notifications.

## Known limitations & why

- **Outlook (work):** IT disabled calendar publishing. No workaround without IT.
- **ClickUp:** workspace admin disabled personal API tokens (button visible but
  unclickable in avatar → Settings → Apps). If ever enabled: add the token as
  `CLICKUP_TOKEN` secret — the code already supports it end-to-end.
- **Apple Calendar:** uses iCloud public-share links (unencrypted, obscure URL).
  Ashley accepted this trade-off.
- **Push notifications:** not possible from a static site; in-app overdue
  alerts + digest email substitute.
- **Scheduled-workflow auto-disable:** GitHub disables cron workflows after ~60
  days without repo activity. The hourly bot commits keep homebase-data active,
  so this shouldn't trigger — but if feeds mysteriously stop, check the Actions
  tab for a "re-enable" banner.

## Maintenance recipes

- **Update the app:** edit `index.html` locally, upload to homebase repo
  (overwrites), Pages redeploys in ~1 min.
- **Add a calendar:** append its ICS link (comma-separated) to the matching
  secret in homebase-data → Settings → Secrets → Actions.
- **New device:** open the app, Set up sync, paste the PAT (view/regenerate
  under GitHub → Settings → Developer settings → Fine-grained tokens).
- **Backups:** app footer has Export/Import (JSON). Token never included.
- **Change digest time:** edit the cron in `morning-digest.yml` (remember: UTC).
- **Kill switch:** delete the PAT (revokes all device sync); delete the repos
  (removes everything).

## Design conventions

- Categories: work 💼 blue, home 🏠 green, health 🌸 pink, errands 🛒 orange,
  projects 🎨 purple. Feed sources have their own colors (Google blue, Apple
  gray, Outlook light blue, ClickUp purple).
- Ashley's preferences: casual tone, explain the how/why, keep things simple,
  checked items must stay visible.
