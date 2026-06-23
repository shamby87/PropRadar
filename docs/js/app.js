// PropRadar dashboard: fetch exported stats and render the active platform tab.

const DATA_URL = "data/stats.json";
let DASHBOARD_DATA = null;
let activePlatform = "overall";

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const status = document.getElementById("status");
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    DASHBOARD_DATA = await res.json();
  } catch (err) {
    status.textContent = "Could not load performance data. Run the export to generate data/stats.json.";
    return;
  }

  applyBranding(DASHBOARD_DATA);
  bindTabs();
  render(activePlatform);
}

function applyBranding(data) {
  if (data.site_title) document.getElementById("site-title").textContent = data.site_title;
  if (data.site_tagline) document.getElementById("site-tagline").textContent = data.site_tagline;
  document.title = `${data.site_title || "PropRadar"} — Performance`;

  if (data.generated_at) {
    const dt = new Date(data.generated_at);
    document.getElementById("generated-at").textContent = `Updated ${dt.toLocaleString()}`;
  }
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      activePlatform = tab.dataset.platform;
      render(activePlatform);
    });
  });
}

function render(platform) {
  const block = DASHBOARD_DATA.platforms[platform];
  const root = document.getElementById("dashboard");
  PropRadarCharts.destroyAll();

  if (!block || !block.totals || !block.totals.entries) {
    root.innerHTML = `<p class="empty">No recorded picks yet for ${labelFor(platform)}.</p>`;
    document.getElementById("date-range").textContent = "";
    return;
  }

  const t = block.totals;
  document.getElementById("date-range").textContent =
    t.date_start && t.date_end ? `${t.date_start} – ${t.date_end}` : "";

  root.innerHTML = [
    statCards(t, platform),
    chartsSection(),
    streaksAndTops(block),
    recentSection(block.recent, platform),
    crossCheck(block.sheet_summaries, t),
  ].join("");

  PropRadarCharts.renderProfit(document.getElementById("profit-chart"), block.profit_over_time);
  renderBars("league-bars", block.breakdowns.by_league);
  renderBars("ou-bars", block.breakdowns.by_ou);
  renderStatGroups("stat-bars", block.breakdowns.by_stat_by_sport);
}

function labelFor(platform) {
  return { overall: "Overall", sleeper: "Sleeper", prizepicks: "PrizePicks" }[platform] || platform;
}

// ---- formatting helpers ----
function money(v) {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}
function pct(v) {
  return v == null ? "—" : `${v.toFixed(1)}%`;
}
function signClass(v) {
  if (v == null || v === 0) return "";
  return v > 0 ? "pos" : "neg";
}

function card(label, value, sub, cls = "", title = "") {
  const titleAttr = title ? ` title="${title}"` : "";
  return `<div class="card stat-card"${titleAttr}>
    <span class="stat-label">${label}</span>
    <span class="stat-value ${cls}">${value}</span>
    <span class="stat-sub">${sub || ""}</span>
  </div>`;
}

function statCards(t, platform) {
  const evLabel = t.avg_ev == null ? "—" : `${t.avg_ev > 0 ? "+" : ""}${t.avg_ev.toFixed(1)}%`;

  const netProfit = card("Net Profit", money(t.profit), `${t.entries} entries`, signClass(t.profit));
  const legHitRate = card("Leg Hit Rate", pct(t.leg_hit_rate), `${t.leg_hits}/${t.leg_hits + t.leg_misses} legs`);
  const roi = card("ROI", pct(t.roi), "net profit ÷ total staked", signClass(t.roi));

  // The Overall (cross-platform) view only shows the metrics that are
  // comparable across platforms; per-platform tabs show the full set.
  const cards =
    platform === "overall"
      ? [netProfit, legHitRate, roi]
      : [
          netProfit,
          card("Parlay Win Rate", pct(t.parlay_win_rate), `${t.wins}W · ${t.losses}L${t.pushes ? ` · ${t.pushes}P` : ""}`),
          legHitRate,
          roi,
          card("Avg Est. Edge", evLabel, "per PropRadar pick", signClass(t.avg_ev)),
          card("Avg Legs", t.avg_legs_per_parlay == null ? "—" : t.avg_legs_per_parlay.toFixed(2), "per parlay (incl. promo)"),
        ];

  return `<section class="section">
    <div class="stat-grid">
      ${cards.join("\n      ")}
    </div>
  </section>`;
}

