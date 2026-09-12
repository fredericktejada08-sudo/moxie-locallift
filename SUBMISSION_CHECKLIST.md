# Submission Checklist

## Selected track

**Track A -- Build a Claude-Powered SEO Workflow**

LocalLift is a working local SEO crawler/analyzer that converts a medspa page or main domain into a
prioritized, evidence-grounded work queue and optional Claude synthesis.

## Assessment requirements

- [x] Working tool or workflow
- [x] Real SEO task with a clear connection to operating at scale
- [x] Visible input, deterministic evidence, AI output, and validation step
- [x] Honest AI limitations and explicit human review points
- [x] Offline demo path for a reliable interview walkthrough
- [x] 15-20 minute walkthrough structure
- [ ] Shareable link, repository, file, or screen recording up to 3 minutes
- [ ] Candidate-written summary of 200-400 words
- [ ] Submit to the hiring contact before the Delivery interview

## Candidate-only written summary worksheet

The assessment explicitly says not to use AI to write the 200-400 word summary. Write this section yourself.
Useful facts to cover:

- Track selected: Track A
- Tool name: LocalLift
- Problem: repeated and inconsistent first-pass local SEO triage across a large medspa portfolio
- Input: business name, city, optional priority service, main domain, and 10/25/50-page crawl limit
- Output: discovered page inventory, role-aware checks, aggregate issues, optional Claude action plan,
  human verification queue, project audit history, GBP/GSC/GA4 connection states, and JSON/CSV/PDF exports
- AI boundary: Claude synthesizes supplied evidence; it does not invent or verify GBP, ranking, traffic,
  backlink, conversion, or clinical data
- Demo context: three fictional offline businesses are included; live page and live Claude modes are optional
- Important limitation: focused page-level triage, not a full crawler or complete SEO audit
- Personal reflection to add: what you chose, what you changed after testing, and what you would improve next

Before submitting, read the summary aloud and make sure every sentence sounds like you and is something you
can defend in the live walkthrough.

## Share package

Include:

- `README.md`
- application source (`server.py`, `locallift/`, `static/`)
- tests
- `PRESENTATION.md`
- `AI_EVALUATION.md`
- your own 200-400 word summary
- optional screen recording no longer than 3 minutes

Do not include `.env` or an API key.
