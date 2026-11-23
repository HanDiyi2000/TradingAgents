// FEAT-06: one page driving one local analysis.
// Configuration comes from GET /api/config; a run is started with POST /api/runs
// and followed by polling GET /api/runs/<id>/events?since=<cursor>. The final
// report is served from that run; switching tabs or downloading never re-runs it.

let state = {
  runId: null,
  cursor: 0,
  running: false,
  polling: false,     // a poll request is in flight; at most one at a time
  warned: false,
  seen: new Set(),    // event indexes already rendered, so a slow poll never repeats one
};

const $ = (id) => document.getElementById(id);

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function initForm() {
  const cfg = await getJSON("/api/config");
  const provider = $("provider");
  for (const p of cfg.providers) {
    const o = document.createElement("option");
    o.value = p.value; o.textContent = p.label;
    if (p.value === cfg.default_provider) o.selected = true;
    provider.appendChild(o);
  }
  await refreshModels(cfg.default_provider, cfg.default_quick_think_llm, cfg.default_deep_think_llm);
  const analysts = $("analysts");
  for (const a of cfg.analysts) {
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox"; box.value = a.value; box.checked = a.default !== false;
    if (a.default) box.dataset.default = "1";
    label.appendChild(box); label.appendChild(document.createTextNode(a.label));
    analysts.appendChild(label);
  }
  const depth = $("research_depth");
  for (const d of cfg.depth_options) {
    const o = document.createElement("option");
    o.value = d.value; o.textContent = `${d.label} (${d.value} rounds)`;
    if (d.value === cfg.default_depth) o.selected = true;
    depth.appendChild(o);
  }
  $("output_language").value = cfg.default_output_language || "English";
  $("date").value = todayISO();
}

// Fetch the given provider's quick/deep models and refill both boxes. Called on
// load and on every provider change, because ChatGPT lists its plan's models
// live while other providers use the catalog.
async function refreshModels(provider, defQuick, defDeep) {
  const models = await getJSON("/api/models?provider=" + encodeURIComponent(provider));
  fillModels(models, {
    default_quick_think_llm: defQuick !== undefined ? defQuick : null,
    default_deep_think_llm: defDeep !== undefined ? defDeep : null,
  });
  showModelHint(models);
}

function showModelHint(models) {
  const hint = $("model-hint");
  if (!hint) return;
  let text = "";
  if (models.needs_login) {
    text = "Sign in first: run `tradingagents login chatgpt` in a terminal, then reopen provider selection.";
  } else if (models.error) {
    text = models.error;
  }
  hint.textContent = text;
  hint.hidden = !text;
}

function fillModels(models, cfg) {
  const quick = $("quick_think_llm");
  const deep = $("deep_think_llm");
  quick.innerHTML = ""; deep.innerHTML = "";
  const add = (sel, items, def) => {
    const seen = new Set();
    for (const m of items || []) {
      if (seen.has(m.value)) continue;
      seen.add(m.value);
      const o = document.createElement("option");
      o.value = m.value; o.textContent = m.label || m.value;
      if (m.value === def) o.selected = true;
      sel.appendChild(o);
    }
  };
  add(quick, models.quick, cfg.default_quick_think_llm);
  add(deep, models.deep, cfg.default_deep_think_llm);
  updateStartEnabled();
}

function selectedAnalysts() {
  return Array.from(document.querySelectorAll("#analysts input:checked")).map((b) => b.value);
}

function modelValue(selectId, inputId) {
  const sel = $(selectId);
  if (sel.value === "custom") {
    const input = $(inputId);
    return input ? input.value.trim() : "";
  }
  return sel.value;
}

function collectConfig() {
  return {
    ticker: $("ticker").value.trim(),
    date: $("date").value,
    llm_provider: $("provider").value,
    quick_think_llm: modelValue("quick_think_llm", "quick_custom"),
    deep_think_llm: modelValue("deep_think_llm", "deep_custom"),
    analysts: selectedAnalysts(),
    research_depth: Number($("research_depth").value),
    output_language: $("output_language").value,
  };
}

