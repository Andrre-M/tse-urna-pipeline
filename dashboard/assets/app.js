"use strict";

const DATASETS = ["overview", "coverage", "event_timeline", "applications", "temporal_outliers"];
const COLORS = { navy: "#123b57", teal: "#087f73", amber: "#dc8a20", red: "#b84b3f", grid: "#e3e6e3", paper: "#fffef9" };
const SEVERITY_COLORS = { INFO: "#087f73", ALERTA: "#dc8a20", ERRO: "#b84b3f", DEBUG: "#537a94", FATAL: "#742f4b" };
const number = new Intl.NumberFormat("pt-BR");
const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });

const state = { data: {}, page: "overview" };

const byId = (id) => document.getElementById(id);
const unique = (values) => [...new Set(values)].sort((a, b) => String(a).localeCompare(String(b), "pt-BR"));
const sum = (rows, key = "event_count") => rows.reduce((total, row) => total + Number(row[key] || 0), 0);
const groupSum = (rows, key, valueKey = "event_count") => {
  const grouped = new Map();
  rows.forEach((row) => grouped.set(row[key], (grouped.get(row[key]) || 0) + Number(row[valueKey] || 0)));
  return grouped;
};

function plot(id, traces, layout = {}) {
  const base = {
    margin: { l: 58, r: 18, t: 22, b: 52 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, system-ui, sans-serif", color: "#415463", size: 11 },
    xaxis: { gridcolor: COLORS.grid, zeroline: false, automargin: true },
    yaxis: { gridcolor: COLORS.grid, zeroline: false, automargin: true },
    hoverlabel: { bgcolor: COLORS.navy, bordercolor: COLORS.navy, font: { color: "white" } },
    legend: { orientation: "h", y: 1.08, x: 0 },
    ...layout,
  };
  Plotly.react(id, traces, base, { responsive: true, displayModeBar: false, locale: "pt-BR" });
}

function kpi(label, value, detail = "") {
  const element = document.createElement("article");
  element.className = "kpi";
  const labelElement = document.createElement("p");
  labelElement.className = "kpi-label";
  labelElement.textContent = label;
  const valueElement = document.createElement("strong");
  valueElement.className = "kpi-value";
  valueElement.textContent = value;
  element.append(labelElement, valueElement);
  if (detail) {
    const detailElement = document.createElement("span");
    detailElement.className = "kpi-detail";
    detailElement.textContent = detail;
    element.append(detailElement);
  }
  return element;
}

function setSelect(select, values, allLabel, current = "") {
  const options = [new Option(allLabel, ""), ...values.map((value) => new Option(value, value))];
  select.replaceChildren(...options);
  select.value = values.includes(current) ? current : "";
}

function renderOverview() {
  const overview = state.data.overview[0];
  byId("overview-kpis").replaceChildren(
    kpi("Eventos", number.format(overview.total_events), "registros operacionais agregados"),
    kpi("Seções publicadas", number.format(overview.published_sections), `de ${number.format(overview.catalog_sections)} catalogadas`),
    kpi("Cobertura", percent.format(overview.coverage_rate), `${number.format(overview.unpublished_sections)} sem arquivo publicado`),
    kpi("Municípios", number.format(overview.municipalities), `${number.format(overview.zones)} pares município/zona`),
    kpi("Timestamps atípicos", number.format(overview.temporal_outlier_events), "preservados e sinalizados"),
  );

  const timeline = groupSum(state.data.event_timeline, "event_date");
  const dates = [...timeline.keys()].sort();
  plot("overview-timeline", [{
    type: "scatter", mode: "lines", x: dates, y: dates.map((date) => timeline.get(date)),
    line: { color: COLORS.teal, width: 3 }, fill: "tozeroy", fillcolor: "rgba(8,127,115,.12)",
    hovertemplate: "%{x}<br><b>%{y:,.0f}</b> eventos<extra></extra>",
  }], { yaxis: { tickformat: "~s", gridcolor: COLORS.grid }, xaxis: { gridcolor: "transparent" } });

  plot("overview-coverage", [{
    type: "pie", hole: .72,
    labels: ["Publicadas", "Não publicadas"],
    values: [overview.published_sections, overview.unpublished_sections],
    marker: { colors: [COLORS.teal, "#d9dedc"] }, textinfo: "none",
    hovertemplate: "%{label}<br><b>%{value:,.0f}</b> seções<extra></extra>",
  }], {
    margin: { l: 10, r: 10, t: 12, b: 42 },
    annotations: [{ text: `<b>${percent.format(overview.coverage_rate)}</b><br><span style="font-size:11px">cobertura</span>`, showarrow: false, font: { color: COLORS.navy, size: 20 } }],
    legend: { orientation: "h", x: .5, xanchor: "center", y: -.08 },
  });
}

function coverageRows() {
  const municipality = byId("coverage-municipality").value;
  const zone = byId("coverage-zone").value;
  return state.data.coverage.filter((row) => (!municipality || row.municipality_name === municipality) && (!zone || row.zone === zone));
}

function refreshCoverageZones() {
  const municipality = byId("coverage-municipality").value;
  const zones = unique(state.data.coverage.filter((row) => !municipality || row.municipality_name === municipality).map((row) => row.zone));
  setSelect(byId("coverage-zone"), zones, "Todas as zonas", byId("coverage-zone").value);
}

function renderCoverage() {
  const rows = coverageRows();
  const published = rows.filter((row) => row.publication_status === "published").length;
  const withEvents = rows.filter((row) => row.has_events).length;
  const events = sum(rows);
  byId("coverage-kpis").replaceChildren(
    kpi("Seções", number.format(rows.length), "no recorte selecionado"),
    kpi("Publicadas", number.format(published), rows.length ? percent.format(published / rows.length) : "0%"),
    kpi("Com eventos", number.format(withEvents), "contagem maior que zero"),
    kpi("Eventos", number.format(events), "soma das seções"),
  );

  const municipalityTotals = groupSum(rows, "municipality_name");
  const ranked = [...municipalityTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 15).reverse();
  plot("coverage-municipalities", [{
    type: "bar", orientation: "h", x: ranked.map((item) => item[1]), y: ranked.map((item) => item[0]),
    marker: { color: COLORS.teal }, hovertemplate: "%{y}<br><b>%{x:,.0f}</b> eventos<extra></extra>",
  }], { margin: { l: 120, r: 15, t: 15, b: 45 }, xaxis: { tickformat: "~s", gridcolor: COLORS.grid }, yaxis: { gridcolor: "transparent" } });

  const positive = rows.filter((row) => row.event_count > 0).map((row) => row.event_count);
  plot("coverage-distribution", [{
    type: "histogram", x: positive, nbinsx: 30, marker: { color: COLORS.amber },
    hovertemplate: "Volume por seção: %{x}<br><b>%{y}</b> seções<extra></extra>",
  }], { xaxis: { title: "Eventos por seção", gridcolor: COLORS.grid }, yaxis: { title: "Seções", gridcolor: COLORS.grid } });

  const tableRows = [...rows].sort((a, b) => b.event_count - a.event_count).slice(0, 100).map((row) => {
    const tr = document.createElement("tr");
    [row.municipality_name, row.zone, row.section].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    const status = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `status-pill${row.publication_status === "published" ? "" : " unpublished"}`;
    pill.textContent = row.publication_status === "published" ? "publicada" : "não publicada";
    status.append(pill);
    const count = document.createElement("td"); count.className = "numeric"; count.textContent = number.format(row.event_count);
    tr.append(status, count);
    return tr;
  });
  byId("coverage-table").replaceChildren(...tableRows);
}

function eventRows(dataset) {
  const municipality = byId("events-municipality").value;
  const zone = byId("events-zone").value;
  const severity = byId("events-severity").value;
  return dataset.filter((row) => (!municipality || row.municipality_name === municipality) && (!zone || row.zone === zone) && (!severity || row.severity === severity));
}

function refreshEventZones() {
  const municipality = byId("events-municipality").value;
  const zones = unique(state.data.event_timeline.filter((row) => !municipality || row.municipality_name === municipality).map((row) => row.zone));
  setSelect(byId("events-zone"), zones, "Todas as zonas", byId("events-zone").value);
}

function renderEvents() {
  const timelineRows = eventRows(state.data.event_timeline);
  const applicationRows = eventRows(state.data.applications);
  const severities = unique(timelineRows.map((row) => row.severity));
  const dateSeries = severities.map((severity) => {
    const grouped = groupSum(timelineRows.filter((row) => row.severity === severity), "event_date");
    const dates = [...grouped.keys()].sort();
    return { type: "scatter", mode: "lines", name: severity, x: dates, y: dates.map((date) => grouped.get(date)), line: { width: 2.5, color: SEVERITY_COLORS[severity] || COLORS.navy }, hovertemplate: `${severity}<br>%{x}<br><b>%{y:,.0f}</b> eventos<extra></extra>` };
  });
  plot("events-timeline", dateSeries, { yaxis: { tickformat: "~s", gridcolor: COLORS.grid }, xaxis: { gridcolor: "transparent" } });

  const hours = groupSum(timelineRows, "event_hour");
  plot("events-hours", [{ type: "bar", x: Array.from({ length: 24 }, (_, index) => index), y: Array.from({ length: 24 }, (_, index) => hours.get(index) || 0), marker: { color: COLORS.amber }, hovertemplate: "%{x}h<br><b>%{y:,.0f}</b> eventos<extra></extra>" }], { xaxis: { title: "Hora registrada", dtick: 2, gridcolor: "transparent" }, yaxis: { tickformat: "~s", gridcolor: COLORS.grid } });

  const apps = unique(applicationRows.map((row) => row.application));
  const appTraces = unique(applicationRows.map((row) => row.severity)).map((severity) => ({
    type: "bar", name: severity, x: apps,
    y: apps.map((app) => sum(applicationRows.filter((row) => row.application === app && row.severity === severity))),
    marker: { color: SEVERITY_COLORS[severity] || COLORS.navy },
    hovertemplate: `${severity}<br>%{x}<br><b>%{y:,.0f}</b> eventos<extra></extra>`,
  }));
  plot("events-applications", appTraces, { barmode: "stack", xaxis: { gridcolor: "transparent" }, yaxis: { tickformat: "~s", gridcolor: COLORS.grid } });
}

function renderQuality() {
  const outliers = state.data.temporal_outliers;
  const years = groupSum(outliers, "event_year_recorded");
  const yearEntries = [...years.entries()].sort((a, b) => a[0] - b[0]);
  plot("quality-outliers", [{ type: "bar", x: yearEntries.map((item) => String(item[0])), y: yearEntries.map((item) => item[1]), marker: { color: [COLORS.amber, COLORS.red, "#742f4b"] }, text: yearEntries.map((item) => number.format(item[1])), textposition: "outside", hovertemplate: "Ano %{x}<br><b>%{y}</b> eventos<extra></extra>" }], { xaxis: { title: "Ano registrado", type: "category", gridcolor: "transparent" }, yaxis: { title: "Eventos", gridcolor: COLORS.grid }, margin: { l: 55, r: 15, t: 28, b: 55 } });

  const rows = [...outliers].sort((a, b) => b.event_count - a.event_count).map((row) => {
    const tr = document.createElement("tr");
    [row.section_id, row.municipality_name, row.event_year_recorded, row.application, row.severity].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
    const count = document.createElement("td"); count.className = "numeric"; count.textContent = number.format(row.event_count); tr.append(count);
    return tr;
  });
  byId("outliers-table").replaceChildren(...rows);
}

function showPage(page) {
  const validPage = ["overview", "coverage", "events", "quality"].includes(page) ? page : "overview";
  state.page = validPage;
  document.querySelectorAll(".page").forEach((element) => { element.hidden = element.dataset.page !== validPage; element.classList.toggle("is-active", element.dataset.page === validPage); });
  document.querySelectorAll(".nav-link").forEach((element) => element.classList.toggle("is-active", element.dataset.pageTarget === validPage));
  history.replaceState(null, "", `#${validPage}`);
  if (state.data.overview) {
    if (validPage === "overview") renderOverview();
    if (validPage === "coverage") renderCoverage();
    if (validPage === "events") renderEvents();
    if (validPage === "quality") renderQuality();
    window.setTimeout(() => window.dispatchEvent(new Event("resize")), 20);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindControls() {
  document.querySelectorAll(".nav-link").forEach((button) => button.addEventListener("click", () => showPage(button.dataset.pageTarget)));
  byId("coverage-municipality").addEventListener("change", () => { refreshCoverageZones(); renderCoverage(); });
  byId("coverage-zone").addEventListener("change", renderCoverage);
  byId("events-municipality").addEventListener("change", () => { refreshEventZones(); renderEvents(); });
  byId("events-zone").addEventListener("change", renderEvents);
  byId("events-severity").addEventListener("change", renderEvents);
  window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));
}

async function initialize() {
  try {
    const payloads = await Promise.all(DATASETS.map(async (name) => {
      const response = await fetch(`data/${name}.json`);
      if (!response.ok) throw new Error(`Falha ao carregar ${name}`);
      return [name, await response.json()];
    }));
    state.data = Object.fromEntries(payloads);
    const municipalities = unique(state.data.coverage.map((row) => row.municipality_name));
    setSelect(byId("coverage-municipality"), municipalities, "Todos os municípios");
    setSelect(byId("events-municipality"), municipalities, "Todos os municípios");
    setSelect(byId("events-severity"), unique(state.data.event_timeline.map((row) => row.severity)), "Todas as severidades");
    refreshCoverageZones();
    refreshEventZones();
    const metadata = await fetch("build.json").then((response) => response.json());
    byId("build-provenance").textContent = `Gold ${metadata.revision.slice(0, 9)} • ${number.format(Object.values(metadata.tables).reduce((a, b) => a + b, 0))} linhas`;
    byId("loading").hidden = true;
    showPage(location.hash.slice(1) || "overview");
  } catch (error) {
    byId("loading").hidden = true;
    const panel = byId("error");
    panel.hidden = false;
    panel.textContent = `Não foi possível carregar o painel: ${error.message}`;
  }
}

bindControls();
initialize();
