"use strict";

const state = { data: null, route: "overview", cache: new Map(), view: {} };
const app = document.querySelector("#app");
const loading = document.querySelector("#loading");
const fmt = new Intl.NumberFormat("pt-BR");
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });
const pct2 = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 2 });

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[char]));
const slug = (value) => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const byOffice = (rows, office) => rows.find((row) => row.office === office);
const sum = (rows, key) => rows.reduce((total, row) => total + Number(row[key] || 0), 0);
const median = (values) => {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
};

async function loadJson(path) {
  if (!state.cache.has(path)) state.cache.set(path, fetch(path).then((response) => {
    if (!response.ok) throw new Error(`Não foi possível carregar ${path}`);
    return response.json();
  }));
  return state.cache.get(path);
}

function expandFrame(payload) {
  return payload.rows.map((values) => Object.fromEntries(payload.fields.map((field, index) => [field, values[index]])));
}

function pageHead(eyebrow, title, intro, noteTitle, note) {
  return `<header class="page-head"><div><span class="eyebrow">${eyebrow}</span><h1>${title}</h1><p>${intro}</p></div><aside class="head-note"><strong>${noteTitle}</strong>${note}</aside></header>`;
}

function metric(label, value, detail) {
  return `<article class="metric"><span>${label}</span><strong>${value}</strong><small>${detail}</small></article>`;
}

function stacked(row) {
  const total = Number(row.total_votes) || 1;
  const parts = [
    ["valid", row.valid_votes, "Válidos"], ["blank", row.blank_votes, "Brancos"],
    ["null", row.null_votes, "Nulos"], ["separate", row.separately_annulled_votes, "Anulados em separado"],
  ];
  return `<div class="stacked-bar" aria-label="Composição dos votos">${parts.map(([klass, value, label]) => `<span class="${klass}" style="width:${Number(value || 0) / total * 100}%" title="${label}: ${fmt.format(value || 0)}"></span>`).join("")}</div><div class="legend">${parts.filter(([, value]) => Number(value) > 0).map(([klass, value, label]) => `<span><i class="${klass}"></i>${label} ${pct.format(Number(value) / total)}</span>`).join("")}</div>`;
}

function officeComposition(rows) {
  return `<div class="composition-list">${rows.map((row) => `<div class="composition-row"><div><strong>${escapeHtml(row.office)}</strong><small>${fmt.format(row.total_votes)} votos registrados</small></div><div>${stacked(row)}</div></div>`).join("")}</div>`;
}

function barChart(rows, { label = "label", value = "value", format = fmt.format, limit = 12, candidate = false } = {}) {
  const visible = rows.slice(0, limit);
  const maximum = Math.max(...visible.map((row) => Number(row[value])), 1);
  return `<div class="chart">${visible.map((row) => `<div class="bar-row ${candidate ? "candidate-row" : ""}"><span class="bar-label" title="${escapeHtml(row[label])}">${escapeHtml(row[label])}</span><div class="bar-track"><div class="bar-fill" style="width:${Number(row[value]) / maximum * 100}%"></div></div><span class="bar-value">${format(Number(row[value]))}</span></div>`).join("")}</div>`;
}

function agePyramid(rows) {
  const ageOrder = ["16 anos", "17 anos", "18 anos", "19 anos", "20 anos", "21 a 24 anos", "25 a 29 anos", "30 a 34 anos", "35 a 39 anos", "40 a 44 anos", "45 a 49 anos", "50 a 54 anos", "55 a 59 anos", "60 a 64 anos", "65 a 69 anos", "70 a 74 anos", "75 a 79 anos", "80 a 84 anos", "85 a 89 anos", "90 a 94 anos", "95 a 99 anos", "100 anos ou mais"];
  const lookup = new Map(rows.map((row) => [`${row.category}|${row.subcategory}`, Number(row.registered_electors || 0)]));
  const total = sum(rows, "registered_electors") || 1;
  const maleTotal = rows.filter((row) => row.subcategory === "MASCULINO").reduce((value, row) => value + Number(row.registered_electors || 0), 0);
  const femaleTotal = rows.filter((row) => row.subcategory === "FEMININO").reduce((value, row) => value + Number(row.registered_electors || 0), 0);
  const uninformed = rows.filter((row) => row.subcategory === "NÃO INFORMADO" || row.category === "Inválida").reduce((value, row) => value + Number(row.registered_electors || 0), 0);
  const bands = [...ageOrder].reverse().map((age) => ({
    age,
    male: lookup.get(`${age}|MASCULINO`) || 0,
    female: lookup.get(`${age}|FEMININO`) || 0,
  }));
  const maximum = Math.max(...bands.flatMap((row) => [row.male, row.female]), 1);
  const side = (value, age, gender, klass) => `<div class="pyramid-side ${klass}"><div class="pyramid-bar" style="width:${value / maximum * 100}%" title="${gender}, ${age}: ${fmt.format(value)} (${pct.format(value / total)} do recorte)" aria-label="${gender}, ${age}: ${fmt.format(value)}"></div></div>`;
  return `<div class="age-pyramid"><div class="pyramid-header"><strong>Homens <span>${pct.format(maleTotal / total)}</span></strong><span>Faixa etária</span><strong>Mulheres <span>${pct.format(femaleTotal / total)}</span></strong></div><div class="pyramid-body">${bands.map((row) => `<div class="pyramid-row">${side(row.male, row.age, "Homens", "male")}<span class="pyramid-age">${escapeHtml(row.age)}</span>${side(row.female, row.age, "Mulheres", "female")}</div>`).join("")}</div>${uninformed ? `<p class="pyramid-note">${fmt.format(uninformed)} registros com gênero não informado ou faixa etária inválida.</p>` : ""}</div>`;
}