// Models must be chosen before Start: an empty ID would be submitted as "".
function updateStartEnabled() {
  const quick = modelValue("quick_think_llm", "quick_custom");
  const deep = modelValue("deep_think_llm", "deep_custom");
  const ready = !state.running && quick && deep;
  $("start").disabled = !ready;
  toggleCustomInputs();
}

function toggleCustomInputs() {
  const show = (selId, inputId) => {
    const input = $(inputId);
    if (input) input.hidden = $(selId).value !== "custom";
  };
  show("quick_think_llm", "quick_custom");
  show("deep_think_llm", "deep_custom");
}

function setRunning(running) {
  state.running = running;
  $("start").textContent = running ? "Analysis running…" : "Start analysis";
  updateStartEnabled();
}

function resetViews() {
  $("events").innerHTML = "";
  $("empty").hidden = false;
  $("tab-report").disabled = true;
  $("download").hidden = true;
  $("status").textContent = "";
  $("status").className = "status";
  showTab("progress");
  state.warned = false;
  state.cursor = 0;
  state.seen = new Set();
  state.polling = false;
}

function showTab(which) {
  const progress = which === "progress";
  $("tab-progress").classList.toggle("active", progress);
  $("tab-report").classList.toggle("active", !progress);
  $("view-progress").hidden = !progress;
  $("view-report").hidden = progress;
}

// Short messages read inline; long text, tool output and report bodies start
// collapsed to "role/report name + one-line preview" and expand on click. Token
// warnings, errors and the debate's early-stop reason are always shown in full.
const COLLAPSE_CHARS = 140;
const ALWAYS_OPEN = new Set(["token_warning", "error", "delegate"]);

function eventText(ev) {
  if (ev.kind === "tool") {
    return `${ev.name || "tool"}(${JSON.stringify(ev.args || {})})`;
  }
  return ev.text || "";
}

function isCollapsible(ev, text) {
  if (ALWAYS_OPEN.has(ev.kind)) return false;
  if (ev.kind === "tool" || ev.kind === "report") return true;
  return text.length > COLLAPSE_CHARS || text.includes("\n");
}

function addEvent(ev) {
  if (ev.kind === "status") return; // statuses drive the counter, not the log
  if (ev.index != null) {
    if (state.seen.has(ev.index)) return; // a repeated/late poll never re-renders
    state.seen.add(ev.index);
  }
  const list = $("events");
  const stick = shouldStickToBottom();

  if (ev.kind === "token_warning") {
    if (state.warned) return; // one warning only
    state.warned = true;
    const li = document.createElement("li");
    li.className = "kind-token_warning";
    li.textContent = `Token usage warning: ${Number(ev.total_tokens).toLocaleString()} used (threshold ${Number(ev.threshold).toLocaleString()})`;
    appendSticky(list, li, stick);
    return;
  }

  const text = eventText(ev);
  const li = document.createElement("li");
  li.className = "kind-" + (ev.kind || "message");
  const roleText = ev.role || ev.section || ev.kind || "";

  if (isCollapsible(ev, text)) {
    li.classList.add("collapsible", "collapsed");
    const summary = document.createElement("button");
    summary.type = "button";
    summary.className = "event-summary";
    const name = document.createElement("span");
    name.className = "role";
    name.textContent = roleText;
    const preview = document.createElement("span");
    preview.className = "preview";
    preview.textContent = oneLine(text, 120);
    summary.appendChild(name);
    summary.appendChild(preview);
    const body = document.createElement("div");
    body.className = "event-body";
    body.textContent = text;
    summary.addEventListener("click", () => {
      // Keep the clicked item under the cursor while it grows/shrinks.
      li.classList.toggle("collapsed");
    });
    li.appendChild(summary);
    li.appendChild(body);
  } else {
    const role = document.createElement("span");
    role.className = "role";
    role.textContent = roleText;
    li.appendChild(role);
    li.appendChild(document.createTextNode(text));
  }
  appendSticky(list, li, stick);
  $("empty").hidden = true;
}

function oneLine(text, max) {
  const flat = String(text || "").replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max - 1) + "…" : flat;
}

// Only auto-scroll when the reader is already near the bottom; a reader who
// scrolled up (or is expanding an older item) keeps their place.
function shouldStickToBottom() {
  const view = $("view-progress");
  return view.scrollHeight - view.scrollTop - view.clientHeight < 48;
}

