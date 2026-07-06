"""
HomeBase morning digest.
Runs inside GitHub Actions (see morning-digest.yml in homebase-data).
Reads calendar.json + data.json from the repo checkout and writes
digest.md + title.txt, which the workflow turns into a GitHub issue
(GitHub then emails the notification).
No secrets used; safe to be public.
"""
import os, json, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TIMEZONE", "America/Chicago"))
TODAY = datetime.datetime.now(TZ).date()
DS = TODAY.isoformat()

CATS = {
    "work":     ("💼", "Work"),
    "home":     ("🏠", "House/Home"),
    "health":   ("🌸", "Personal/Health"),
    "errands":  ("🛒", "Errands/Shopping"),
    "projects": ("🎨", "Personal Projects"),
}
SRC = {"google": "Google", "outlook": "Outlook", "apple": "Apple", "clickup": "ClickUp"}


def load(path, fallback):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return fallback


def occurs(item, day):
    """Same recurrence rules as the HomeBase app."""
    if not item.get("date"):
        return False
    base = datetime.date.fromisoformat(item["date"])
    recur = item.get("recur") or "none"
    if recur == "none":
        return item["date"] == day.isoformat()
    if day < base:
        return False
    diff = (day - base).days
    if recur == "daily":    return True
    if recur == "weekdays": return day.weekday() < 5
    if recur == "weekly":   return day.weekday() == base.weekday()
    if recur == "biweekly": return day.weekday() == base.weekday() and diff % 14 == 0
    if recur == "monthly":  return day.day == base.day
    return False


def main():
    cal = load("calendar.json", {"events": [], "tasks": []})
    data = load("data.json", {"items": [], "extDone": {}})
    ext_done = data.get("extDone") or {}

    events = sorted([e for e in cal.get("events", []) if e["date"] == DS],
                    key=lambda e: e.get("time") or "99:99")
    ctasks = [t for t in cal.get("tasks", []) if t.get("date") == DS]
    items = sorted([i for i in data.get("items", []) if occurs(i, TODAY)],
                   key=lambda i: i.get("time") or "99:99")
    overdue = sorted(
        [i for i in data.get("items", [])
         if (i.get("recur") or "none") == "none" and i.get("date") and i["date"] < DS
         and not (i.get("completions") or {}).get(i["date"])],
        key=lambda i: i["date"])
    ext_overdue = [t for t in cal.get("tasks", [])
                   if t.get("date") and t["date"] < DS and not ext_done.get(t["id"])]

    lines = []
    if not (events or ctasks or items or overdue or ext_overdue):
        lines.append("Nothing scheduled today. Enjoy the quiet! 🎉")
    else:
        if events:
            lines.append("### 📅 Events")
            for e in events:
                when = f"**{e['time']}**" + (f"–{e['endTime']}" if e.get("endTime") else "") if e.get("time") else "_all day_"
                lines.append(f"- {when} · {e['title']} ({SRC.get(e['source'], e['source'])})")
            lines.append("")
        if items or ctasks:
            lines.append("### ✅ To do today")
            for i in items:
                icon, cname = CATS.get(i.get("cat"), ("•", ""))
                done = (i.get("completions") or {}).get(DS)
                text = f"~~{i['title']}~~" if done else i["title"]
                t = f"**{i['time']}** · " if i.get("time") else ""
                lines.append(f"- {icon} {t}{text}" + (f" _({cname})_" if cname else ""))
            for t in ctasks:
                done = ext_done.get(t["id"])
                text = f"~~{t['title']}~~" if done else t["title"]
                lines.append(f"- ✅ {text} _(ClickUp{(' · ' + t['list']) if t.get('list') else ''})_")
            lines.append("")
        if overdue or ext_overdue:
            lines.append("### ⚠️ Overdue")
            for i in overdue:
                icon, _ = CATS.get(i.get("cat"), ("•", ""))
                lines.append(f"- {icon} {i['title']} _(was due {i['date']})_")
            for t in ext_overdue:
                lines.append(f"- ✅ {t['title']} _(ClickUp, was due {t['date']})_")
            lines.append("")

    lines.append("---")
    lines.append("_Open [HomeBase](https://ashley-melander.github.io/homebase/) · digest generated automatically_")

    with open("digest.md", "w") as f:
        f.write("\n".join(lines))
    with open("title.txt", "w") as f:
        f.write("☀️ Your day — " + TODAY.strftime("%A, %B %d").replace(" 0", " "))
    print("digest ready:", len(events), "events,", len(items) + len(ctasks), "todos,",
          len(overdue) + len(ext_overdue), "overdue")


if __name__ == "__main__":
    main()
