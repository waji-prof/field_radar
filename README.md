# Field Radar

A free daily briefing for **Applied & Organizational Psychology, L&D, Future of Work,
Behavioral Science, UX research, research methods, and AI in HR/L&D**, plus a
PhD and conference deadline tracker.

- **Cost: ₹0.** No API keys, no subscriptions, no hosting, nothing to buy.
- **Runs on your own PC** using Python (free, open source) and only Python's built-in parts,
  so there's nothing extra to install.
- **Private.** Everything stays in this folder. Nothing is uploaded anywhere.

---

## Quick start

1. **Get today's briefing:** double-click **`run_radar.bat`**. After about 30–60 seconds
   your dashboard opens in the browser.
2. **Make it automatic (optional):** double-click **`schedule_install.bat`** and type a time
   (e.g. `08:00`). Every day at that time you'll get a Windows notification. Click it to
   open the dashboard.
3. **Tune it:** open `config.toml` in Notepad to change keywords, how strict the filter is,
   and more. Save, then run again.

To stop the daily run, double-click `schedule_remove.bat`.

---

## What works for free, and what needs your PC switched on

| Feature | Free? | Needs PC on? |
|---|---|---|
| Fetching new journal papers, preprints, news, PhDs, conferences | ✅ | ✅ Yes, it runs on your PC |
| Keyword relevance scoring and evidence labels | ✅ | ✅ Yes, during the run |
| Daily automatic run (Windows Task Scheduler) | ✅ | ✅ Yes. If the PC is off at 08:00, it runs **as soon as you switch it on** |
| Windows pop-up notification | ✅ | ✅ Yes |
| **Viewing** the dashboard | ✅ | ✅ Yes, but **no internet needed** to view it. It's a single saved file |
| Deadline tracker | ✅ | Only to refresh it |
| AI-written summaries | ❌ Not in this version (see "Adding AI later") | — |
| Updates while the PC is off, or on your phone | Possible for free with GitHub (see "Ideas for later"). Not set up yet | — |

In short: **everything here is free. It only needs the PC on for the few minutes it fetches.**
You don't have to keep it running all day.

---

## Where the information comes from (all free and public)

| Type | Sources |
|---|---|
| **Peer-reviewed journals** (via **Crossref**, the official DOI registry) | J. Applied Psychology, Personnel Psychology, J. Organizational Behavior, JOOP, EJWOP, AMJ, OBHDP, Leadership Quarterly, Work & Stress, JOHP, J. Vocational Behavior, J. Business & Psychology, Applied Psychology, GOM, Human Relations, Org. Psychology Review · HRDQ, HRDR, IJTD, AMLE, J. Workplace Learning, EJTD, Management Learning, Human Resource Management · J. Behavioral Decision Making, Behavioural Public Policy, Nature Human Behaviour, Psychological Bulletin · Computers in Human Behavior, IJHCS |
| **Preprints** | PsyArXiv, arXiv (Human-Computer Interaction, Computers & Society) |
| **Research news** | APS (Association for Psychological Science), ScienceDaily Psychology |
| **Practice & industry** | MIT Sloan Management Review, Harvard Business Review, Josh Bersin, Training Industry, Behavioural Insights Team, Behavioral Scientist, Nielsen Norman Group, eLearning Industry, UX Collective |
| **News & reports** | Google News searches for each interest area, plus workforce reports (Gallup, CIPD, SHRM, Deloitte, McKinsey, WEF, Microsoft, LinkedIn) |
| **PhD positions** | EURAXESS (EU official), jobs.ac.uk, Academic Positions, funded-PhD news |
| **Conferences** | WikiCFP (psychology, behavioral science, HCI), plus your own list in `deadlines.toml` |

Edit or add sources in **`sources.toml`**. Each source is a small block you can copy.

---

## Reading the dashboard

- **⭐ Top picks**: the best new items, at most two per interest area, so one topic can't take over.
- **One tab per interest area**, plus **🎯 PhDs & Conferences**, **⏰ Deadlines**, **🔖 Saved**
  (star ☆ any item), and **⚙ Sources & help**, which shows whether each source worked.
