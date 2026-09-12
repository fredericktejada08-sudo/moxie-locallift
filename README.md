# LocalLift

LocalLift is a working Track A submission for Moxie's AI-Focused SEO Specialist take-home. It turns a
medspa page or main website URL into an evidence-grounded local SEO work queue: discovery and extraction
first, rule-based prioritization second, and optional Claude synthesis last.

The separation matters. Claude never receives an unsupported claim such as estimated traffic, rankings,
reviews, or GBP status. It sees only machine-extracted page facts and issue IDs, and every AI-prioritized
action must cite one of those IDs. Anything the page cannot prove is routed to a human verification queue.

## Start the demo

Python 3.11+ is required. ReportLab powers the direct PDF export.

```bash
cd /home/fredericktejada/projects/moxie-locallift
python3 -m pip install -r requirements.txt
python3 server.py
```

Open <http://127.0.0.1:8042>. The fictional three-site portfolio loads automatically and needs neither
internet access nor an API key.

For live Claude synthesis:

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
python3 server.py
```

Live URL analysis requires outbound internet access. If Claude is unconfigured or unavailable, the page
analysis still completes and clearly labels the result as rules-only.

Projects work without external credentials and persist under `.data/`. To enable the project-level Google
connection buttons, create a Google OAuth 2.0 Web application and add this exact authorized redirect URI:

```text
http://127.0.0.1:8042/oauth/google/callback
```

Then add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`. LocalLift requests each source only when
the user clicks its Connect button:

- GBP: `https://www.googleapis.com/auth/business.manage`
- GSC: `https://www.googleapis.com/auth/webmasters.readonly`
- GA4: `https://www.googleapis.com/auth/analytics.readonly`

To use the client identity from existing authorized-user profiles, set `GOOGLE_GBP_OAUTH_PROFILE_FILE`,
`GOOGLE_GSC_OAUTH_PROFILE_FILE`, and/or `GOOGLE_GA4_OAUTH_PROFILE_FILE`. LocalLift reads the client ID and
secret, then opens a new Google account picker and consent screen for the selected source. It never reuses the
profile's refresh token. Desktop-client profiles return to `http://localhost:8042` by default.

Newly authorized Google tokens are never returned to the browser or stored in project JSON. This local prototype stores them
in `.data/google_tokens.json` with owner-only permissions. Production deployment requires encrypted secret
storage and a public HTTPS callback.

Semrush is separate from projects. Add a Version 4 key with Keyword Reports access and available API units as
`SEMRUSH_API_KEY` in `.env`. The Keywords workspace retrieves the latest country-level volume, difficulty,
CPC, intent, competition, SERP features, and 12-month trend, then keeps up to 24 refresh snapshots per keyword
in `.data/keyword_monitor.json`. Each lookup currently costs 20 Semrush API units, so research and refresh
requests are capped at 10 keywords.

## What it does

1. Validates the submitted URL and blocks local/private network targets.
2. In Site crawl mode, reads sitemap locations from robots.txt and `/sitemap.xml`, follows sitemap indexes,
   supplements discovery with homepage links, removes assets and utility URLs, then prioritizes up to 50 pages.
3. Classifies homepage, service, location, article, about, contact, and general pages so each receives only
   applicable local SEO checks.
4. Fetches up to 2 MB per public HTML page, following only validated public redirects.
5. Extracts title, description, H1s, canonical, robots directives, JSON-LD types, local schema/address,
   visible word count, image alt coverage, internal links, phone links, and city/service placement.
6. Groups repeated issues across affected URLs while preserving the complete per-page evidence inventory.
7. Optionally calls Claude using a strict JSON schema and validates that its action references point to
   real issue IDs.
8. Saves audit snapshots into persistent business projects and surfaces their prioritized recommendations,
   affected pages, implementation steps, and human review checks directly in the project dashboard.
9. Authorizes GBP, GSC, and GA4 independently at project level through incremental Google OAuth.
10. Researches Semrush keyword metrics and monitors volume changes without creating Semrush projects.
11. Keeps multiple audits in a portfolio view, filters urgent sites, and exports any result as JSON, CSV,
    or a styled PDF report.

The API also includes `POST /api/batch` for up to 10 sites per request. This is the same contract the UI
would use for a spreadsheet, CRM, or scheduled-crawl integration.

## API examples

Single page:

```bash
curl -s http://127.0.0.1:8042/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Example MedSpa",
    "city": "Austin",
    "service": "Laser Hair Removal",
    "url": "https://example.com/laser-hair-removal",
    "use_ai": false
  }'
```

Whole-site crawl:

```bash
curl -s http://127.0.0.1:8042/api/crawl \
  -H 'Content-Type: application/json' \
  -d '{
    "business_name": "Example MedSpa",
    "city": "Austin",
    "service": "Laser Hair Removal",
    "url": "https://example.com",
    "max_pages": 25,
    "use_ai": false
  }'
```

Bulk page audits remain available through `POST /api/batch`:

```json
{
  "use_ai": false,
  "sites": [
    {
      "business_name": "Example MedSpa",
      "city": "Austin",
      "service": "Laser Hair Removal",
      "url": "https://example.com/laser-hair-removal"
    }
  ]
}
```

Project endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/projects` | List saved projects, audit summaries, and connector states |
| `POST /api/projects` | Create a project |
| `POST /api/projects/{id}/audits` | Save or update an audit snapshot |
| `GET /api/projects/{id}/dashboard` | Read evidence-linked suggestions from the primary site audit |
| `GET /api/projects/{id}/dashboard?audit_id={audit}` | Read suggestions from a selected saved snapshot |
| `GET /api/projects/{id}/google/connect?source=gsc` | Start `gbp`, `gsc`, or `ga4` authorization |
| `POST /api/projects/{id}/google/disconnect` | Remove a project connection |
| `GET /api/keywords` | List monitored keywords and Semrush availability |
| `POST /api/keywords/research` | Fetch and save metrics for up to 10 keywords |
| `POST /api/keywords/refresh` | Refresh selected monitored keyword snapshots |
| `POST /api/keywords/delete` | Remove a monitored keyword |

## Project map

| Path | Responsibility |
|---|---|
| `server.py` | HTTP server, API endpoints, batch orchestration, static app |
| `locallift/analyzer.py` | public URL guardrails, fetch, structured HTML extraction |
| `locallift/crawler.py` | sitemap discovery, URL filtering, page classification, crawl aggregation |
| `locallift/rules.py` | deterministic scoring and evidence-backed issue records |
| `locallift/claude.py` | prompt, JSON schema, Claude API call, evidence-ID validation |
| `locallift/exporters.py` | styled page/site PDF report generation |
| `locallift/projects.py` | local project records, audit snapshots, private token persistence |
| `locallift/google_oauth.py` | incremental GBP, GSC, and GA4 OAuth authorization |
| `locallift/keywords.py` | Semrush keyword metrics, validation, and volume history |
| `locallift/demo.py` | three fictional offline pages and labeled reference output |
| `static/` | responsive portfolio triage interface |
| `tests/` | extractor and prioritization regression tests |
| `PRESENTATION.md` | 15-20 minute interview run-of-show |
| `AI_EVALUATION.md` | real two-pass Claude test and the prompt correction it caused |
| `SUBMISSION_CHECKLIST.md` | take-home requirements and candidate-only writing worksheet |

## Design decisions

- **Evidence before AI:** HTML parsing and severity are deterministic. The LLM improves synthesis and
  communication; it does not decide what the page contains.
- **Failure is visible:** network errors, missing credentials, and Claude failures do not become invented
  findings or silent fallbacks.
- **Human review stays explicit:** GBP/NAP accuracy, Search Console performance, medical claims, visual
  image meaning, and rendered-JavaScript behavior are outside a static HTML fetch.
- **No production data in the offline demo:** all three businesses and pages are fictional.
- **Operational output:** detailed CSV and JSON support tickets and QA; the PDF supports client/team review.
- **Project boundary:** audits and Google authorization belong to a business project rather than a temporary
  browser session.

## Known limitations

- This is a focused crawler capped at 50 prioritized URLs, not a replacement for a full enterprise crawl.
  Without a sitemap it discovers only the homepage and its direct internal links.
- It does not validate redirect chains, full internal link graphs, robots.txt blocking rules, hreflang,
  response parity across user agents, or JavaScript-rendered content.
- Static extraction cannot verify the live GBP, NAP citations, reviews, rankings, traffic, conversions,
  backlinks, Core Web Vitals, or competitor gaps.
- The Google connectors currently complete authorization and record connection state. Account/location and
  property selection, scheduled ingestion, token refresh, and source-backed audit rules are the next phase.
- Semrush Keyword Reports requires Standard API access and available units. A valid Version 4 key without that
  entitlement is rejected by Semrush with `403 Forbidden`.
- The readiness score is a routing heuristic, not a Google ranking score.
- Word count and empty alt values are review signals, not automatic quality violations.
- A production version needs authentication, tenant isolation, a job queue, persistent audit history,
  retry controls, rate limits, monitoring, and an approved data-retention policy.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py locallift/*.py
```

The Claude request follows Anthropic's Messages API and current `output_config.format` structured-output
shape. `ANTHROPIC_MODEL` is configurable because model availability changes over time.