function chartsSection() {
  return `<section class="section">
    <h2>Profit Over Time</h2>
    <div class="card chart-card"><canvas id="profit-chart"></canvas></div>
  </section>
  <section class="section two-col">
    <div>
      <h2>Hit Rate by League</h2>
      <div class="card" id="league-bars"></div>
    </div>
    <div>
      <h2>Over / Under</h2>
      <div class="card" id="ou-bars"></div>
    </div>
  </section>
  <section class="section">
    <h2>By Stat</h2>
    <div class="card" id="stat-bars"></div>
  </section>`;
}

function barRow(r) {
  const rate = r.hit_rate == null ? 0 : r.hit_rate;
  const fillClass = r.hit_rate == null ? "" : r.hit_rate >= 50 ? "pos" : "neg";
  return `<div class="bar-row">
    <span class="bar-label">${r.key}</span>
    <span class="bar-track"><span class="bar-fill ${fillClass}" style="width:${rate}%"></span></span>
    <span class="bar-val">${pct(r.hit_rate)} <small>(${r.legs})</small></span>
  </div>`;
}

function renderBars(containerId, rows) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!rows || !rows.length) {
    el.innerHTML = `<p class="empty">No data</p>`;
    return;
  }
  el.innerHTML = rows.map(barRow).join("");
}

function renderStatGroups(containerId, sports) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!sports || !sports.length) {
    el.innerHTML = `<p class="empty">No data</p>`;
    return;
  }
  el.innerHTML = sports
    .map((s) => {
      const bars = s.stats.map(barRow).join("");
      return `<div class="stat-group">
        <div class="stat-group-head">${s.sport} <small>(${s.legs})</small></div>
        ${bars}
      </div>`;
    })
    .join("");
}

function streaksAndTops(block) {
  const s = block.streaks;
  const cur = s.current && s.current.type
    ? `<span class="pill ${s.current.type}">${s.current.length}</span> ${s.current.type} streak`
    : "—";
  return `<section class="section two-col">
    <div>
      <h2>Streaks</h2>
      <div class="card">
        <div class="bar-row" style="grid-template-columns:1fr auto"><span>Current</span><span>${cur}</span></div>
        <div class="bar-row" style="grid-template-columns:1fr auto"><span>Longest win streak</span><span class="pill win">${s.longest_win}</span></div>
        <div class="bar-row" style="grid-template-columns:1fr auto"><span>Longest loss streak</span><span class="pill loss">${s.longest_loss}</span></div>
      </div>
    </div>
    <div>
      <h2>Best &amp; Worst</h2>
      <div class="card">
        ${topRow("Best", block.best[0])}
        ${topRow("Worst", block.worst[0])}
      </div>
    </div>
  </section>`;
}

function topRow(label, entry) {
  if (!entry) return `<div class="bar-row" style="grid-template-columns:1fr auto"><span>${label}</span><span>—</span></div>`;
  const legs = entry.legs.map((l) => l.name.split(" ").slice(-1)[0]).join(", ");
  return `<div class="bar-row" style="grid-template-columns:auto 1fr auto">
    <span class="stat-sub">${label}</span>
    <span class="legs-cell" title="${entry.legs.map((l) => l.name).join(", ")}">${entry.date} · ${legs}</span>
    <span class="num ${signClass(entry.profit)}">${money(entry.profit)}</span>
  </div>`;
}

function platformRowClass(platform) {
  if (platform === "prizepicks") return "row-pp";
  if (platform === "sleeper") return "row-sleeper";
  return "";
}

