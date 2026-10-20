"""Field Radar — your free daily intelligence briefing.

    python radar.py              fetch new items, rebuild dashboard, notify
    python radar.py --open       ...and open the dashboard in your browser
    python radar.py --offline    rebuild the dashboard from saved items only
    python radar.py --no-notify  skip the Windows pop-up
"""
import argparse
import json
import sys
import tomllib
import traceback
import webbrowser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fieldradar import dashboard, fetch, notify, score, store, summarize  # noqa: E402
from fieldradar.textutil import normalize_title  # noqa: E402

DATA = HERE / "data"
DASHBOARD = HERE / "dashboard.html"
LOG = DATA / "last_run.log"


def load_toml(name):
    with open(HERE / name, "rb") as f:
        return tomllib.load(f)


def log(lines):
    text = "\n".join(lines)
    print(text)
    LOG.write_text(text + "\n", encoding="utf-8")


def too_old(item, settings, now):
    """Some feeds include years-old posts; ignore anything outside the window."""
    if not item.get("published"):
        return False
    is_opp = item["kind"] in ("phd", "cfp")
    days = int(settings.get("opportunity_days", 60)) if is_opp else int(settings.get("days_back", 14))
    return (now - datetime.fromisoformat(item["published"])).days > days


def seconds(duration):
    """'2:16:13' → 8173; '' → 0."""
    try:
        total = 0
        for part in (duration or "").split(":"):
            total = total * 60 + int(part)
        return total
    except ValueError:
        return 0


def pick_media(items, settings):
    """Daily limits for the video tabs: each day keeps its best N shorts and N long-form
    items (max a few per channel), so the tabs end instead of scrolling forever."""
    tz = timedelta(hours=float(settings.get("timezone_hours", 5.5)))
    limits = {"shorts": int(settings.get("shorts_per_day", 20)),
              "longform": int(settings.get("longform_per_day", 10))}
    per_channel = int(settings.get("media_per_channel", 4))
    used, per_chan, out = Counter(), Counter(), []
    for it in sorted(items, key=lambda i: i["score"], reverse=True):
        day = (datetime.fromisoformat(it["first_seen"]) + tz).date().isoformat()
        tab = it["media_tab"]
        if used[(day, tab)] >= limits[tab] or per_chan[(day, tab, it["source"])] >= per_channel:
            continue
        used[(day, tab)] += 1
        per_chan[(day, tab, it["source"])] += 1
        it["day"] = day
        out.append(it)
    return out


def fetch_all(sources, settings, db, now):
    status, errors, new_total = [], [], 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(fetch.fetch_source, s, settings): s for s in sources}
        for job in as_completed(jobs):
            src = jobs[job]
            try:
                items = job.result()
            except Exception as e:
                errors.append(f"{src['name']}: {e}")
                status.append({"name": src["name"], "ok": False, "found": 0, "new": 0, "error": str(e)[:160]})
                continue
            new = 0
            for it in items:
                if not it["title"] or not it["link"] or too_old(it, settings, now) or db.seen(it):
                    continue
                it["ai_summary"] = summarize.summarize(it, settings)  # None unless AI is set up
                it["summary"] = summarize.extract(it)
                db.add(it, now)
                new += 1
            new_total += new
            status.append({"name": src["name"], "ok": True, "found": len(items), "new": new, "error": ""})
    return status, errors, new_total


