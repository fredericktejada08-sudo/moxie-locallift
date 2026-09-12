const state = {
  results: [],
  selectedId: null,
  tab: "overview",
  aiConfigured: false,
  loading: false,
  scope: "page",
  projects: [],
  selectedProjectId: null,
  projectDashboards: {},
  projectDashboardLoading: new Set(),
  projectDashboardErrors: {},
  pendingAuditAdd: false,
  keywords: [],
  selectedKeywordIds: new Set(),
  semrushConfigured: false,
  keywordLoading: false,
};

const els = {
  form: document.querySelector("#audit-form"),
  demoButton: document.querySelector("#demo-button"),
  analyzeButton: document.querySelector("#analyze-button"),
  exportButton: document.querySelector("#export-button"),
  csvButton: document.querySelector("#csv-button"),
  pdfButton: document.querySelector("#pdf-button"),
  portfolioList: document.querySelector("#portfolio-list"),
  portfolioCount: document.querySelector("#portfolio-count"),
  portfolioFilter: document.querySelector("#portfolio-filter"),
  emptyState: document.querySelector("#empty-state"),
  resultView: document.querySelector("#result-view"),
  resultContext: document.querySelector("#result-context"),
  resultTitle: document.querySelector("#result-title"),
  resultUrl: document.querySelector("#result-url"),
  sourceBadge: document.querySelector("#source-badge"),
  metrics: document.querySelector("#metrics"),
  tabContent: document.querySelector("#tab-content"),
  useAi: document.querySelector("#use-ai"),
  aiToggleWrap: document.querySelector("#ai-toggle-wrap"),
  apiDot: document.querySelector("#api-dot"),
  apiStatus: document.querySelector("#api-status"),
  modelStatus: document.querySelector("#model-status"),
  toast: document.querySelector("#toast"),
  scopeOptions: document.querySelectorAll(".scope-option"),
  auditTitle: document.querySelector("#new-audit-title"),
  fieldGrid: document.querySelector("#field-grid"),
  serviceInput: document.querySelector("#service"),
  serviceLabel: document.querySelector("#service-label"),
  urlInput: document.querySelector("#url"),
  urlLabel: document.querySelector("#url-label"),
  crawlLimitField: document.querySelector("#crawl-limit-field"),
  projectsButton: document.querySelector("#projects-button"),
  projectsCount: document.querySelector("#projects-count"),
  addProjectButton: document.querySelector("#add-project-button"),
  projectsDialog: document.querySelector("#projects-dialog"),
  closeProjectsButton: document.querySelector("#close-projects-button"),
  newProjectButton: document.querySelector("#new-project-button"),
  cancelProjectButton: document.querySelector("#cancel-project-button"),
  projectCreatePanel: document.querySelector("#project-create-panel"),
  projectForm: document.querySelector("#project-form"),
  projectName: document.querySelector("#project-name"),
  projectBusiness: document.querySelector("#project-business"),
  projectCity: document.querySelector("#project-city"),
  projectUrl: document.querySelector("#project-url"),
  projectsList: document.querySelector("#projects-list"),
  projectDetail: document.querySelector("#project-detail"),
  keywordsButton: document.querySelector("#keywords-button"),
  keywordsCount: document.querySelector("#keywords-count"),
  keywordsDialog: document.querySelector("#keywords-dialog"),
  closeKeywordsButton: document.querySelector("#close-keywords-button"),
  keywordsForm: document.querySelector("#keywords-form"),
  keywordsInput: document.querySelector("#keywords-input"),
  keywordsCountry: document.querySelector("#keywords-country"),
  researchKeywordsButton: document.querySelector("#research-keywords-button"),
  refreshKeywordsButton: document.querySelector("#refresh-keywords-button"),
  exportKeywordsButton: document.querySelector("#export-keywords-button"),
  keywordsNotice: document.querySelector("#keywords-notice"),
  monitoredKeywordsCount: document.querySelector("#monitored-keywords-count"),
  keywordsTableBody: document.querySelector("#keywords-table-body"),
  keywordsEmpty: document.querySelector("#keywords-empty"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sentenceCase(value) {
  const text = String(value || "").replaceAll("_", " ");
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("is-visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => els.toast.classList.remove("is-visible"), 3200);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The service returned HTTP ${response.status}.`);
  }
  if (!response.ok) {
    throw new Error(data.error || "The request could not be completed.");
  }
  return data;
}

function setLoading(loading) {
  state.loading = loading;
  els.analyzeButton.disabled = loading;
  els.demoButton.disabled = loading;
  els.pdfButton.disabled = loading;
  const idleLabel = state.scope === "site" ? "Crawl site" : "Analyze page";
  els.analyzeButton.textContent = loading ? (state.scope === "site" ? "Crawling..." : "Analyzing...") : idleLabel;
}

function setScope(scope) {
  state.scope = scope === "site" ? "site" : "page";
  const siteMode = state.scope === "site";
  els.scopeOptions.forEach((button) => {
    const active = button.dataset.scope === state.scope;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-checked", String(active));
  });
  els.auditTitle.textContent = siteMode ? "Audit an entire website" : "Analyze a service page";
  els.serviceLabel.textContent = siteMode ? "Priority service (optional)" : "Primary service";
  els.serviceInput.required = !siteMode;
  els.urlLabel.textContent = siteMode ? "Main site URL" : "Public page URL";
  els.urlInput.placeholder = siteMode ? "https://example.com" : "https://example.com/service-page";
  els.crawlLimitField.hidden = !siteMode;
  els.fieldGrid.classList.toggle("is-crawl", siteMode);
  setLoading(false);
}

function highestPriority(result) {
  if (!result.issues.length) return "clean";
  return result.issues[0].severity;
}

function priorityLabel(result) {
  const severity = highestPriority(result);
  return severity === "clean" ? "No high issues" : `${sentenceCase(severity)} priority`;
}

function filteredResults() {
  const filter = els.portfolioFilter.value;
  if (filter === "all") return state.results;
  if (filter === "clean") {
    return state.results.filter((result) => !result.issues.some((issue) => ["critical", "high"].includes(issue.severity)));
  }
  return state.results.filter((result) => result.issues.some((issue) => issue.severity === filter));
}

function renderPortfolio() {
  els.portfolioCount.textContent = state.results.length;
  const results = filteredResults();
  if (!results.length) {
    els.portfolioList.innerHTML = '<div class="portfolio-empty">No audits match this filter.</div>';
    return;
  }
  els.portfolioList.innerHTML = results.map((result) => {
    const priority = highestPriority(result);
    const siteAudit = result.audit_type === "site";
    const descriptor = siteAudit
      ? `Site crawl | ${result.site.city} | ${result.facts.pages_analyzed} pages`
      : `${result.site.service} | ${result.site.city}`;
    return `
      <button class="portfolio-item ${result.id === state.selectedId ? "is-active" : ""}" type="button" data-result-id="${escapeHtml(result.id)}">
        <span>
          <span class="portfolio-name">${escapeHtml(result.site.business_name)}</span>
          <span class="portfolio-service">${escapeHtml(descriptor)}</span>
          <span class="priority-line"><i class="priority-pip ${priority}"></i>${escapeHtml(priorityLabel(result))} | ${result.issues.length} ${siteAudit ? "issue groups" : "issues"}</span>
        </span>
        <span class="portfolio-score" title="Readiness score">${result.score}</span>
      </button>`;
  }).join("");
}

function metric(label, value, tone = "") {
  return `<div class="metric"><div class="metric-topline"><span>${escapeHtml(label)}</span></div><div class="metric-value ${tone}">${escapeHtml(value)}</div></div>`;
}

function renderMetrics(result) {
  const siteAudit = result.audit_type === "site";
  const priority = highestPriority(result);
  const priorityTone = priority === "critical" ? "bad" : priority === "high" ? "warn" : priority === "clean" ? "good" : "";
  const scoreTone = result.score >= 80 ? "good" : result.score < 50 ? "bad" : "warn";
  const indexable = siteAudit ? result.facts.noindex_pages === 0 : result.facts.indexable;
  const indexTone = indexable ? "good" : "bad";
  els.metrics.innerHTML = [
    metric("Readiness score", `${result.score}/100`, scoreTone),
    metric("Highest priority", priority === "clean" ? "Clear" : sentenceCase(priority), priorityTone),
    metric(siteAudit ? "Pages analyzed" : "Open issues", siteAudit ? result.facts.pages_analyzed : result.issues.length),
    metric("Indexability", siteAudit ? `${result.facts.indexable_pages}/${result.facts.pages_analyzed} indexable` : (indexable ? "Indexable" : "Blocked"), indexTone),
  ].join("");
}

function renderIssue(issue) {
  const affected = issue.affected_pages?.length ? `
    <div class="affected-pages">
      ${issue.affected_pages.slice(0, 5).map((page) => `
        <div class="affected-page">
          <span>${escapeHtml(sentenceCase(page.page_type))}</span>
          <a href="${escapeHtml(page.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(page.page_title || page.url)}</a>
          <strong>${escapeHtml(page.page_score)}</strong>
        </div>`).join("")}
      ${issue.affected_pages.length > 5 ? `<div class="affected-page"><span></span><span>+${issue.affected_pages.length - 5} more pages</span><span></span></div>` : ""}
    </div>` : "";
  return `
    <article class="issue-card ${escapeHtml(issue.severity)}">
      <div class="issue-topline">
        <div class="issue-title-group">
          <div class="issue-category">${escapeHtml(issue.category)}</div>
          <h3>${escapeHtml(issue.title)}</h3>
        </div>
        <span class="badge ${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)}</span>
      </div>
      <div class="issue-copy">
        <p><span class="copy-label">Evidence</span>${escapeHtml(issue.evidence)}</p>
        <p><span class="copy-label">Recommended action</span>${escapeHtml(issue.recommendation)}</p>
      </div>
      <div class="issue-meta">
        <span>Impact: ${escapeHtml(issue.impact)}</span>
        <span>Effort: ${escapeHtml(issue.effort)}</span>
        <span>Confidence: ${escapeHtml(issue.confidence)}</span>
        <span>ID: ${escapeHtml(issue.id)}</span>
      </div>
      ${affected}
    </article>`;
}

function renderOverview(result) {
  const aiSummary = result.ai.status === "complete" ? result.ai.result.executive_summary : "";
  const issues = result.issues.length
    ? result.issues.map(renderIssue).join("")
    : '<div class="clean-state">No material issue was found by the automated checks.</div>';
  return `
    ${aiSummary ? `<div class="summary-strip">${escapeHtml(aiSummary)}</div>` : ""}
    <div class="queue-header">
      <h3>Prioritized findings</h3>
      <p>${result.audit_type === "site" ? "Grouped across affected pages" : "Sorted by severity and evidence confidence"}</p>
    </div>
    <div class="issue-list">${issues}</div>`;
}

function evidenceValue(value) {
  if (Array.isArray(value)) return value.length ? value.join(" | ") : "None detected";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === "") return "Not detected";
  return value;
}

function evidenceItem(label, value) {
  return `<div class="evidence-item"><div class="evidence-label">${escapeHtml(label)}</div><div class="evidence-value">${escapeHtml(evidenceValue(value))}</div></div>`;
}

function renderEvidence(result) {
  const facts = result.facts;
  if (result.audit_type === "site") {
    const items = [
      ["Discovery", facts.discovery.method],
      ["Eligible URLs", facts.pages_discovered],
      ["Pages analyzed", facts.pages_analyzed],
      ["Fetch failures", facts.pages_failed],
      ["Indexable pages", facts.indexable_pages],
      ["Noindex pages", facts.noindex_pages],
      ["Missing titles", facts.missing_titles],
      ["Missing descriptions", facts.missing_descriptions],
      ["Missing canonicals", facts.missing_canonicals],
      ["Images without usable alt", `${facts.images_without_alt}/${facts.images}`],
      ["Page types", Object.entries(facts.page_types).map(([key, value]) => `${key}: ${value}`)],
      ["Crawl limited", facts.discovery.limit_reached],
    ];
    const rows = result.pages.map((page) => `
      <tr>
        <td><span class="score-chip">${escapeHtml(page.score)}</span></td>
        <td>${escapeHtml(sentenceCase(page.page_type))}</td>
        <td><span class="inventory-page">${escapeHtml(page.facts.title || "Untitled page")}</span><a class="inventory-url" href="${escapeHtml(page.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(page.url)}</a></td>
        <td>${page.issues.length}</td>
        <td>${page.facts.indexable ? "Yes" : "No"}</td>
      </tr>`).join("");
    return `
      <div class="evidence-header"><h3>Crawl summary</h3><p>${Number(result.source.bytes).toLocaleString()} HTML bytes analyzed</p></div>
      <div class="evidence-grid">${items.map(([label, value]) => evidenceItem(label, value)).join("")}</div>
      <div class="evidence-header" style="margin-top:22px"><h3>Page inventory</h3><p>${result.pages.length} pages</p></div>
      <div class="inventory-wrap"><table class="inventory-table"><thead><tr><th>Score</th><th>Type</th><th>Page</th><th>Issues</th><th>Indexable</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  const items = [
    ["Title", facts.title],
    ["Title length", facts.title_length],
    ["Meta description", facts.meta_description],
    ["Description length", facts.meta_description_length],
    ["H1 headings", facts.h1s],
    ["Canonical", facts.canonical],
    ["Robots meta", facts.robots],
    ["Schema types", facts.schema_types],
    ["JSON-LD blocks", facts.json_ld_blocks],
    ["LocalBusiness schema", facts.has_local_business_schema],
    ["Structured address", facts.has_address_schema],
    ["Visible word count", facts.word_count],
    ["Internal links", facts.internal_links],
    ["Images", facts.images],
    ["Images without usable alt", facts.images_without_alt],
    ["Clickable phone", facts.has_phone_link],
    [`${result.site.city} in title`, facts.city_in_title],
    [`${result.site.city} in body`, facts.city_in_body],
    [`${result.site.service} in title`, facts.service_in_title],
    [`${result.site.service} in H1`, facts.service_in_h1],
  ];
  return `
    <div class="evidence-header">
      <h3>Extracted page facts</h3>
      <p>HTTP ${escapeHtml(result.source.status)} | ${Number(result.source.bytes).toLocaleString()} bytes</p>
    </div>
    <div class="evidence-grid">${items.map(([label, value]) => evidenceItem(label, value)).join("")}</div>`;
}

function renderAiAction(action, index) {
  return `
    <article class="ai-action">
      <div class="ai-action-heading"><span class="ai-action-number">${index + 1}</span><h3>${escapeHtml(action.title)}</h3></div>
      <div class="ai-action-copy">
        <p><span class="copy-label">Why now</span>${escapeHtml(action.why)}</p>
        <p><span class="copy-label">Implementation</span>${escapeHtml(action.steps)}</p>
      </div>
      <div class="evidence-ids">${action.evidence_ids.map((id) => `<span class="evidence-id">${escapeHtml(id)}</span>`).join("")}</div>
    </article>`;
}

function renderAi(result) {
  if (result.ai.status === "unavailable") {
    return `<div class="notice error"><strong>Claude synthesis unavailable.</strong><br>${escapeHtml(result.ai.error)}</div>`;
  }
  if (result.ai.status !== "complete") {
    const button = state.aiConfigured
      ? '<button id="run-claude-button" class="button button-primary" type="button">Run Claude synthesis</button>'
      : "";
    return `<div class="notice"><strong>Rules-only audit.</strong><br>No AI request was made for this run. ${button}</div>`;
  }

  const ai = result.ai.result;
  const metadataTarget = result.audit_type === "site" ? "homepage " : "";
  const modeLabel = result.ai.mode === "reference_demo" ? "Reference output | offline" : result.ai.model;
  const actions = ai.priority_actions.length
    ? ai.priority_actions.map(renderAiAction).join("")
    : '<div class="clean-state">Claude did not recommend speculative work from the supplied evidence.</div>';
  return `
    <div class="ai-header">
      <div class="ai-title-row"><h3>Grounded synthesis</h3><span class="model-badge">${escapeHtml(modeLabel)}</span></div>
      <p class="ai-summary">${escapeHtml(ai.executive_summary)}</p>
    </div>
    <div class="ai-actions">${actions}</div>
    <div class="metadata-panel">
      <div class="metadata-field">
        <span class="copy-label">Proposed ${metadataTarget}title | <span class="char-count ${ai.metadata.title_within_limit ? "" : "over"}">${ai.metadata.title_length}/60</span></span>
        <p>${escapeHtml(ai.metadata.title)}</p>
      </div>
      <div class="metadata-field">
        <span class="copy-label">Proposed ${metadataTarget}description | <span class="char-count ${ai.metadata.description_within_limit ? "" : "over"}">${ai.metadata.description_length}/155</span></span>
        <p>${escapeHtml(ai.metadata.description)}</p>
      </div>
    </div>
    <div class="human-panel">
      <div><h3>Human verification queue</h3><ul class="human-checks">${ai.human_checks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>
      <div><h3>Scale path</h3><p class="scale-note">${escapeHtml(ai.scale_note)}</p></div>
    </div>
    ${result.ai.mode === "reference_demo" && state.aiConfigured ? '<div style="margin-top:16px"><button id="run-claude-button" class="button button-primary" type="button">Re-run with live Claude</button></div>' : ""}`;
}

function selectedResult() {
  return state.results.find((result) => result.id === state.selectedId);
}

function selectedProject() {
  return state.projects.find((project) => project.id === state.selectedProjectId);
}

function projectRootUrl(result) {
  try {
    return new URL(result.site.url).origin;
  } catch {
    return result.site.url;
  }
}

function auditMatchesProject(result, project) {
  if (!result || !project) return false;
  if (String(result.site.business_name || "").trim().toLowerCase() === String(project.business_name || "").trim().toLowerCase()) {
    return true;
  }
  try {
    return new URL(result.site.url).hostname.toLowerCase() === new URL(project.site_url).hostname.toLowerCase();
  } catch {
    return false;
  }
}

function renderProjectList() {
  els.projectsCount.textContent = state.projects.length;
  if (!state.projects.length) {
    els.projectsList.innerHTML = '<div class="portfolio-empty">No saved projects.</div>';
    return;
  }
  els.projectsList.innerHTML = state.projects.map((project) => `
    <button class="project-list-item ${project.id === state.selectedProjectId ? "is-active" : ""}" type="button" data-project-id="${escapeHtml(project.id)}">
      <span class="project-list-name">${escapeHtml(project.name)}</span>
      <span class="project-list-meta">${escapeHtml(project.business_name)}${project.city ? ` | ${escapeHtml(project.city)}` : ""}</span>
      <span class="project-list-meta">${project.audits.length} audit${project.audits.length === 1 ? "" : "s"} | ${project.connectors.filter((item) => item.connected).length}/3 sources</span>
    </button>`).join("");
}

function connectorMarkup(connector) {
  const stateLabel = connector.connected ? "Authorized" : connector.configured ? "Not connected" : "OAuth setup needed";
  const button = connector.connected
    ? `<button class="button button-secondary button-small" type="button" data-disconnect-source="${escapeHtml(connector.id)}">Disconnect</button>`
    : `<button class="button button-project button-small" type="button" data-connect-source="${escapeHtml(connector.id)}" ${connector.configured ? "" : "disabled"}>Connect</button>`;
  return `
    <article class="connector-item">
      <span class="connector-mark">${escapeHtml(connector.short_label)}</span>
      <div class="connector-copy">
        <strong>${escapeHtml(connector.label)}</strong>
        <span>${connector.connected ? `Authorized ${new Date(connector.connected_at).toLocaleDateString()}` : "Google account authorization"}</span>
      </div>
      <div class="connector-actions">
        <span class="connection-state ${connector.connected ? "connected" : ""}">${escapeHtml(stateLabel)}</span>
        ${button}
      </div>
    </article>`;
}

function projectRecommendationMarkup(action) {
  const pages = Array.isArray(action.affected_pages) ? action.affected_pages : [];
  const affected = action.affected_count ? `
    <div class="project-affected-pages">
      <div class="project-affected-heading">
        <span>Affected pages</span>
        <strong>${escapeHtml(action.affected_count)}</strong>
      </div>
      ${pages.map((page) => `
        <a href="${escapeHtml(page.url)}" target="_blank" rel="noopener noreferrer">
          <span>${escapeHtml(page.title || page.url)}</span>
          <small>${escapeHtml(sentenceCase(page.page_type))} | ${escapeHtml(page.score)}/100</small>
        </a>`).join("")}
      ${action.affected_count > pages.length ? `<div class="project-more-pages">+${escapeHtml(action.affected_count - pages.length)} more affected page${action.affected_count - pages.length === 1 ? "" : "s"}</div>` : ""}
    </div>` : "";
  return `
    <article class="project-recommendation ${escapeHtml(action.severity)}">
      <div class="project-recommendation-rank" aria-label="Priority ${escapeHtml(action.rank)}">${escapeHtml(action.rank)}</div>
      <div class="project-recommendation-copy">
        <div class="project-recommendation-title">
          <h4>${escapeHtml(action.title)}</h4>
          <div>
            <span class="badge ${escapeHtml(action.severity)}">${escapeHtml(action.severity)}</span>
            ${action.effort ? `<span class="project-effort">${escapeHtml(action.effort)} effort</span>` : ""}
          </div>
        </div>
        ${action.why ? `<p>${escapeHtml(action.why)}</p>` : ""}
        ${action.steps ? `<div class="project-action"><span>Next action</span><strong>${escapeHtml(action.steps)}</strong></div>` : ""}
        ${affected}
      </div>
    </article>`;
}

function renderProjectRecommendations(project) {
  if (state.projectDashboardLoading.has(project.id)) {
    return `
      <section class="project-recommendations">
        <div class="connections-heading"><h3>Recommended next steps</h3><p>Latest saved audit</p></div>
        <div class="project-dashboard-state">Loading recommendations...</div>
      </section>`;
  }
  if (state.projectDashboardErrors[project.id]) {
    return `
      <section class="project-recommendations">
        <div class="connections-heading"><h3>Recommended next steps</h3><p>Latest saved audit</p></div>
        <div class="project-dashboard-state error">${escapeHtml(state.projectDashboardErrors[project.id])}</div>
      </section>`;
  }
  const dashboard = state.projectDashboards[project.id];
  if (!dashboard || !dashboard.audit) {
    return `
      <section class="project-recommendations">
        <div class="connections-heading"><h3>Recommended next steps</h3><p>Latest saved audit</p></div>
        <div class="project-dashboard-state">${escapeHtml(dashboard?.summary || "Save an audit to this project to see prioritized suggestions here.")}</div>
      </section>`;
  }

  const source = dashboard.recommendation_source === "claude" ? "Claude + audit evidence" : "Audit evidence";
  const auditDate = dashboard.audit.created_at
    ? new Date(dashboard.audit.created_at).toLocaleDateString()
    : "Latest snapshot";
  const actions = dashboard.actions.length
    ? dashboard.actions.map(projectRecommendationMarkup).join("")
    : '<div class="project-dashboard-state clean">No open recommendations in the latest audit.</div>';
  const checks = dashboard.human_checks.length ? `
    <details class="project-human-checks">
      <summary>Human review checks <span>${dashboard.human_checks.length}</span></summary>
      <ul>${dashboard.human_checks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </details>` : "";
  return `
    <section class="project-recommendations">
      <div class="connections-heading">
        <h3>Recommended next steps</h3>
        <p>${escapeHtml(source)} | ${escapeHtml(auditDate)}</p>
      </div>
      <p class="project-executive-summary">${escapeHtml(dashboard.summary)}</p>
      ${dashboard.scale_note ? `<p class="project-scale-note"><strong>At scale</strong>${escapeHtml(dashboard.scale_note)}</p>` : ""}
      <div class="project-recommendation-list">${actions}</div>
      ${checks}
    </section>`;
}

function renderProjectDetail() {
  const project = selectedProject();
  if (!project) {
    els.projectDetail.innerHTML = `
      <div class="project-empty">
        <strong>Create a project to organize audits</strong>
        <span>Project-level Google connections become available after the project is created.</span>
      </div>`;
    return;
  }
  const current = selectedResult();
  const containsCurrent = current && project.audits.some((audit) => audit.id === current.id);
  const addButton = current && auditMatchesProject(current, project) ? `
    <button class="button button-project" type="button" data-add-audit="${escapeHtml(project.id)}">
      ${containsCurrent ? "Update audit snapshot" : "Add current audit"}
    </button>` : "";
  const latest = project.audits[0];
  const dashboardAudit = state.projectDashboards[project.id]?.audit;
  const selectedAuditId = dashboardAudit?.id;
  const auditRows = project.audits.length ? project.audits.map((audit) => `
    <button class="project-audit-row ${audit.id === selectedAuditId ? "is-active" : ""}" type="button" data-project-audit="${escapeHtml(audit.id)}">
      <span><strong>${escapeHtml(audit.audit_type === "site" ? "Site crawl" : "Page audit")}</strong><small>${audit.created_at ? escapeHtml(new Date(audit.created_at).toLocaleDateString()) : "Saved snapshot"}</small></span>
      <span>${escapeHtml(audit.score)}/100</span>
      <span>${escapeHtml(audit.page_count)} page${audit.page_count === 1 ? "" : "s"}</span>
    </button>`).join("") : '<div class="portfolio-empty">No audits saved to this project.</div>';
  els.projectDetail.innerHTML = `
    <div class="project-detail-header">
      <div>
        <p class="eyebrow">${escapeHtml(project.city || "Project")}</p>
        <h3>${escapeHtml(project.name)}</h3>
        <a class="project-domain" href="${escapeHtml(project.site_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(project.site_url)}</a>
      </div>
      ${addButton}
    </div>
    <div class="project-stats">
      <div class="project-stat"><span>Saved audits</span><strong>${project.audits.length}</strong></div>
      <div class="project-stat"><span>Audit score</span><strong>${dashboardAudit ? `${escapeHtml(dashboardAudit.score)}/100` : latest ? `${escapeHtml(latest.score)}/100` : "-"}</strong></div>
      <div class="project-stat"><span>Data sources</span><strong>${project.connectors.filter((item) => item.connected).length}/3</strong></div>
    </div>
    ${renderProjectRecommendations(project)}
    <div class="connections-heading">
      <h3>Google data sources</h3>
      <p>Authorization only; property mapping follows connection</p>
    </div>
    <div class="connector-list">${project.connectors.map(connectorMarkup).join("")}</div>
    <div class="project-audits">
      <div class="connections-heading"><h3>Audit history</h3><p>Saved snapshots</p></div>
      ${auditRows}
    </div>`;
}

function renderProjects() {
  renderProjectList();
  renderProjectDetail();
}

async function loadProjectDashboard(projectId, force = false, auditId = "") {
  if (!projectId || state.projectDashboardLoading.has(projectId)) return;
  if (!force && state.projectDashboards[projectId]) return;
  state.projectDashboardLoading.add(projectId);
  delete state.projectDashboardErrors[projectId];
  if (state.selectedProjectId === projectId) renderProjectDetail();
  try {
    const query = auditId ? `?audit_id=${encodeURIComponent(auditId)}` : "";
    const data = await request(`/api/projects/${encodeURIComponent(projectId)}/dashboard${query}`);
    state.projectDashboards[projectId] = data.dashboard;
  } catch (error) {
    state.projectDashboardErrors[projectId] = error.message;
  } finally {
    state.projectDashboardLoading.delete(projectId);
    if (state.selectedProjectId === projectId) renderProjectDetail();
  }
}

async function loadProjects() {
  const data = await request("/api/projects");
  state.projects = data.projects;
  if (!state.projects.some((project) => project.id === state.selectedProjectId)) {
    state.selectedProjectId = state.projects[0]?.id || null;
  }
  renderProjects();
  await loadProjectDashboard(state.selectedProjectId, true);
}

function keywordVolumeChange(record) {
  const current = Number(record.latest.search_volume || 0);
  if (record.previous_search_volume == null) return {label: "-", tone: ""};
  const change = current - Number(record.previous_search_volume || 0);
  return {
    label: `${change > 0 ? "+" : ""}${change.toLocaleString()}`,
    tone: change > 0 ? "up" : change < 0 ? "down" : "",
  };
}

function renderKeywords() {
  els.keywordsCount.textContent = state.keywords.length;
  els.monitoredKeywordsCount.textContent = state.keywords.length;
  els.keywordsEmpty.hidden = state.keywords.length > 0;
  els.exportKeywordsButton.disabled = state.keywordLoading || !state.keywords.length;
  els.refreshKeywordsButton.disabled = state.keywordLoading || !state.selectedKeywordIds.size;
  els.keywordsTableBody.innerHTML = state.keywords.map((record) => {
    const latest = record.latest || {};
    const change = keywordVolumeChange(record);
    const updated = record.updated_at ? new Date(record.updated_at).toLocaleDateString() : "-";
    const difficulty = latest.keyword_difficulty == null ? "-" : Number(latest.keyword_difficulty).toFixed(0);
    const cpc = latest.cpc_usd == null ? "-" : `$${Number(latest.cpc_usd).toFixed(2)}`;
    const intents = Array.isArray(latest.intents) && latest.intents.length
      ? latest.intents.map(sentenceCase).join(", ")
      : "-";
    return `
      <tr>
        <td class="keyword-check"><input type="checkbox" aria-label="Select ${escapeHtml(record.keyword)}" data-keyword-select="${escapeHtml(record.id)}" ${state.selectedKeywordIds.has(record.id) ? "checked" : ""}></td>
        <td><strong>${escapeHtml(record.keyword)}</strong><span>${escapeHtml(latest.month || "Latest snapshot")}</span></td>
        <td>${escapeHtml(record.country)}</td>
        <td class="keyword-number">${Number(latest.search_volume || 0).toLocaleString()}</td>
        <td><span class="keyword-change ${change.tone}">${escapeHtml(change.label)}</span></td>
        <td>${escapeHtml(difficulty)}</td>
        <td>${escapeHtml(cpc)}</td>
        <td>${escapeHtml(intents)}</td>
        <td>${escapeHtml(updated)}</td>
        <td><button class="keyword-remove" type="button" data-keyword-remove="${escapeHtml(record.id)}" aria-label="Remove ${escapeHtml(record.keyword)}" title="Remove keyword">&times;</button></td>
      </tr>`;
  }).join("");
}

function showKeywordNotice(message, error = false) {
  els.keywordsNotice.textContent = message;
  els.keywordsNotice.hidden = !message;
  els.keywordsNotice.classList.toggle("error", error);
}

function setKeywordLoading(loading, label = "Research (20 units each)") {
  state.keywordLoading = loading;
  els.researchKeywordsButton.disabled = loading || !state.semrushConfigured;
  els.researchKeywordsButton.textContent = loading ? "Fetching metrics..." : label;
  renderKeywords();
}

async function loadKeywords() {
  const data = await request("/api/keywords");
  state.keywords = data.records;
  state.semrushConfigured = Boolean(data.semrush_configured);
  state.selectedKeywordIds = new Set(
    [...state.selectedKeywordIds].filter((id) => state.keywords.some((record) => record.id === id))
  );
  if (!state.semrushConfigured) {
    showKeywordNotice("Semrush keyword research is not configured.", true);
  }
  setKeywordLoading(false);
}

async function researchKeywords(event) {
  event.preventDefault();
  showKeywordNotice("");
  setKeywordLoading(true);
  try {
    const data = await request("/api/keywords/research", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        keywords: els.keywordsInput.value,
        country: els.keywordsCountry.value,
      }),
    });
    state.keywords = data.records;
    els.keywordsInput.value = "";
    renderKeywords();
    toast(`${data.updated.length} keyword${data.updated.length === 1 ? "" : "s"} updated.`);
  } catch (error) {
    showKeywordNotice(error.message, true);
  } finally {
    setKeywordLoading(false);
  }
}

async function refreshKeywords() {
  if (!state.selectedKeywordIds.size) return;
  showKeywordNotice("");
  setKeywordLoading(true);
  try {
    const data = await request("/api/keywords/refresh", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ids: [...state.selectedKeywordIds]}),
    });
    state.keywords = data.records;
    renderKeywords();
    toast(`${data.updated.length} volume snapshot${data.updated.length === 1 ? "" : "s"} saved.`);
  } catch (error) {
    showKeywordNotice(error.message, true);
  } finally {
    setKeywordLoading(false);
  }
}

async function removeKeyword(recordId) {
  try {
    const data = await request("/api/keywords/delete", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({id: recordId}),
    });
    state.keywords = data.records;
    state.selectedKeywordIds.delete(recordId);
    renderKeywords();
    toast("Keyword removed.");
  } catch (error) {
    showKeywordNotice(error.message, true);
  }
}

function exportKeywordCsv() {
  if (!state.keywords.length) return;
  const columns = ["keyword", "country", "month", "search_volume", "volume_change", "keyword_difficulty", "cpc_usd", "competitive_density", "intents", "updated_at"];
  const rows = state.keywords.map((record) => ({
    keyword: record.keyword,
    country: record.country,
    month: record.latest.month || "",
    search_volume: record.latest.search_volume ?? "",
    volume_change: record.previous_search_volume == null ? "" : Number(record.latest.search_volume || 0) - Number(record.previous_search_volume),
    keyword_difficulty: record.latest.keyword_difficulty ?? "",
    cpc_usd: record.latest.cpc_usd ?? "",
    competitive_density: record.latest.competitive_density ?? "",
    intents: Array.isArray(record.latest.intents) ? record.latest.intents.join(" | ") : "",
    updated_at: record.updated_at,
  }));
  const csv = [columns.join(","), ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(","))].join("\r\n");
  downloadBlob(new Blob(["\ufeff" + csv], {type: "text/csv;charset=utf-8"}), "locallift-keyword-monitor.csv");
  toast("Keyword CSV exported.");
}

function showProjectForm(prefill = true) {
  const result = prefill ? selectedResult() : null;
  els.projectName.value = result ? result.site.business_name : "";
  els.projectBusiness.value = result ? result.site.business_name : "";
  els.projectCity.value = result ? result.site.city : "";
  els.projectUrl.value = result ? projectRootUrl(result) : "";
  els.projectCreatePanel.hidden = false;
  els.projectName.focus();
}

async function openProjects(addCurrent = false) {
  state.pendingAuditAdd = addCurrent && Boolean(selectedResult());
  if (!els.projectsDialog.open) els.projectsDialog.showModal();
  try {
    await loadProjects();
    if (state.pendingAuditAdd) {
      const current = selectedResult();
      const root = projectRootUrl(current);
      const match = state.projects.find((project) => project.site_url === root || project.business_name === current.site.business_name);
      if (match) {
        state.selectedProjectId = match.id;
        renderProjects();
        await loadProjectDashboard(match.id);
      } else {
        showProjectForm(true);
      }
    }
  } catch (error) {
    toast(error.message);
  }
  try {
    await loadKeywords();
  } catch (error) {
    showKeywordNotice(error.message, true);
  }
}

async function addAuditToProject(projectId) {
  const result = selectedResult();
  if (!result) return;
  const data = await request(`/api/projects/${encodeURIComponent(projectId)}/audits`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({result}),
  });
  const index = state.projects.findIndex((project) => project.id === data.project.id);
  if (index >= 0) state.projects[index] = data.project;
  else state.projects.unshift(data.project);
  state.selectedProjectId = data.project.id;
  state.pendingAuditAdd = false;
  renderProjects();
  await loadProjectDashboard(data.project.id, true, result.id);
  toast("Audit saved to project.");
}

async function createProject(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(els.projectForm).entries());
  try {
    const data = await request("/api/projects", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    state.projects.unshift(data.project);
    state.selectedProjectId = data.project.id;
    els.projectCreatePanel.hidden = true;
    renderProjects();
    if (state.pendingAuditAdd) await addAuditToProject(data.project.id);
    else toast("Project created.");
  } catch (error) {
    toast(error.message);
  }
}

async function connectGoogle(source) {
  const project = selectedProject();
  if (!project) return;
  const popup = window.open("", "locallift-google-oauth", "popup,width=560,height=720");
  try {
    const data = await request(`/api/projects/${encodeURIComponent(project.id)}/google/connect?source=${encodeURIComponent(source)}`);
    if (popup) popup.location.assign(data.authorization_url);
    else window.location.assign(data.authorization_url);
  } catch (error) {
    if (popup) popup.close();
    toast(error.message);
  }
}

async function disconnectGoogle(source) {
  const project = selectedProject();
  if (!project) return;
  try {
    const data = await request(`/api/projects/${encodeURIComponent(project.id)}/google/disconnect`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({source}),
    });
    const index = state.projects.findIndex((item) => item.id === project.id);
    state.projects[index] = data.project;
    renderProjects();
    toast("Google connection removed.");
  } catch (error) {
    toast(error.message);
  }
}

function renderSelected() {
  const result = selectedResult();
  if (!result) {
    els.emptyState.hidden = false;
    els.resultView.hidden = true;
    return;
  }

  els.emptyState.hidden = true;
  els.resultView.hidden = false;
  els.resultContext.textContent = result.audit_type === "site"
    ? `Site crawl | ${result.site.city} | ${result.facts.pages_analyzed} pages`
    : `${result.site.service} | ${result.site.city}`;
  els.resultTitle.textContent = result.site.business_name;
  els.resultUrl.textContent = result.site.url;
  els.resultUrl.href = result.source.mode === "offline_demo" ? "#" : result.site.url;
  els.resultUrl.removeAttribute("aria-disabled");
  if (result.source.mode === "offline_demo") {
    els.resultUrl.removeAttribute("href");
    els.resultUrl.removeAttribute("target");
    els.resultUrl.setAttribute("aria-disabled", "true");
  } else {
    els.resultUrl.target = "_blank";
  }
  els.sourceBadge.textContent = result.source.mode === "offline_demo"
    ? "Offline demo evidence"
    : result.audit_type === "site" ? "Live site crawl" : "Live page evidence";
  renderMetrics(result);

  if (state.tab === "evidence") els.tabContent.innerHTML = renderEvidence(result);
  else if (state.tab === "ai") els.tabContent.innerHTML = renderAi(result);
  else els.tabContent.innerHTML = renderOverview(result);
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === state.tab;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
}

function render() {
  renderPortfolio();
  renderSelected();
}

function upsertResult(result) {
  const index = state.results.findIndex((item) => item.id === result.id);
  if (index >= 0) state.results[index] = result;
  else state.results.unshift(result);
  state.selectedId = result.id;
}

async function loadDemo() {
  if (state.loading) return;
  setLoading(true);
  try {
    const data = await request("/api/demo");
    state.results = data.results;
    state.selectedId = data.results[0]?.id || null;
    state.tab = "overview";
    render();
    toast("Sample portfolio loaded.");
  } catch (error) {
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

async function analyze(event) {
  event.preventDefault();
  if (state.loading) return;
  const formData = new FormData(els.form);
  const payload = Object.fromEntries(formData.entries());
  payload.use_ai = state.aiConfigured && els.useAi.checked;
  const endpoint = state.scope === "site" ? "/api/crawl" : "/api/analyze";
  setLoading(true);
  try {
    const result = await request(endpoint, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    upsertResult(result);
    state.tab = result.ai.status === "complete" ? "ai" : "overview";
    render();
    if (result.ai.status === "unavailable") toast("Audit complete; Claude was unavailable.");
    else toast(state.scope === "site" ? `${result.facts.pages_analyzed} pages audited.` : "Audit added to the portfolio.");
  } catch (error) {
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

async function runClaudeForSelected() {
  const current = selectedResult();
  if (!current || state.loading) return;
  setLoading(true);
  try {
    const result = await request("/api/synthesize", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({result: current}),
    });
    upsertResult(result);
    render();
    toast(result.ai.status === "complete" ? "Live Claude synthesis complete." : "Claude synthesis was unavailable.");
  } catch (error) {
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

function fileSlug(result) {
  return result.site.business_name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "audit";
}

function downloadBlob(blob, filename) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportSelected() {
  const result = selectedResult();
  if (!result) return;
  downloadBlob(
    new Blob([JSON.stringify(result, null, 2)], {type: "application/json"}),
    `${fileSlug(result)}-locallift.json`,
  );
  toast("Audit JSON exported.");
}

function csvCell(value) {
  const text = Array.isArray(value) ? value.join(" | ") : String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function exportCsv() {
  const result = selectedResult();
  if (!result) return;
  const columns = [
    "business", "city", "site_url", "page_url", "page_type", "page_score", "indexable",
    "severity", "issue_id", "category", "issue", "evidence", "recommendation", "effort", "confidence",
  ];
  const pages = result.audit_type === "site" ? result.pages : [{
    url: result.site.url,
    page_type: "service",
    score: result.score,
    facts: result.facts,
    issues: result.issues,
  }];
  const rows = [];
  pages.forEach((page) => {
    const issues = page.issues.length ? page.issues : [{}];
    issues.forEach((issue) => rows.push({
      business: result.site.business_name,
      city: result.site.city,
      site_url: result.site.url,
      page_url: page.url,
      page_type: page.page_type,
      page_score: page.score,
      indexable: page.facts.indexable ? "yes" : "no",
      severity: issue.severity || "",
      issue_id: issue.id || "",
      category: issue.category || "",
      issue: issue.title || "",
      evidence: issue.evidence || "",
      recommendation: issue.recommendation || "",
      effort: issue.effort || "",
      confidence: issue.confidence || "",
    }));
  });
  const csv = [columns.map(csvCell).join(","), ...rows.map((row) => columns.map((key) => csvCell(row[key])).join(","))].join("\r\n");
  downloadBlob(new Blob(["\ufeff" + csv], {type: "text/csv;charset=utf-8"}), `${fileSlug(result)}-locallift.csv`);
  toast("Audit CSV exported.");
}

async function exportPdf() {
  const result = selectedResult();
  if (!result || state.loading) return;
  setLoading(true);
  els.pdfButton.textContent = "Building PDF...";
  try {
    const response = await fetch("/api/export/pdf", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({result}),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `PDF export returned HTTP ${response.status}.`);
    }
    downloadBlob(await response.blob(), `${fileSlug(result)}-locallift-audit.pdf`);
    toast("Audit PDF exported.");
  } catch (error) {
    toast(error.message);
  } finally {
    els.pdfButton.textContent = "Export PDF";
    setLoading(false);
  }
}

async function boot() {
  const query = new URLSearchParams(window.location.search);
  setScope(query.get("scope"));
  try {
    const health = await request("/api/health");
    els.apiDot.classList.add("is-ok");
    els.apiStatus.textContent = `Service v${health.version}`;
    state.aiConfigured = Boolean(health.ai_configured);
    els.modelStatus.textContent = health.ai_configured ? health.model : "Rules only";
    els.useAi.disabled = !health.ai_configured;
    els.aiToggleWrap.classList.toggle("is-disabled", !health.ai_configured);
    els.aiToggleWrap.title = health.ai_configured ? "Include live Claude synthesis" : "Add ANTHROPIC_API_KEY to enable live synthesis";
  } catch {
    els.apiDot.classList.add("is-error");
    els.apiStatus.textContent = "Service unavailable";
  }
  await loadDemo();
  try {
    await loadProjects();
  } catch (error) {
    toast(error.message);
  }
  if (query.get("view") === "projects") {
    state.pendingAuditAdd = false;
    els.projectsDialog.showModal();
    renderProjects();
  }
  if (query.get("view") === "keywords") {
    els.keywordsDialog.showModal();
    renderKeywords();
  }
}

els.form.addEventListener("submit", analyze);
els.demoButton.addEventListener("click", loadDemo);
els.exportButton.addEventListener("click", exportSelected);
els.csvButton.addEventListener("click", exportCsv);
els.pdfButton.addEventListener("click", exportPdf);
els.keywordsButton.addEventListener("click", () => {
  els.keywordsDialog.showModal();
  renderKeywords();
});
els.closeKeywordsButton.addEventListener("click", () => els.keywordsDialog.close());
els.keywordsForm.addEventListener("submit", researchKeywords);
els.refreshKeywordsButton.addEventListener("click", refreshKeywords);
els.exportKeywordsButton.addEventListener("click", exportKeywordCsv);
els.keywordsTableBody.addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-keyword-select]");
  if (!checkbox) return;
  if (checkbox.checked && state.selectedKeywordIds.size >= 10) {
    checkbox.checked = false;
    toast("Select up to 10 keywords per refresh.");
    return;
  }
  if (checkbox.checked) state.selectedKeywordIds.add(checkbox.dataset.keywordSelect);
  else state.selectedKeywordIds.delete(checkbox.dataset.keywordSelect);
  renderKeywords();
});
els.keywordsTableBody.addEventListener("click", (event) => {
  const button = event.target.closest("[data-keyword-remove]");
  if (button) removeKeyword(button.dataset.keywordRemove);
});
els.keywordsDialog.addEventListener("click", (event) => {
  if (event.target === els.keywordsDialog) els.keywordsDialog.close();
});
els.projectsButton.addEventListener("click", () => openProjects(false));
els.addProjectButton.addEventListener("click", () => openProjects(true));
els.closeProjectsButton.addEventListener("click", () => els.projectsDialog.close());
els.newProjectButton.addEventListener("click", () => showProjectForm(false));
els.cancelProjectButton.addEventListener("click", () => {
  els.projectCreatePanel.hidden = true;
  state.pendingAuditAdd = false;
});
els.projectForm.addEventListener("submit", createProject);
els.projectsList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-project-id]");
  if (!button) return;
  state.selectedProjectId = button.dataset.projectId;
  els.projectCreatePanel.hidden = true;
  renderProjects();
  loadProjectDashboard(state.selectedProjectId).catch((error) => toast(error.message));
});
els.projectDetail.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add-audit]");
  const connectButton = event.target.closest("[data-connect-source]");
  const disconnectButton = event.target.closest("[data-disconnect-source]");
  const auditButton = event.target.closest("[data-project-audit]");
  if (addButton) addAuditToProject(addButton.dataset.addAudit).catch((error) => toast(error.message));
  else if (connectButton) connectGoogle(connectButton.dataset.connectSource);
  else if (disconnectButton) disconnectGoogle(disconnectButton.dataset.disconnectSource);
  else if (auditButton) loadProjectDashboard(state.selectedProjectId, true, auditButton.dataset.projectAudit);
});
els.projectsDialog.addEventListener("click", (event) => {
  if (event.target === els.projectsDialog) els.projectsDialog.close();
});
window.addEventListener("message", async (event) => {
  const current = new URL(window.location.href);
  const allowedOAuthOrigins = new Set([
    window.location.origin,
    `${current.protocol}//localhost${current.port ? `:${current.port}` : ""}`,
    `${current.protocol}//127.0.0.1${current.port ? `:${current.port}` : ""}`,
  ]);
  if (!allowedOAuthOrigins.has(event.origin) || event.data?.type !== "locallift-google-oauth") return;
  toast(event.data.message);
  if (event.data.success) {
    state.selectedProjectId = event.data.project_id;
    await loadProjects();
  }
});
els.scopeOptions.forEach((button) => button.addEventListener("click", () => setScope(button.dataset.scope)));
els.portfolioFilter.addEventListener("change", renderPortfolio);
els.portfolioList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-result-id]");
  if (!button) return;
  state.selectedId = button.dataset.resultId;
  render();
});
document.querySelector(".tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (!tab) return;
  state.tab = tab.dataset.tab;
  renderSelected();
});
els.tabContent.addEventListener("click", (event) => {
  if (event.target.closest("#run-claude-button")) runClaudeForSelected();
});

boot();
