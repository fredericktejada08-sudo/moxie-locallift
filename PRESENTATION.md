# LocalLift -- 15-20 Minute Team Demo

These are factual speaking prompts, not a script. Use your own language in the interview.

## 0:00-3:00 -- Problem and scale

- Moxie's small SEO team supports 700+ local medspa businesses.
- A manual first pass repeats the same checks, produces inconsistent prioritization, and spends specialist
  time documenting facts that software can extract.
- LocalLift targets the triage step: find the site that needs attention, show why, and route the next action.
- The goal is not an autonomous SEO consultant. It is a faster, more consistent evidence packet for one.

## 3:00-9:00 -- Working demo

1. Start on the portfolio view. Point out that Northline's noindex page rises above content refinements.
2. Switch to Site crawl, enter a main domain, and show the 10/25/50-page scope control.
3. Run the crawl without Claude first. Open the Evidence tab to show sitemap discovery, page types, and the
   page inventory produced before AI is involved.
4. Open an aggregate finding and show the affected URLs, per-page scores, exact evidence, and action.
5. Run Claude synthesis. Show evidence IDs and the separate human verification queue.
6. Open Harbor. Show that the workflow can return no material automated issue instead of manufacturing work.
7. Add the audit to a project. Show that Google Business Profile, Search Console, and GA4 authorization is
   scoped to that project and that unconfigured sources remain visibly disconnected.
8. Export CSV for the implementation queue, PDF for a team/client readout, and JSON for automation.
9. If live crawling is not practical, use the offline page portfolio and explain the same evidence contract.

## 9:00-13:00 -- How AI is used

- Python discovers eligible pages, classifies their roles, extracts facts, and applies repeatable issue rules.
- Claude receives only those facts and issues, then creates the executive summary, top three actions,
  metadata option, human checks, and scale note.
- Structured output makes the response parseable. A second application-layer check removes any action
  that does not cite a real issue ID.
- This is where AI helps: prioritization language, implementation sequencing, and clear communication.
- This is where it does not help: proving GBP data, Search Console performance, rankings, medical claims,
  whether an image is decorative, or anything absent from the fetched page.
- In the first live test, Claude returned valid JSON but still invented a `MedicalSpa` schema label and an
  unsupported outcome claim. The prompt was tightened and the second run removed both. Valid structure is
  not the same as valid SEO judgment; `AI_EVALUATION.md` preserves the evidence.

## 13:00-16:00 -- Judgment and limitations

- The score is a queue-routing heuristic, not a ranking prediction.
- Empty alt text and low word count are review prompts, not automatic SEO violations.
- The focused crawl is capped at 50 URLs and static fetches miss JavaScript-rendered output.
- A failed AI call never blocks or contaminates the deterministic audit.
- Live pages may block automated requests; the offline portfolio keeps the demo reliable.

## 16:00-19:00 -- Next scale step

- One week: persistent audit history, rendered-page analysis, recursive link discovery, and direct ticket export.
- Next phase: join Search Console, GBP, PageSpeed, and backlink data using the same evidence-ID contract.
- Production: asynchronous jobs, change detection, tenant access controls, approval workflows, cost limits,
  evaluation datasets, and prompt/version monitoring.
- The output should route specialists toward exceptions, while clean sites move into monitoring.

## Close

- Restate the operating principle: automate facts, use AI for bounded synthesis, keep judgment with the SEO
  specialist.