function sortRows(rows, key, direction) {
  const factor = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = left[key]; const b = right[key];
    if (typeof a === "number" || typeof b === "number") return (Number(a || 0) - Number(b || 0)) * factor;
    return String(a ?? "").localeCompare(String(b ?? ""), "pt-BR", { sensitivity: "base" }) * factor;
  });
}

function sortHeader(label, key, sort, numeric = false) {
  const active = sort.key === key;
  const arrow = active ? (sort.direction === "asc" ? " ↑" : " ↓") : "";
  return `<th class="${numeric ? "num" : ""}"><button class="sort-button ${active ? "active" : ""}" data-sort="${key}">${label}${arrow}</button></th>`;
}

function bindSorting(container, sort, update) {
  container.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.sort;
    sort.direction = sort.key === key && sort.direction === "desc" ? "asc" : "desc";
    sort.key = key;
    update();
  }));
}

function municipalityOptions(selected = "") {
  return `<option value="">Todos os municípios</option>${state.data.municipalities.map((row) => `<option value="${row.municipality_code}" ${row.municipality_code === selected ? "selected" : ""}>${escapeHtml(row.municipality_name)}</option>`).join("")}`;
}

function geoPath(geometry, project) {
  const polygon = (rings) => rings.map((ring) => `M${ring.map((point) => project(point).join(",")).join("L")}Z`).join("");
  if (geometry.type === "Polygon") return polygon(geometry.coordinates);
  if (geometry.type === "MultiPolygon") return geometry.coordinates.map(polygon).join("");
  return "";
}

