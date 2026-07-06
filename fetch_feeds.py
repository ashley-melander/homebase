"""
HomeBase feed fetcher.
Runs inside GitHub Actions (see refresh.yml in the homebase-data repo).
Pulls calendar events from ICS feeds (Google / Outlook / Apple) and open
tasks from ClickUp, then writes everything to calendar.json.

All credentials come from environment variables (GitHub Actions secrets):
  GOOGLE_ICS_URL, OUTLOOK_ICS_URL, APPLE_ICS_URL  - ICS feed links (optional)
  CLICKUP_TOKEN                                    - ClickUp personal API token (optional)
  TIMEZONE                                         - e.g. America/Chicago
This file contains no secrets and is safe to be public.
"""
import os, re, json, datetime
from zoneinfo import ZoneInfo

import requests
import icalendar
import recurring_ical_events

TZ = ZoneInfo(os.environ.get("TIMEZONE", "America/Chicago"))
TODAY = datetime.datetime.now(TZ).date()
WINDOW_START = TODAY - datetime.timedelta(days=30)
WINDOW_END = TODAY + datetime.timedelta(days=120)
MAX_SPAN_DAYS = 60  # cap for absurdly long multi-day events


def fetch_ics(url: str, source: str) -> list:
    """Download one ICS feed and expand it into per-day event entries."""
    out = []
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    cal = icalendar.Calendar.from_ical(r.content)
    # recurring_ical_events expands RRULEs (weekly meetings etc.) into
    # concrete occurrences inside our window.
    for ev in recurring_ical_events.of(cal).between(WINDOW_START, WINDOW_END):
        title = str(ev.get("SUMMARY", "Untitled"))
        uid = str(ev.get("UID", ""))
        start = ev.get("DTSTART").dt
        end = ev.get("DTEND").dt if ev.get("DTEND") else None

        if isinstance(start, datetime.datetime):
            # timed event -> convert to the user's timezone
            start = start.astimezone(TZ)
            time = start.strftime("%H:%M")
            end_time = end.astimezone(TZ).strftime("%H:%M") if isinstance(end, datetime.datetime) else ""
            days = [start.date()]
        else:
            # all-day event; DTEND is exclusive per the ICS spec
            time = end_time = ""
            last = end - datetime.timedelta(days=1) if isinstance(end, datetime.date) else start
            last = min(last, start + datetime.timedelta(days=MAX_SPAN_DAYS))
            days, d = [], start
            while d <= last:
                days.append(d)
                d += datetime.timedelta(days=1)

        for d in days:
            if WINDOW_START <= d <= WINDOW_END:
                out.append({
                    "id": f"{source}-{uid}-{d.isoformat()}",
                    "title": title,
                    "date": d.isoformat(),
                    "time": time,
                    "endTime": end_time,
                    "source": source,
                })
    return out


def fetch_clickup(token: str) -> list:
    """Pull open tasks assigned to the token's owner, across all workspaces."""
    tasks = []
    H = {"Authorization": token}
    me = requests.get("https://api.clickup.com/api/v2/user", headers=H, timeout=60).json()["user"]
    teams = requests.get("https://api.clickup.com/api/v2/team", headers=H, timeout=60).json()["teams"]
    for team in teams:
        page = 0
        while True:
            r = requests.get(
                f"https://api.clickup.com/api/v2/team/{team['id']}/task",
                headers=H, timeout=60,
                params={"assignees[]": me["id"], "page": page, "subtasks": "true"},
            ).json()
            batch = r.get("tasks", [])
            for t in batch:
                date = time = ""
                if t.get("due_date"):
                    dt = datetime.datetime.fromtimestamp(int(t["due_date"]) / 1000, tz=TZ)
                    date = dt.date().isoformat()
                    if t.get("due_date_time"):
                        time = dt.strftime("%H:%M")
                tasks.append({
                    "id": "clickup-" + t["id"],
                    "title": t["name"],
                    "date": date,
                    "time": time,
                    "source": "clickup",
                    "url": t.get("url", ""),
                    "list": (t.get("list") or {}).get("name", ""),
                })
            if r.get("last_page", True) or not batch:
                break
            page += 1
    return tasks


def main():
    data = {
        "generated": datetime.datetime.now(TZ).isoformat(),
        "events": [],
        "tasks": [],
    }

    for env_name, source in [
        ("GOOGLE_ICS_URL", "google"),
        ("OUTLOOK_ICS_URL", "outlook"),
        ("APPLE_ICS_URL", "apple"),
    ]:
        # each secret can hold SEVERAL feed links, separated by commas,
        # spaces, or newlines — handy for multiple calendars per service
        urls = [u for u in re.split(r"[\s,]+", os.environ.get(env_name, "").strip()) if u]
        for n, url in enumerate(urls):
            if url.startswith("webcal://"):
                url = "https://" + url[len("webcal://"):]
            try:
                events = fetch_ics(url, source)
                data["events"].extend(events)
                print(f"[{source} #{n+1}] {len(events)} event entries")
            except Exception as e:  # one broken feed shouldn't kill the rest
                print(f"[{source} #{n+1}] FAILED: {e}")

    token = os.environ.get("CLICKUP_TOKEN", "").strip()
    if token:
        try:
            data["tasks"] = fetch_clickup(token)
            print(f"[clickup] {len(data['tasks'])} tasks")
        except Exception as e:
            print(f"[clickup] FAILED: {e}")

    data["events"].sort(key=lambda e: (e["date"], e["time"] or "99:99"))
    data["tasks"].sort(key=lambda t: (t["date"] or "9999", t["time"] or "99:99"))

    with open("calendar.json", "w") as f:
        json.dump(data, f, indent=1)
    print(f"Wrote calendar.json: {len(data['events'])} events, {len(data['tasks'])} tasks")


if __name__ == "__main__":
    main()