function platformBadge(platform) {
  if (platform === "prizepicks") return `<span class="platform-pill prizepicks">PrizePicks</span>`;
  if (platform === "sleeper") return `<span class="platform-pill sleeper">Sleeper</span>`;
  return `<span class="platform-pill">${platform || "—"}</span>`;
}

function recentLegend(showPlatforms) {
  const legCodes = [
    ["OH", "Over hit"],
    ["OM", "Over miss"],
    ["OP", "Over push"],
    ["UH", "Under hit"],
    ["UM", "Under miss"],
    ["UP", "Under push"],
  ];
  const parlayCodes = [
    ["W", "Parlay win"],
    ["L", "Parlay loss"],
    ["P", "Parlay push"],
  ];
  const codeItems = (pairs) =>
    pairs
      .map(
        ([code, label]) =>
          `<span class="legend-item"><span class="legend-code">${code}</span> ${label}</span>`
      )
      .join("");

  const platformGroup = showPlatforms
    ? `<div class="legend-group">
        <span class="legend-title">Platforms</span>
        <span class="legend-item"><span class="legend-swatch prizepicks" aria-hidden="true"></span> PrizePicks</span>
        <span class="legend-item"><span class="legend-swatch sleeper" aria-hidden="true"></span> Sleeper</span>
      </div>`
    : "";

  return `<div class="recent-legend" aria-label="Legend">
    ${platformGroup}
    <div class="legend-group">
      <span class="legend-title">Leg codes</span>
      ${codeItems(legCodes)}
    </div>
    <div class="legend-group">
      <span class="legend-title">Parlay</span>
      ${codeItems(parlayCodes)}
    </div>
    <div class="legend-group">
      <span class="legend-title">Other</span>
      <span class="legend-item"><span class="legend-code">promo</span> Sleeper promo leg</span>
    </div>
  </div>`;
}

function recentSection(recent, platform) {
  if (!recent || !recent.length) return "";
  const showPlatform = platform === "overall";
  const rows = recent
    .map((e) => {
      const legParts = e.legs.map(
        (l) => `${l.name} <span class="leg-res ${l.result}">${l.ou}${l.result}</span>`
      );
      const promoParts = (e.promo_legs || []).map(
        (l) =>
          `<span class="promo-leg">${l.name} <span class="leg-res ${l.result}">${l.ou}${l.result}</span> <small>promo</small></span>`
      );
      const legs = legParts.concat(promoParts).join(" · ");
      const rowClass = showPlatform ? platformRowClass(e.platform) : "";
      const platformCell = showPlatform ? `<td>${platformBadge(e.platform)}</td>` : "";
      return `<tr class="${rowClass}">
        ${platformCell}
        <td>${e.date}</td>
        <td><span class="pill ${e.outcome}">${e.outcome === "win" ? "W" : e.outcome === "loss" ? "L" : "P"}</span></td>
        <td class="legs-cell">${legs}</td>
        <td class="num ${signClass(e.profit)}">${money(e.profit)}</td>
      </tr>`;
    })
    .join("");
  const platformHeader = showPlatform ? "<th>Platform</th>" : "";
  return `<section class="section">
    <h2>Recent Picks (${recent.length})</h2>
    <div class="card" style="overflow-x:auto;padding:0">
      <table>
        <thead><tr>${platformHeader}<th>Date</th><th>Result</th><th>Legs</th><th class="num">Profit</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${recentLegend(showPlatform)}
    </div>
  </section>`;
}

function crossCheck(summaries, totals) {
  const keys = summaries ? Object.keys(summaries) : [];
  if (!keys.length) return "";
  const rows = keys
    .map((k) => `<tr><td>${k}</td><td class="num">${summaries[k] == null ? "—" : summaries[k]}</td></tr>`)
    .join("");
  return `<details class="crosscheck">
    <summary>Sheet cross-check</summary>
    <table style="margin-top:12px">
      <thead><tr><th>Sheet cell</th><th class="num">Value</th></tr></thead>
      <tbody>
        ${rows}
        <tr><td>Computed net profit</td><td class="num">${money(totals.profit)}</td></tr>
      </tbody>
    </table>
  </details>`;
}
