"""Keyword relevance, evidence labelling and ranking. No AI needed.

Every item is re-scored on each run, so edits to config.toml apply
to old items too.
"""
import re
from datetime import datetime, timezone

from .textutil import find_deadline, find_first_date

# key: (label shown on the card, credibility points, group for the filter)
EVIDENCE = {
    "meta":          ("Meta-analysis / Review", 5.0, "research"),
    "experiment":    ("Experiment / RCT", 4.0, "research"),
    "peer":          ("Peer-reviewed", 3.0, "research"),
    "preprint":      ("Preprint · not yet peer-reviewed", 1.5, "research"),
    "research-news": ("Research news", 1.5, "research"),
    "industry":      ("Industry report / survey", 1.5, "practice"),
    "practitioner":  ("Practitioner article", 1.0, "practice"),
    "news":          ("News", 0.5, "news"),
    "opinion":       ("Opinion / blog", 0.0, "news"),
    "phd":           ("PhD / research position", 0.0, "opportunity"),
    "cfp":           ("Conference / call for papers", 0.0, "opportunity"),
    "short":         ("Short", 0.0, "media"),
    "video":         ("Video", 0.0, "media"),
    "podcast":       ("Podcast", 0.0, "media"),
}
MEDIA = {"short", "video", "podcast"}
KIND_TO_EVIDENCE = {"peer-reviewed": "peer"}

META = re.compile(r"meta-analy|meta analy|systematic (literature )?review|scoping review|umbrella review", re.I)
EXPERIMENT = re.compile(r"randomi[sz]ed|controlled trial|\brct\b|field experiment|natural experiment|"
                        r"experimental (study|evidence|design)|preregistered experiment", re.I)
# "10 Things…", "IIM Courses: 7 Programs…" — numbered listicles
LISTICLE = re.compile(r"(^|:\s+)\d{1,2}\s+[A-Za-z]")


def _rx(words):
    return [re.compile(r"(?<![a-z0-9])" + re.escape(w.lower().strip()) + r"(?![a-z0-9])")
            for w in words if w.strip()]


def _any(rxs, text):
    return any(r.search(text) for r in rxs)