def main():
    ap = argparse.ArgumentParser(description="Field Radar")
    ap.add_argument("--open", action="store_true", help="open the dashboard afterwards")
    ap.add_argument("--offline", action="store_true", help="don't fetch, just rebuild the dashboard")
    ap.add_argument("--no-notify", action="store_true", help="no Windows notification")
    args = ap.parse_args()

    if sys.stdout:
        sys.stdout.reconfigure(errors="replace")
    DATA.mkdir(exist_ok=True)
    config = load_toml("config.toml")
    settings = config.get("settings", {})
    sources = [s for s in load_toml("sources.toml").get("sources", []) if s.get("enabled", True)]
    manual_deadlines = load_toml("deadlines.toml").get("deadline", [])

    db = store.Store(DATA / "radar.db")
    now = datetime.now(timezone.utc)
    status, errors, new_total = [], [], 0
    if not args.offline:
        status, errors, new_total = fetch_all(sources, settings, db, now)
        db.prune(int(settings.get("keep_days", 90)))
        db.log_run(now, new_total, "\n".join(errors))
        db.commit()

    # Score everything recent (so config edits apply to old items too)
    runs = db.last_runs(1)
    latest_run = runs[0]["at"] if runs else now.isoformat()
    pool = {r["id"]: r for r in db.recent(int(settings.get("days_back", 14)))}
    pool.update({r["id"]: r for r in db.opportunities(int(settings.get("opportunity_days", 60)))})
    scorer = score.Scorer(config, sources)
    min_score = float(settings.get("min_score", 3.0))
    media_min = float(settings.get("media_min_score", 3.5))
    scored, media = [], []
    for it in pool.values():
        info = scorer.score(it, now)
        if not info:
            continue
        it.update(info)
        it["is_new"] = it["first_seen"] >= latest_run
        if info["media_tab"]:
            if info["score"] >= media_min:
                it["media"] = json.loads(it["media"]) if it.get("media") else {}
                if it["kind"] == "video" and 0 < seconds(it["media"].get("duration")) < 180:
                    it["media_tab"] = "shorts"  # under 3 minutes: belongs with the shorts
                media.append(it)
        elif info["score"] >= min_score:
            scored.append(it)
    media = pick_media(media, settings)
    # Keep only the best N per source so a busy feed can't drown the rest,
    # and drop near-duplicate headlines (same story from several newspapers)
    cap, per_source, shown, seen_words = int(settings.get("max_per_source", 15)), Counter(), [], []
    for it in sorted(scored, key=lambda i: i["score"], reverse=True):
        words = set(normalize_title(it["title"]).split())
        if any(len(words & w) / max(1, len(words | w)) > 0.5 for w in seen_words):
            continue
        if per_source[it["source"]] < cap:
            per_source[it["source"]] += 1
            seen_words.append(words)
            shown.append(it)

    meta = {
        "generated": now.isoformat(),
        "latest_run": latest_run,
        "sources": sorted(status, key=lambda s: (s["ok"], s["name"])),
        "new_total": new_total,
    }
    picks = dashboard.build(DASHBOARD, shown, config, manual_deadlines, meta, media)

    new_shown = [i for i in shown if i["is_new"]]
    soon = sorted((i for i in shown if i.get("days_left") is not None and i["days_left"] <= 14),
                  key=lambda i: i["days_left"])
    lines = [
        f"Field Radar · {now.astimezone():%d %b %Y %H:%M}",
        f"Sources OK: {sum(s['ok'] for s in status)}/{len(status)}" if status else "Offline rebuild",
        f"New items stored: {new_total} · Shown on dashboard: {len(shown)} · New & relevant: {len(new_shown)}",
        f"Videos: {sum(m['media_tab'] == 'shorts' for m in media)} shorts · "
        f"{sum(m['media_tab'] == 'longform' for m in media)} long-form",
        f"Dashboard: {DASHBOARD}",
    ]
    lines += [f"  ! {e}" for e in errors]
    log(lines)

    if settings.get("notify", True) and not args.no_notify and not args.offline:
        top = picks[0]["title"] if picks else "No standout items today."
        second = f"{len(new_shown)} new relevant items"
        if soon:
            second += f" · ⏰ {len(soon)} deadline(s) within 14 days"
        notify.notify("Field Radar — your daily briefing", second, top[:120], DASHBOARD)

    if args.open or settings.get("open_dashboard"):
        webbrowser.open(DASHBOARD.as_uri())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        DATA.mkdir(exist_ok=True)
        LOG.write_text("Field Radar crashed:\n" + traceback.format_exc(), encoding="utf-8")
        raise