function appendSticky(list, li, stick) {
  list.appendChild(li);
  if (stick) {
    const view = $("view-progress");
    view.scrollTop = view.scrollHeight;
  }
}

// One poll at a time: each request runs only after the previous finished, so a
// slow response can never overlap and duplicate output. Events are appended by
// run_id + cursor; the run's terminal state switches the view only after the
// final batch has been read.
async function poll() {
  if (!state.runId || state.polling) return;
  state.polling = true;
  try {
    const data = await getJSON(`/api/runs/${state.runId}/events?since=${state.cursor}`);
    for (const ev of data.events) addEvent(ev);
    state.cursor = data.next;

    const st = await getJSON(`/api/runs/${state.runId}/status`);
    if (st.state === "succeeded" || st.state === "failed") {
      // Drain any events that landed with the terminal state before switching.
      const tail = await getJSON(`/api/runs/${state.runId}/events?since=${state.cursor}`);
      for (const ev of tail.events) addEvent(ev);
      state.cursor = tail.next;
      if (st.state === "succeeded") {
        await finishSuccess();
      } else {
        finishFailure(st.error || "Analysis failed.");
      }
      return; // finished; no further polling
    }
  } catch (err) {
    // Transient read failure: keep going; the run continues server-side.
    console.warn("poll error", err);
  } finally {
    state.polling = false;
  }
  if (state.running) {
    setTimeout(poll, 700);
  }
}

async function finishSuccess() {
  const res = await fetch(`/api/runs/${state.runId}/report`);
  const html = await res.text();
  const frame = $("report-frame");
  frame.srcdoc = html;
  $("report-meta").textContent = reportMeta(html);
  $("download").href = `/api/runs/${state.runId}/report.md`;
  $("download").hidden = false;
  $("tab-report").disabled = false;
  $("status").className = "status";
  $("status").textContent = "Analysis complete.";
  setRunning(false);
  showTab("report");
}

function reportMeta(html) {
  // Derive ticker/date/rating from the exported report header when possible.
  const text = html;
  const pick = (label) => {
    const m = text.match(new RegExp(label + ":\\s*([^<\\n]+)"));
    return m ? m[1].trim() : "";
  };
  const ticker = pick("Trading Analysis Report");
  const date = pick("Analysis date");
  const rating = pick("Rating");
  const parts = [];
  if (state.ticker) parts.push(state.ticker);
  if (state.date) parts.push(state.date);
  if (rating) parts.push(`Rating: ${rating}`);
  return parts.join("  ·  ");
}

function finishFailure(message) {
  setRunning(false);
  const status = $("status");
  status.className = "status failed";
  status.textContent = "Analysis failed: " + message;
  // Keep the process log and the form; the user can retry.
}

async function startAnalysis(event) {
  event.preventDefault();
  if (state.running) return; // guard rapid double-clicks
  const config = collectConfig();
  if (!config.ticker) {
    $("config-error").textContent = "Enter a stock code.";
    return;
  }
  if (config.analysts.length === 0) {
    $("config-error").textContent = "Select at least one analyst.";
    return;
  }
  $("config-error").textContent = "";
  resetViews();
  state.ticker = config.ticker;
  state.date = config.date;
  setRunning(true);
  try {
    const started = await postJSON("/api/runs", config);
    state.runId = started.run_id;
    state.cursor = 0;
    poll(); // single self-scheduling loop; no interval to overlap requests
  } catch (err) {
    finishFailure(err.message || String(err));
  }
}

$("config-form").addEventListener("submit", startAnalysis);
$("tab-progress").addEventListener("click", () => showTab("progress"));
$("tab-report").addEventListener("click", () => { if (!$("tab-report").disabled) showTab("report"); });

// Switching provider refreshes both model boxes for that provider's models.
$("provider").addEventListener("change", async (e) => {
  await refreshModels(e.target.value);
});
$("quick_think_llm").addEventListener("change", updateStartEnabled);
$("deep_think_llm").addEventListener("change", updateStartEnabled);
$("quick_custom").addEventListener("input", updateStartEnabled);
$("deep_custom").addEventListener("input", updateStartEnabled);

initForm();