class Scorer:
    def __init__(self, config, sources=()):
        self.settings = config.get("settings", {})
        # `base` in sources.toml: extra points for hand-picked, always-on-topic channels/podcasts
        self.source_base = {s["name"]: float(s.get("base", 0)) for s in sources}
        self.interests = [{
            "id": it["id"], "name": it["name"], "icon": it.get("icon", "•"),
            "strong": _rx(it.get("strong", [])), "normal": _rx(it.get("normal", [])),
            "boost_only": bool(it.get("boost_only", False)),
        } for it in config["interests"]]
        self.boost_only = {it["id"] for it in self.interests if it["boost_only"]}
        opp = config.get("opportunities", {})
        self.phd = _rx(opp.get("phd_words", []))
        self.funded = _rx(opp.get("funded_words", []))
        self.europe = _rx(opp.get("europe_words", []))
        self.skip = _rx(opp.get("skip_words", []))
        self.phd_topics = _rx(opp.get("phd_topics", []))
        noise = config.get("noise", {})
        self.fluff = _rx(noise.get("fluff", []))
        self.off_topic = _rx(noise.get("off_topic", []))

    def area_scores(self, title, body):
        t, b = title.lower(), body.lower()
        out, strong_hits = {}, 0
        for it in self.interests:
            s = 0.0
            for r in it["strong"]:
                if r.search(t):
                    s += 4.0
                elif r.search(b):
                    s += 2.0
                else:
                    continue
                if not it["boost_only"]:
                    strong_hits += 1
            n = 0.0
            for r in it["normal"]:
                if r.search(t):
                    n += 1.0
                elif r.search(b):
                    n += 0.4
            out[it["id"]] = min(s + min(n, 2.5), 12.0)
        return out, strong_hits

    def evidence(self, kind, text):
        flags = []
        key = KIND_TO_EVIDENCE.get(kind, kind)
        if key not in EVIDENCE:
            key = "news"
        is_meta, is_exp = bool(META.search(text)), bool(EXPERIMENT.search(text))
        if key == "peer":
            key = "meta" if is_meta else "experiment" if is_exp else "peer"
        elif key in ("preprint", "research-news"):
            if is_meta:
                flags.append("Review / meta-analysis")
            elif is_exp:
                flags.append("Experiment")
        return key, flags

    def score(self, item, now=None):
        """Return scoring info for an item, or None if it should be hidden."""
        now = now or datetime.now(timezone.utc)
        title, body = item["title"], item.get("summary") or ""
        text = f"{title} {body}"
        low = text.lower()
        kind = item["kind"]

        areas, strong_hits = self.area_scores(title, f"{body} {item.get('venue', '')}")
        hint = item.get("hint")
        if hint in areas:
            areas[hint] += 1.5
        # "Boost-only" areas (Research & Methods) add a bonus but can't make
        # an item relevant on their own — a rigorous study must also be on-topic.
        topical = {k: v for k, v in areas.items() if k not in self.boost_only}
        best_id = max(topical, key=topical.get)
        best = topical[best_id]
        others = sorted(topical.values())[-3:-1]
        boost = max((areas[k] for k in self.boost_only), default=0.0)
        relevance = best + 0.25 * sum(others) + (0.4 * boost if best >= 3 else 0.0)

        penalty = 0.0
        if _any(self.fluff, title.lower()) or LISTICLE.search(title):
            penalty -= 3.0
        if _any(self.off_topic, low):
            penalty -= 4.0

        if kind in MEDIA:
            return self._score_media(item, kind, areas, topical, best, best_id, relevance, penalty, now)

        if item.get("filter") and best < 3:
            return None

        ev_key, flags = self.evidence(kind, text)
        ev_label, ev_points, group = EVIDENCE[ev_key]
        ev_flags = list(flags)  # design signals only (before Funded/Europe are added)

        when = item.get("published") or item.get("first_seen")
        age_days = 7.0
        if when:
            try:
                age_days = max(0.0, (now - datetime.fromisoformat(when)).total_seconds() / 86400)
            except ValueError:
                pass
        recency = max(0.0, 2.0 - 0.15 * age_days)

        opp, deadline, deadline_what = 0.0, None, ""
        if ev_key == "phd":
            if self.phd_topics and not _any(self.phd_topics, title.lower()):
                # unrelated field — unless it's a general scholarship scheme open to any field
                if "scholarship" not in title.lower():
                    return None
                opp -= 1.0
            has_phd = _any(self.phd, low)
            opp += 4.0 if has_phd else -2.0
            if _any(self.skip, title.lower()):
                opp -= 4.0  # postdoc / lecturer jobs, not PhD positions
            if _any(self.funded, low):
                opp += 2.0
                flags.append("Funded")
            if _any(self.europe, low):
                opp += 2.0
                flags.append("Europe")
            deadline = find_deadline(text)
            deadline_what = "Apply by"
        elif ev_key == "cfp":
            if best < 2:
                return None
            deadline = find_first_date(body)
            deadline_what = "Event starts"
            flags.append("Check organiser")
            opp += 1.0
        else:
            deadline = find_deadline(text) if "deadline" in low or "apply by" in low else None
            deadline_what = "Deadline" if deadline else ""

        days_left = None
        if deadline:
            days_left = (deadline.date() - now.date()).days
            if days_left < 0:
                return None  # expired
            if days_left <= 60:
                opp += 2.0

        total = relevance + ev_points + recency + opp + penalty
        tags = [k for k, v in topical.items() if v >= 3]
        # Research tab: rigorous designs, or research items with clear methods signals
        if best >= 3 and (ev_key in ("meta", "experiment") or ev_flags
                          or (group == "research" and boost >= 2)):
            tags += list(self.boost_only)
        if ev_key in ("phd", "cfp"):
            tags.append("opportunities")
        return {
            "score": round(total, 2),
            "primary": "opportunities" if ev_key in ("phd", "cfp") else best_id,
            "media_tab": None,
            "tags": tags,
            "evidence": ev_key,
            "evidence_label": ev_label,
            "group": group,
            "flags": flags,
            "deadline": deadline.date().isoformat() if deadline else None,
            "deadline_what": deadline_what,
            "days_left": days_left,
        }

    def _score_media(self, item, kind, areas, topical, best, best_id, relevance, penalty, now):
        """Videos & podcasts: titles are short, so the bar is lower than for articles,
        and hand-picked channels can carry a `base` bonus."""
        base = self.source_base.get(item.get("source"), 0.0)
        min_rel = float(self.settings.get("media_min_relevance", 2.0))
        if item.get("filter") and best < min_rel:
            return None
        if penalty < 0:
            return None  # promos ("webinar", "mini preview"…) and off-topic videos are dropped outright
        when = item.get("published") or item.get("first_seen")
        age_days = 3.0
        if when:
            try:
                age_days = max(0.0, (now - datetime.fromisoformat(when)).total_seconds() / 86400)
            except ValueError:
                pass
        recency = max(0.0, 2.0 - 0.15 * age_days)
        total = relevance + base + recency + penalty
        label, _, group = EVIDENCE[kind]
        tags = [k for k, v in topical.items() if v >= min_rel]
        return {
            "score": round(total, 2),
            "primary": "media",
            "media_tab": "shorts" if kind == "short" else "longform",
            "tags": tags,
            "evidence": kind,
            "evidence_label": label,
            "group": group,
            "flags": [],
            "deadline": None,
            "deadline_what": "",
            "days_left": None,
        }