- **Filters:** search, evidence type (e.g. "Strong evidence only"), newest first, "New only".
- Every card shows **headline → original source link → publisher/journal → date →
  a short description taken from the source** (often the paper's abstract).

### Evidence labels: separating evidence from opinion

| Label | Meaning |
|---|---|
| **Meta-analysis / Review** | Pools many studies. Strongest evidence. |
| **Experiment / RCT** | Tests cause and effect. |
| **Peer-reviewed** | Journal article checked by expert reviewers. |
| **Preprint · not yet peer-reviewed** | New research that reviewers haven't checked yet. |
| **Research news** | A journalist's write-up of a study. Click through to the original. |
| **Industry report / survey** | Useful, but often run by companies with an interest in the result. |
| **Practitioner article** | Expert experience and frameworks, not data. |
| **News**, **Opinion / blog** | Awareness only. Not evidence. |

### How ranking works (no AI)

Points for: matching your keywords (title matches count double) · stronger evidence ·
recency · for PhDs: *funded*, *in Europe*, deadline soon.
Points lost for: listicle and fluff headlines ("10 tips…"), off-topic subjects (stocks, clinical topics…).
Items under `min_score` are hidden, and each source shows at most `max_per_source` items.

---

## Customising

| I want to… | Do this |
|---|---|
| See **fewer, better** items | Raise `min_score` in `config.toml` (e.g. 6 → 8) |
| See **more** items | Lower `min_score` (e.g. 6 → 4) |
| Track a new topic | Add phrases to `strong = [...]` in the right interest area |
| Hide a recurring annoyance | Add a word to `off_topic` or `fluff` |
| Add a journal | Find its ISSN (on the journal's website) and add it to a `crossref` block in `sources.toml` |
| Add a blog or site | Find its RSS feed URL and copy an `rss` block in `sources.toml` |
| Add a conference or PhD deadline | Add a `[[deadline]]` block in `deadlines.toml` with `date = "YYYY-MM-DD"` |
| Change the daily time | Run `schedule_install.bat` again |

---

## Honest limitations of the free version

- **No AI summaries.** You see the source's own description: the abstract for most journal papers,
  the feed snippet for blogs. Google News items have no description, only the headline.
- **Some journals (often Elsevier) don't share abstracts** through Crossref, so those cards show
  only the title and link.
- **PhD sites like EURAXESS and jobs.ac.uk have no working RSS feed**, so Field Radar finds their
  listings through Google News. It catches many but not all positions. Still check the portals directly now and then.
- **Deadlines are found automatically only when a listing writes them out**
  ("Apply by 2 December 2026"). WikiCFP shows **event dates**, not submission deadlines.
- **WikiCFP is community-posted.** Some conferences listed there are low quality or predatory.
  Always check the organiser.
- **Keyword matching is simple.** Expect a few misses and a few odd items. Tune `config.toml` over time.
- **Google News links** go through a Google redirect before reaching the article. That's normal.

---

## Adding AI later (only when you decide to)

Everything is ready for it. The one place to plug it in is **`fieldradar/summarize.py`**,
switched on by `summarizer = "..."` in `config.toml`. It only runs on **new** items, once each,
and saves the result, so nothing is ever summarised twice.

| Option | Cost | Notes |
|---|---|---|
| **Ollama** (open source, runs on your PC) | ₹0 | Free, but needs a reasonably powerful PC (8–16 GB RAM) and is slower |
| **Claude API** (Anthropic) | Paid per use | Best quality summaries and "why it matters to you" notes. Decide on a budget first |

Nothing here turns on by itself. It stays `"none"` until you change it.

## Ideas for later (still ₹0)

- **Run without your PC, read on your phone:** GitHub's free tier (GitHub Actions + GitHub Pages)
  can run Field Radar daily in the cloud and publish the dashboard as a web page. The catch: on
  the free plan the page is public. It only contains public headlines and links, but it is visible to anyone with the address.
- **Phone notifications:** *ntfy* is a free, open-source push-notification app.
- **Weekly summary tab** (top themes of the week) and **export saved items to Zotero/BibTeX**.

---

## Files

```
run_radar.bat          ← double-click: fetch + open dashboard
schedule_install.bat   ← double-click: run automatically every day
schedule_remove.bat    ← double-click: stop the daily run
config.toml            ← your interests, keywords, filter strictness
sources.toml           ← where it looks
deadlines.toml         ← your own deadline list
dashboard.html         ← the dashboard (created by each run)
data/radar.db          ← memory of what you've seen (delete it to start fresh)
data/last_run.log      ← what happened in the last run (check here if something looks wrong)
radar.py, fieldradar/  ← the program itself
```

## Troubleshooting

- **Nothing happens / error:** open `data\last_run.log`.
- **A source shows ✗ in "Sources & help":** the website changed or was down. It usually fixes itself.
  If it keeps failing, set `enabled = false` for it in `sources.toml`.
- **"Python was not found":** install Python from python.org (free) and tick "Add python.exe to PATH".
- **No notification:** check Windows Settings → System → Notifications, and Focus Assist / Do Not Disturb.