function renderMap(targetId, rows, valueKey, { format = pct.format, selected = "", onSelect = null } = {}) {
  const target = document.querySelector(`#${targetId}`);
  if (!state.data.geojson?.features?.length) {
    target.innerHTML = `<div class="empty"><div><strong>Mapa indisponível nesta compilação</strong>A tabela mantém a consulta completa.</div></div>`;
    return;
  }
  const coords = state.data.geojson.features.flatMap((feature) => {
    const pairs = [];
    const walk = (value) => Array.isArray(value[0]) ? value.forEach(walk) : pairs.push(value);
    walk(feature.geometry.coordinates); return pairs;
  });
  const xs = coords.map((point) => point[0]); const ys = coords.map((point) => point[1]);
  const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
  const project = ([x, y]) => [20 + (x - minX) / (maxX - minX) * 560, 20 + (maxY - y) / (maxY - minY) * 560];
  const lookup = new Map(rows.map((row) => [String(row.municipality_code), row]));
  const values = rows.map((row) => Number(row[valueKey])).filter(Number.isFinite);
  const min = Math.min(...values); const max = Math.max(...values);
  const color = (value) => { const t = (value - min) / (max - min || 1); return `rgb(${Math.round(221 - t * 203)},${Math.round(236 - t * 129)},${Math.round(223 - t * 148)})`; };
  target.innerHTML = `<svg viewBox="0 0 600 600" role="img" aria-label="Mapa dos municípios do Ceará">${state.data.geojson.features.map((feature) => {
    const code = String(feature.properties.municipality_code || "");
    const name = feature.properties.municipality_name || "Município";
    const row = lookup.get(code);
    return `<path tabindex="0" class="${selected === code ? "selected" : ""}" d="${geoPath(feature.geometry, project)}" fill="${row ? color(Number(row[valueKey])) : "#dfe5df"}" data-code="${code}" data-name="${escapeHtml(name)}" data-value="${row ? format(Number(row[valueKey])) : "Sem dado"}"></path>`;
  }).join("")}</svg><div class="map-scale"><span>${format(min)}</span><i></i><span>${format(max)}</span></div><div class="map-tooltip" hidden></div>`;
  const tooltip = target.querySelector(".map-tooltip");
  target.querySelectorAll("path").forEach((path) => {
    const show = (event) => { tooltip.hidden = false; tooltip.innerHTML = `<strong>${path.dataset.name}</strong><br>${path.dataset.value}`; tooltip.style.left = `${event.offsetX || 20}px`; tooltip.style.top = `${event.offsetY || 20}px`; };
    path.addEventListener("mousemove", show); path.addEventListener("focus", show);
    path.addEventListener("mouseleave", () => { tooltip.hidden = true; }); path.addEventListener("blur", () => { tooltip.hidden = true; });
    if (onSelect) path.addEventListener("click", () => onSelect(path.dataset.code));
  });
}

function renderOverview() {
  const rows = state.data.overview;
  const president = byOffice(rows, "Presidente");
  const municipal = state.data.municipality_summary.filter((row) => row.office === "Presidente");
  const turnout = sortRows(municipal, "turnout_rate", "asc");
  const largest = sortRows(municipal, "eligible_voters", "desc").slice(0, 5);
  app.innerHTML = `${pageHead("Primeiro turno", "O Ceará em uma leitura.", "Participação, composição dos votos e diferenças territoriais em uma síntese do primeiro turno.", "4 de outubro de 2026", "Resultados eleitorais, perfil cadastral e logs técnicos permanecem em universos separados.")}
    <section class="metric-grid" aria-label="Indicadores principais">
      ${metric("Eleitorado apto", fmt.format(president.eligible_voters), "Universo do cargo de Presidente")}
      ${metric("Comparecimento", fmt.format(president.turnout), pct.format(president.turnout_rate))}
      ${metric("Abstenção", fmt.format(president.abstentions), pct.format(president.abstention_rate))}
      ${metric("Território", "184 municípios", `${fmt.format(state.data.section_count)} seções apuradas`)}
    </section>
    <div class="section-heading"><h2>Composição por cargo</h2><p>A proporção de votos válidos, brancos e nulos revela diferenças que o comparecimento, praticamente igual entre cargos, escondia.</p></div>
    <section class="panel-grid"><article class="panel wide">${officeComposition(rows)}</article></section>
    <div class="section-heading"><h2>O estado não vota de forma uniforme</h2><p>Os extremos são descritivos e não explicam, isoladamente, o comportamento do eleitorado.</p></div>
    <section class="metric-grid compact-metrics">
      ${metric("Menor comparecimento", pct.format(turnout[0].turnout_rate), turnout[0].municipality_name)}
      ${metric("Mediana municipal", pct.format(median(municipal.map((row) => row.turnout_rate))), "Metade dos municípios acima e metade abaixo")}
      ${metric("Maior comparecimento", pct.format(turnout.at(-1).turnout_rate), turnout.at(-1).municipality_name)}
      ${metric("Amplitude", `${((turnout.at(-1).turnout_rate - turnout[0].turnout_rate) * 100).toFixed(1).replace(".", ",")} p.p.`, "Diferença entre os extremos municipais")}
    </section>
    <section class="panel-grid overview-secondary"><article class="panel"><h3>Maiores eleitorados municipais</h3><p class="panel-intro">Aptos para Presidente.</p>${barChart(largest.map((row) => ({ label: row.municipality_name, value: row.eligible_voters })), { limit: 5 })}</article><article class="panel"><h3>Onde aprofundar</h3><div class="link-list"><a href="#municipios">Comparar os 184 municípios <span>→</span></a><a href="#eleitorado">Conhecer o perfil cadastral <span>→</span></a><a href="#cargos">Analisar candidaturas e partidos <span>→</span></a><a href="#explorador">Chegar até zona e seção <span>→</span></a></div></article></section>`;
}

function renderMunicipios() {
  const offices = state.data.overview.map((row) => row.office);
  state.view.municipalitySort = { key: "turnout_rate", direction: "desc" };
  app.innerHTML = `${pageHead("Exploração geográfica", "184 municípios, uma eleição.", "Compare participação e composição dos votos em todo o estado. Mapa, ranking e tabela usam o mesmo cargo e indicador.", "Como ler", "Cores mais intensas indicam valores maiores no indicador selecionado; não representam vantagem de candidatura.")}
    <div class="filter-bar"><div class="field"><label for="municipality-office">Cargo</label><select id="municipality-office">${offices.map((office) => `<option>${escapeHtml(office)}</option>`).join("")}</select></div><div class="field"><label for="municipality-metric">Indicador</label><select id="municipality-metric"><option value="turnout_rate">Comparecimento</option><option value="abstention_rate">Abstenção</option><option value="blank_vote_rate">Votos brancos</option><option value="null_vote_rate">Votos nulos</option></select></div><div class="field"><label for="municipality-search">Buscar município</label><input id="municipality-search" type="search" placeholder="Digite um nome"></div></div>
    <section class="panel-grid page-panels"><article class="panel"><h3>Mapa municipal</h3><p class="panel-intro" id="map-caption"></p><div id="municipality-map" class="map-shell"></div></article><article class="panel"><h3>Ranking municipal</h3><p class="panel-intro">Os 14 maiores valores no filtro atual.</p><div id="municipality-ranking"></div></article><article class="panel wide"><div class="panel-heading"><div><h3>Todos os municípios</h3><p class="panel-intro">Clique nos cabeçalhos para ordenar ou em uma linha para aprofundar.</p></div><span id="municipality-count" class="count-pill"></span></div><div id="municipality-table"></div></article></section>`;
  const update = () => updateMunicipalities(document.querySelector("#municipality-office").value, document.querySelector("#municipality-metric").value, document.querySelector("#municipality-search").value);
  ["#municipality-office", "#municipality-metric", "#municipality-search"].forEach((selector) => document.querySelector(selector).addEventListener(selector.includes("search") ? "input" : "change", () => {
    if (selector === "#municipality-metric") state.view.municipalitySort = { key: document.querySelector(selector).value, direction: "desc" };
    update();
  }));
  update();
}

function updateMunicipalities(office, metricName, query) {
  const labels = { turnout_rate: "comparecimento", abstention_rate: "abstenção", blank_vote_rate: "votos brancos", null_vote_rate: "votos nulos" };
  const allRows = state.data.municipality_summary.filter((row) => row.office === office);
  const normalizedQuery = slug(query);
  const filtered = allRows.filter((row) => !normalizedQuery || slug(row.municipality_name).includes(normalizedQuery));
  const rows = sortRows(filtered, state.view.municipalitySort.key, state.view.municipalitySort.direction);
  document.querySelector("#map-caption").textContent = `${office} · ${labels[metricName]}`;
  document.querySelector("#municipality-ranking").innerHTML = barChart(sortRows(filtered, metricName, "desc").map((row) => ({ label: row.municipality_name, value: row[metricName] })), { format: pct.format, limit: 14 });
  document.querySelector("#municipality-count").textContent = `${rows.length} municípios`;
  const sort = state.view.municipalitySort;
  const container = document.querySelector("#municipality-table");
  container.innerHTML = `<div class="data-table-wrap"><table><thead><tr>${sortHeader("Município", "municipality_name", sort)}${sortHeader("Aptos", "eligible_voters", sort, true)}${sortHeader("Comparecimento", "turnout_rate", sort, true)}${sortHeader("Abstenção", "abstention_rate", sort, true)}${sortHeader("Brancos", "blank_vote_rate", sort, true)}${sortHeader("Nulos", "null_vote_rate", sort, true)}</tr></thead><tbody>${rows.map((row) => `<tr data-municipality="${row.municipality_code}" tabindex="0"><td><strong>${escapeHtml(row.municipality_name)}</strong></td><td class="num">${fmt.format(row.eligible_voters)}</td><td class="num">${pct.format(row.turnout_rate)}</td><td class="num">${pct.format(row.abstention_rate)}</td><td class="num">${pct.format(row.blank_vote_rate)}</td><td class="num">${pct.format(row.null_vote_rate)}</td></tr>`).join("")}</tbody></table></div>`;
  bindSorting(container, sort, () => updateMunicipalities(office, metricName, query));
  const openMunicipality = (code) => { sessionStorage.setItem("atlas-municipality", code); location.hash = "explorador"; };
  container.querySelectorAll("[data-municipality]").forEach((row) => { row.addEventListener("click", () => openMunicipality(row.dataset.municipality)); row.addEventListener("keydown", (event) => { if (event.key === "Enter") openMunicipality(row.dataset.municipality); }); });
  renderMap("municipality-map", allRows, metricName, { onSelect: openMunicipality });
}

function aggregateProfile(dimension, municipality = "") {
  const rows = state.data.electorate_profile.filter((row) => row.dimension === dimension && (!municipality || row.municipality_code === municipality));
  if (municipality) return rows;
  return [...rows.reduce((map, row) => {
    const key = `${row.category}|${row.subcategory || ""}`;
    const current = map.get(key) || { category: row.category, subcategory: row.subcategory, registered_electors: 0 };
    current.registered_electors += Number(row.registered_electors || 0);
    return map.set(key, current);
  }, new Map()).values()];
}

function orderedProfile(dimension, rows) {
  const ageOrder = ["16 anos", "17 anos", "18 anos", "19 anos", "20 anos", "21 a 24 anos", "25 a 29 anos", "30 a 34 anos", "35 a 39 anos", "40 a 44 anos", "45 a 49 anos", "50 a 54 anos", "55 a 59 anos", "60 a 64 anos", "65 a 69 anos", "70 a 74 anos", "75 a 79 anos", "80 a 84 anos", "85 a 89 anos", "90 a 94 anos", "95 a 99 anos", "100 anos ou mais", "Inválida"];
  if (dimension === "age_band" || dimension === "age_gender") return [...rows].sort((a, b) => ageOrder.indexOf(a.category) - ageOrder.indexOf(b.category));
  return sortRows(rows, "registered_electors", "desc");
}

function renderEleitorado() {
  state.view.profileSort = { key: "registered_electors", direction: "desc" };
  app.innerHTML = `${pageHead("Perfil cadastral", "Quem estava apto a votar?", "Idade, escolaridade, gênero, biometria e indicadores de inclusão no cadastro eleitoral.", "Universo próprio", `O perfil soma ${fmt.format(state.data.metadata.registered_electors_profile)} registros e não representa comparecimento.`)}
    <div class="filter-bar"><div class="field"><label for="profile-municipality">Recorte das distribuições</label><select id="profile-municipality">${municipalityOptions()}</select></div><div class="field"><label for="profile-map-metric">Indicador territorial</label><select id="profile-map-metric"><option value="biometric_rate">Biometria</option><option value="disability_rate">Eleitores com deficiência</option><option value="social_name_rate">Uso de nome social</option><option value="registered_electors">Eleitorado cadastrado</option></select></div></div>
    <div id="profile-summary" class="metric-grid profile-metrics"></div>
    <div class="section-heading"><h2>Composição do eleitorado</h2><p>As faixas etárias seguem a ordem de idade; as demais dimensões são ordenadas por volume.</p></div>
    <section class="panel-grid"><article class="panel wide"><h3>Pirâmide etária do eleitorado</h3><p class="panel-intro" id="age-caption"></p><div id="age-chart"></div></article><article class="panel"><h3>Escolaridade</h3><div id="education-chart"></div></article><article class="panel"><h3>Gênero</h3><div id="gender-chart"></div></article></section>
    <div class="section-heading"><h2>Diferenças municipais</h2><p>Compare proporções, não apenas volumes absolutos.</p></div>
    <section class="panel-grid"><article class="panel"><h3>Mapa do indicador</h3><p class="panel-intro" id="profile-map-caption"></p><div id="profile-map" class="map-shell"></div></article><article class="panel"><h3>Maiores valores</h3><div id="profile-ranking"></div></article><article class="panel wide"><h3>Todos os municípios</h3><div id="profile-table"></div></article></section>
    <p class="note"><strong>Leitura responsável.</strong> As categorias reproduzem o cadastro do TSE. Contagens de deficiência e nome social não devem ser usadas para inferir escolhas eleitorais.</p>`;
  const update = () => updateProfile(document.querySelector("#profile-municipality").value, document.querySelector("#profile-map-metric").value);
  document.querySelector("#profile-municipality").addEventListener("change", update);
  document.querySelector("#profile-map-metric").addEventListener("change", () => { state.view.profileSort = { key: document.querySelector("#profile-map-metric").value, direction: "desc" }; update(); });
  update();
}

function updateProfile(municipality, mapMetric) {
  const summaries = state.data.electorate_municipality_summary;
  const selected = municipality ? { ...summaries.find((row) => row.municipality_code === municipality) } : {
    registered_electors: sum(summaries, "registered_electors"), biometric_electors: sum(summaries, "biometric_electors"), electors_with_disability: sum(summaries, "electors_with_disability"), electors_with_social_name: sum(summaries, "electors_with_social_name"),
  };
  selected.biometric_rate = selected.biometric_electors / selected.registered_electors;
  selected.disability_rate = selected.electors_with_disability / selected.registered_electors;
  selected.social_name_rate = selected.electors_with_social_name / selected.registered_electors;
  document.querySelector("#profile-summary").innerHTML = `${metric("Eleitorado cadastrado", fmt.format(selected.registered_electors), municipality ? "Município selecionado" : "Ceará")}${metric("Com biometria", fmt.format(selected.biometric_electors), pct.format(selected.biometric_rate))}${metric("Com deficiência", fmt.format(selected.electors_with_disability), pct.format(selected.disability_rate))}${metric("Com nome social", fmt.format(selected.electors_with_social_name), pct2.format(selected.social_name_rate))}`;
  const age = orderedProfile("age_gender", aggregateProfile("age_gender", municipality));
  const education = orderedProfile("education", aggregateProfile("education", municipality));
  const gender = orderedProfile("gender", aggregateProfile("gender", municipality));
  document.querySelector("#age-caption").textContent = `${fmt.format(sum(age, "registered_electors"))} registros; homens à esquerda e mulheres à direita, na mesma escala.`;
  document.querySelector("#age-chart").innerHTML = agePyramid(age);
  document.querySelector("#education-chart").innerHTML = barChart(education.map((row) => ({ label: row.category, value: row.registered_electors })), { limit: 12 });
  document.querySelector("#gender-chart").innerHTML = barChart(gender.map((row) => ({ label: row.category, value: row.registered_electors })), { limit: 5 });
  const labels = { biometric_rate: "eleitorado com biometria", disability_rate: "eleitores com deficiência", social_name_rate: "uso de nome social", registered_electors: "eleitorado cadastrado" };
  const formatter = mapMetric === "registered_electors" ? fmt.format : (mapMetric === "social_name_rate" ? pct2.format : pct.format);
  document.querySelector("#profile-map-caption").textContent = labels[mapMetric];
  document.querySelector("#profile-ranking").innerHTML = barChart(sortRows(summaries, mapMetric, "desc").map((row) => ({ label: row.municipality_name, value: row[mapMetric] })), { format: formatter, limit: 14 });
  const choose = (code) => { document.querySelector("#profile-municipality").value = code; updateProfile(code, mapMetric); };
  renderMap("profile-map", summaries, mapMetric, { format: formatter, selected: municipality, onSelect: choose });
  const sort = state.view.profileSort;
  const rows = sortRows(summaries, sort.key, sort.direction);
  const container = document.querySelector("#profile-table");
  container.innerHTML = `<div class="data-table-wrap"><table><thead><tr>${sortHeader("Município", "municipality_name", sort)}${sortHeader("Eleitorado", "registered_electors", sort, true)}${sortHeader("Biometria", "biometric_rate", sort, true)}${sortHeader("Deficiência", "disability_rate", sort, true)}${sortHeader("Nome social", "social_name_rate", sort, true)}</tr></thead><tbody>${rows.map((row) => `<tr data-profile-municipality="${row.municipality_code}"><td><strong>${escapeHtml(row.municipality_name)}</strong></td><td class="num">${fmt.format(row.registered_electors)}</td><td class="num">${pct.format(row.biometric_rate)}</td><td class="num">${pct.format(row.disability_rate)}</td><td class="num">${pct2.format(row.social_name_rate)}</td></tr>`).join("")}</tbody></table></div>`;
  bindSorting(container, sort, () => updateProfile(municipality, mapMetric));
  container.querySelectorAll("[data-profile-municipality]").forEach((row) => row.addEventListener("click", () => choose(row.dataset.profileMunicipality)));
}

function candidateKey(row) { return `${row.ballot_number}|${row.candidate_id || "party"}`; }
function aggregateCandidates(source, municipality = "", query = "") {
  const normalized = slug(query);
  const filtered = source.filter((row) => (!municipality || row.municipality_code === municipality) && (!normalized || slug(`${row.candidate_name} ${row.ballot_name} ${row.ballot_number} ${row.party_abbreviation}`).includes(normalized)));
  return [...filtered.reduce((map, row) => {
    const key = candidateKey(row); const current = map.get(key) || { ...row, candidate_key: key, votes: 0 };
    current.votes += row.votes; map.set(key, current); return map;
  }, new Map()).values()];
}

async function renderCargos() {
  const offices = state.data.candidate_files;
  state.view.candidateSort = { key: "votes", direction: "desc" };
  state.view.mapCandidate = "";
  app.innerHTML = `${pageHead("Resultados por cargo", "Candidaturas no território.", "Compare candidaturas e partidos no estado e nos municípios, com contexto sobre a composição dos votos.", "Escopo", "Percentuais de candidatura usam os votos válidos do recorte. Para Senado, cada eleitor podia registrar dois votos.")}
    <div class="filter-bar"><div class="field"><label for="candidate-office">Cargo</label><select id="candidate-office">${offices.map((row) => `<option value="${row.office_code}">${escapeHtml(row.office)}</option>`).join("")}</select></div><div class="field"><label for="candidate-municipality">Localidade da tabela</label><select id="candidate-municipality">${municipalityOptions()}</select></div><div class="field"><label for="candidate-search">Buscar candidatura</label><input id="candidate-search" type="search" placeholder="Nome, número ou partido"></div></div>
    <div id="candidate-summary" class="metric-grid candidate-metrics"></div>
    <section class="panel-grid page-panels"><article class="panel wide"><div class="panel-heading"><div><h3 id="candidate-title">Resultado</h3><p class="panel-intro" id="candidate-caption"></p></div></div><div id="candidate-chart"></div><div id="candidate-table" class="table-spacing"></div></article><article class="panel"><div class="field map-candidate-field"><label for="map-candidate">Candidatura no mapa</label><select id="map-candidate"></select></div><p class="panel-intro">Percentual entre os votos válidos do cargo em cada município.</p><div id="candidate-map" class="map-shell"></div></article><article class="panel"><h3>Maiores percentuais municipais</h3><p class="panel-intro" id="candidate-map-caption"></p><div id="candidate-ranking"></div></article></section>`;
  let source = [];
  const update = () => updateCandidates(source, document.querySelector("#candidate-municipality").value, document.querySelector("#candidate-search").value);
  const loadOffice = async () => {
    const code = document.querySelector("#candidate-office").value;
    const file = offices.find((row) => String(row.office_code) === code).file;
    source = expandFrame(await loadJson(file)); state.view.mapCandidate = ""; state.view.candidateSort = { key: "votes", direction: "desc" }; update();
  };
  document.querySelector("#candidate-office").addEventListener("change", loadOffice);
  document.querySelector("#candidate-municipality").addEventListener("change", update);
  document.querySelector("#candidate-search").addEventListener("input", update);
  document.querySelector("#map-candidate").addEventListener("change", (event) => { state.view.mapCandidate = event.target.value; update(); });
  await loadOffice();
}

function updateCandidates(source, municipality, query) {
  const statewide = sortRows(aggregateCandidates(source), "votes", "desc");
  const selectedKey = statewide.some((row) => row.candidate_key === state.view.mapCandidate) ? state.view.mapCandidate : statewide[0]?.candidate_key;
  state.view.mapCandidate = selectedKey || "";
  const selector = document.querySelector("#map-candidate");
  selector.innerHTML = statewide.map((row) => `<option value="${row.candidate_key}" ${row.candidate_key === selectedKey ? "selected" : ""}>${row.ballot_number} · ${escapeHtml(row.candidate_name || row.ballot_name)}</option>`).join("");
  const office = state.data.overview.find((row) => row.office === source[0]?.office);
  document.querySelector("#candidate-summary").innerHTML = `${metric("Votos válidos", fmt.format(office.valid_votes), pct.format(office.valid_votes / office.total_votes))}${metric("Brancos", fmt.format(office.blank_votes), pct.format(office.blank_vote_rate))}${metric("Nulos", fmt.format(office.null_votes), pct.format(office.null_vote_rate))}${metric("Candidaturas / legendas", fmt.format(statewide.length), source[0]?.office || "Cargo selecionado")}`;
  const aggregated = aggregateCandidates(source, municipality, query);
  const total = sum(aggregated, "votes");
  aggregated.forEach((row) => { row.share = total ? row.votes / total : 0; row.display_name = row.candidate_name || row.ballot_name; row.status = row.round_result_status || row.candidacy_status || ""; });
  const rows = sortRows(aggregated, state.view.candidateSort.key, state.view.candidateSort.direction);
  document.querySelector("#candidate-title").textContent = source[0]?.office || "Resultado";
  document.querySelector("#candidate-caption").textContent = `${fmt.format(total)} votos nominais ou de legenda no recorte · ${rows.length} resultados`;
  document.querySelector("#candidate-chart").innerHTML = barChart(sortRows(aggregated, "votes", "desc").map((row) => ({ label: `${row.ballot_number} · ${row.display_name}${row.party_abbreviation ? ` (${row.party_abbreviation})` : ""}`, value: row.votes })), { candidate: true, limit: 15 });
  const hasParty = rows.some((row) => row.party_abbreviation); const hasStatus = rows.some((row) => row.status);
  const sort = state.view.candidateSort; const container = document.querySelector("#candidate-table");
  container.innerHTML = `<div class="data-table-wrap"><table><thead><tr>${sortHeader("Nº", "ballot_number", sort)}${sortHeader("Candidatura / legenda", "display_name", sort)}${hasParty ? sortHeader("Partido", "party_abbreviation", sort) : ""}${hasStatus ? sortHeader("Situação", "status", sort) : ""}${sortHeader("Votos", "votes", sort, true)}${sortHeader("% do recorte", "share", sort, true)}</tr></thead><tbody>${rows.map((row) => `<tr><td>${row.ballot_number}</td><td><strong>${escapeHtml(row.display_name)}</strong></td>${hasParty ? `<td>${escapeHtml(row.party_abbreviation || "—")}</td>` : ""}${hasStatus ? `<td>${escapeHtml(row.status || "—")}</td>` : ""}<td class="num">${fmt.format(row.votes)}</td><td class="num">${pct.format(row.share)}</td></tr>`).join("")}</tbody></table></div>`;
  bindSorting(container, sort, () => updateCandidates(source, municipality, query));
  const municipalTotals = new Map(); const selectedVotes = new Map();
  source.forEach((row) => { municipalTotals.set(row.municipality_code, (municipalTotals.get(row.municipality_code) || 0) + row.votes); if (candidateKey(row) === selectedKey) selectedVotes.set(row.municipality_code, (selectedVotes.get(row.municipality_code) || 0) + row.votes); });
  const mapRows = state.data.municipalities.map((item) => ({ ...item, share: (selectedVotes.get(item.municipality_code) || 0) / (municipalTotals.get(item.municipality_code) || 1) }));
  const selectedCandidate = statewide.find((row) => row.candidate_key === selectedKey);
  document.querySelector("#candidate-map-caption").textContent = selectedCandidate ? `${selectedCandidate.ballot_number} · ${selectedCandidate.candidate_name || selectedCandidate.ballot_name}` : "";
  document.querySelector("#candidate-ranking").innerHTML = barChart(sortRows(mapRows, "share", "desc").map((row) => ({ label: row.municipality_name, value: row.share })), { format: pct.format, limit: 14 });
  const chooseMunicipality = (code) => { document.querySelector("#candidate-municipality").value = code; updateCandidates(source, code, query); };
  renderMap("candidate-map", mapRows, "share", { format: pct.format, selected: municipality, onSelect: chooseMunicipality });
}

function renderExplorador() {
  const stored = sessionStorage.getItem("atlas-municipality") || ""; sessionStorage.removeItem("atlas-municipality");
  app.innerHTML = `${pageHead("Consulta detalhada", "Do estado até a seção.", "Aprofunde a consulta gradualmente. Cada seleção acrescenta contexto sem deixar a página vazia.", "Granularidade", "Totais pequenos exigem cautela e não descrevem a escolha individual de eleitores.")}
    <div class="filter-bar"><div class="field"><label for="explorer-municipality">Município</label><select id="explorer-municipality">${municipalityOptions(stored)}</select></div><div class="field"><label for="explorer-zone">Zona</label><select id="explorer-zone" disabled><option>Selecione o município</option></select></div><div class="field"><label for="explorer-section">Seção</label><select id="explorer-section" disabled><option>Selecione a zona</option></select></div></div><div id="section-detail" class="section-card"></div>`;
  const municipalitySelect = document.querySelector("#explorer-municipality");
  const zoneSelect = document.querySelector("#explorer-zone"); const sectionSelect = document.querySelector("#explorer-section");
  const currentMunicipality = () => state.data.section_index.find((row) => row.municipality_code === municipalitySelect.value);
  const showState = () => {
    const president = byOffice(state.data.overview, "Presidente");
    document.querySelector("#section-detail").innerHTML = `<span class="eyebrow">Ceará · primeiro turno</span><h2>Comece pelo município</h2><p>Enquanto você escolhe, este resumo estadual mantém o contexto da consulta.</p><section class="metric-grid compact-metrics">${metric("Municípios", "184", "Cobertura estadual")}${metric("Zonas", "205", "Pares município/zona")}${metric("Seções", fmt.format(state.data.section_count), "Seções apuradas")}${metric("Comparecimento", pct.format(president.turnout_rate), "Referência: Presidente")}</section>`;
  };
  const showMunicipality = () => {
    const item = currentMunicipality(); if (!item) { showState(); return; }
    const rows = state.data.municipality_summary.filter((row) => row.municipality_code === item.municipality_code);
    const president = byOffice(rows, "Presidente");
    document.querySelector("#section-detail").innerHTML = `<span class="eyebrow">${escapeHtml(item.municipality_name)} · visão municipal</span><h2>${escapeHtml(item.municipality_name)}</h2><p>Selecione uma das ${item.zones.length} zonas para continuar ou consulte o panorama municipal abaixo.</p><section class="metric-grid compact-metrics">${metric("Aptos", fmt.format(president.eligible_voters), "Presidente")}${metric("Comparecimento", fmt.format(president.turnout), pct.format(president.turnout_rate))}${metric("Abstenção", fmt.format(president.abstentions), pct.format(president.abstention_rate))}${metric("Zonas", fmt.format(item.zones.length), `${fmt.format(item.zones.reduce((total, zone) => total + zone.sections.length, 0))} seções`)}</section><div class="section-heading"><h2>Composição por cargo</h2></div>${officeComposition(rows)}`;
  };
  const showZone = () => {
    const item = currentMunicipality(); const zone = item?.zones.find((row) => row.zone === zoneSelect.value); if (!zone) { showMunicipality(); return; }
    const rows = state.data.zone_summary.filter((row) => row.municipality_code === item.municipality_code && row.zone === zone.zone);
    const president = byOffice(rows, "Presidente");
    document.querySelector("#section-detail").innerHTML = `<span class="eyebrow">${escapeHtml(item.municipality_name)} · Zona ${zone.zone}</span><h2>${zone.sections.length} seções na zona</h2><p>Selecione uma seção no filtro ou na lista para abrir seus resultados.</p><section class="metric-grid compact-metrics">${metric("Aptos", fmt.format(president.eligible_voters), "Presidente")}${metric("Comparecimento", fmt.format(president.turnout), pct.format(president.turnout_rate))}${metric("Abstenção", fmt.format(president.abstentions), pct.format(president.abstention_rate))}${metric("Seções", fmt.format(zone.sections.length), "Zona selecionada")}</section><div class="section-heading"><h2>Seções e locais</h2></div><div class="section-list">${zone.sections.map((section) => `<button data-open-section="${section.section}"><strong>Seção ${section.section}</strong><span>${escapeHtml(section.voting_place_name)}</span></button>`).join("")}</div>`;
    document.querySelectorAll("[data-open-section]").forEach((button) => button.addEventListener("click", () => { sectionSelect.value = button.dataset.openSection; loadSection(item.municipality_code, zone.zone, button.dataset.openSection); }));
  };
  const updateMunicipality = () => {
    const item = currentMunicipality();
    zoneSelect.innerHTML = item ? `<option value="">Selecione</option>${item.zones.map((zone) => `<option>${zone.zone}</option>`).join("")}` : `<option>Selecione o município</option>`;
    zoneSelect.disabled = !item; sectionSelect.innerHTML = `<option>Selecione a zona</option>`; sectionSelect.disabled = true; showMunicipality();
  };
  const updateZone = () => {
    const item = currentMunicipality(); const zone = item?.zones.find((row) => row.zone === zoneSelect.value);
    sectionSelect.innerHTML = zone ? `<option value="">Selecione</option>${zone.sections.map((section) => `<option value="${section.section}">${section.section} · ${escapeHtml(section.voting_place_name)}</option>`).join("")}` : `<option>Selecione a zona</option>`;
    sectionSelect.disabled = !zone; showZone();
  };
  municipalitySelect.addEventListener("change", updateMunicipality); zoneSelect.addEventListener("change", updateZone);
  sectionSelect.addEventListener("change", () => sectionSelect.value ? loadSection(municipalitySelect.value, zoneSelect.value, sectionSelect.value) : showZone());
  if (stored) updateMunicipality(); else showState();
}

async function loadSection(municipality, zone, section) {
  const target = document.querySelector("#section-detail");
  target.innerHTML = `<div class="empty"><div><strong>Carregando a seção ${section}</strong>Buscando o bloco da zona ${zone}.</div></div>`;
  try {
    const payload = await loadJson(`assets/data/sections/${municipality}-${zone}.json`);
    const summaries = expandFrame(payload.summaries).filter((row) => row.section === section).map((row) => ({ ...row, municipality_name: payload.municipality_name }));
    const results = expandFrame(payload.results).filter((row) => row.section === section);
    const first = summaries[0]; const president = byOffice(summaries, "Presidente");
    target.innerHTML = `<span class="eyebrow">${escapeHtml(first.municipality_name)} · Zona ${zone}</span><h2>Seção ${section}</h2><p>${escapeHtml(first.voting_place_name)} · ${escapeHtml(first.voting_place_address)}</p><section class="metric-grid compact-metrics">${metric("Aptos · Presidente", fmt.format(president.eligible_voters), "Universo do cargo")}${metric("Comparecimento", fmt.format(president.turnout), pct.format(president.turnout_rate))}${metric("Abstenção", fmt.format(president.abstentions), pct.format(president.abstention_rate))}${metric("Situação", first.section_installed === "S" ? "Instalada" : first.section_installed, first.section_annulled === "S" ? "Seção anulada" : "Sem indicação de anulação")}</section><div class="section-heading"><h2>Resultados por cargo</h2></div><div class="panel-grid">${summaries.map((summary) => { const rows = results.filter((row) => row.office === summary.office).sort((a, b) => b.votes - a.votes); return `<article class="panel"><h3>${escapeHtml(summary.office)}</h3><p class="panel-intro">${fmt.format(summary.total_votes)} votos registrados</p>${stacked(summary)}<div class="chart-spacing">${barChart(rows.map((row) => ({ label: row.result_type === "blank" ? "Voto branco" : row.result_type === "null" ? "Voto nulo" : `${row.ballot_number} · ${row.candidate_name || row.ballot_name}${row.party_abbreviation ? ` (${row.party_abbreviation})` : ""}`, value: row.votes })), { candidate: true, limit: 12 })}</div></article>`; }).join("")}</div><p class="note"><strong>Privacidade e interpretação.</strong> A urna publica totais agregados por seção; o voto individual continua secreto. Logs técnicos não são usados nesta consulta.</p>`;
  } catch (error) {
    target.innerHTML = `<div class="empty"><div><strong>Não foi possível abrir a seção.</strong>${escapeHtml(error.message)}</div></div>`;
  }
}

const routes = { overview: renderOverview, municipios: renderMunicipios, eleitorado: renderEleitorado, cargos: renderCargos, explorador: renderExplorador };
async function navigate() {
  const route = location.hash.slice(1) || "overview"; state.route = routes[route] ? route : "overview"; state.view = {};
  document.querySelectorAll("[data-route]").forEach((link) => link.classList.toggle("active", link.dataset.route === state.route));
  document.querySelector("#main-nav").classList.remove("open"); document.querySelector(".menu-button").setAttribute("aria-expanded", "false");
  await routes[state.route](); document.title = `${document.querySelector("h1")?.textContent || "Atlas Eleitoral"} · Ceará 2026`; window.scrollTo(0, 0);
}

document.querySelector(".menu-button").addEventListener("click", (event) => { const nav = document.querySelector("#main-nav"); const open = nav.classList.toggle("open"); event.currentTarget.setAttribute("aria-expanded", String(open)); });
const dialog = document.querySelector("#methodology-dialog");
document.querySelector("#methodology-button").addEventListener("click", () => dialog.showModal());
document.querySelector("#methodology-close").addEventListener("click", () => dialog.close());

loadJson("assets/data/atlas.json").then((data) => {
  state.data = data; loading.hidden = true;
  document.querySelector("#methodology-content").innerHTML = `<p>O atlas usa exclusivamente tabelas Gold derivadas dos arquivos oficiais de resultados, detalhe por seção, perfil do eleitorado e candidaturas publicados pelo Tribunal Superior Eleitoral.</p><h3>Datas e recorte</h3><p>Primeiro turno de 2026 no Ceará, realizado em 4 de outubro. Cada cargo conserva seu código de eleição e seu universo de aptos.</p><h3>Percentuais</h3><p>Comparecimento e abstenção usam aptos como denominador. Brancos e nulos usam o total de votos do cargo. Percentuais de candidatura usam apenas votos válidos; para Senado, cada eleitor podia registrar dois votos.</p><h3>Perfil cadastral</h3><p>Gênero, idade, escolaridade, biometria, deficiência e nome social descrevem o cadastro eleitoral. Não indicam comparecimento nem escolha de candidatura.</p><h3>Logs e limitações</h3><p>Logs de urna registram eventos técnicos, aplicações e severidades; não são votos nem resultados. Os 316 timestamps atípicos permanecem preservados na Gold de logs e não alimentam estas cinco páginas.</p><h3>Fonte</h3><p>TSE, Portal de Dados Abertos. Compilação Gold esquema ${escapeHtml(data.metadata.schema_version)}.</p>`;
  window.addEventListener("hashchange", navigate); navigate();
}).catch((error) => { loading.hidden = true; app.innerHTML = `<div class="empty"><div><strong>Não foi possível abrir o atlas.</strong>${escapeHtml(error.message)}</div></div>`; });
