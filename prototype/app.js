const MIN_YEAR = -3400;
const MAX_YEAR = 2024;
const SPEEDS = [1, 2, 4];
const COLORS = [
  "#6d8f78", "#ad8c63", "#7589a6", "#9b6f79", "#809b5c", "#a77f9d",
  "#5f9692", "#b09551", "#8473a5", "#a36f55", "#6f91ad", "#8a9b75"
];

const elements = {
  loading: document.querySelector("#loading"),
  loadingDetail: document.querySelector("#loading-detail"),
  yearLabel: document.querySelector("#year-label"),
  yearInput: document.querySelector("#year-input"),
  yearSlider: document.querySelector("#year-slider"),
  playButton: document.querySelector("#play-button"),
  speedButton: document.querySelector("#speed-button"),
  stepLabel: document.querySelector("#step-label"),
  activeCount: document.querySelector("#active-count"),
  detailPanel: document.querySelector("#detail-panel"),
  detailTitle: document.querySelector("#detail-title"),
  detailOriginal: document.querySelector("#detail-original"),
  detailPeriod: document.querySelector("#detail-period"),
  detailArea: document.querySelector("#detail-area"),
  detailGeometryStatus: document.querySelector("#detail-geometry-status"),
  detailRelation: document.querySelector("#detail-relation"),
  detailNameReview: document.querySelector("#detail-name-review"),
  detailSource: document.querySelector("#detail-source"),
  detailLinks: document.querySelector("#detail-links"),
  aboutPanel: document.querySelector("#about-panel")
};

let map;
let collection;
let modernCollection;
let activeCollection;
let year = 1800;
let playing = false;
let speedIndex = 0;
let playTimer = null;
let selectedId = null;
let ready = false;
let labelMarkers = [];

function formatYear(value) {
  return value < 0 ? `公元前 ${Math.abs(value)} 年` : `公元 ${value} 年`;
}

function stepSize(value) {
  if (value < -1000) return 100;
  if (value < 500) return 25;
  if (value < 1500) return 10;
  return 1;
}

function activeFilter(value) {
  return [
    "all",
    ["<=", ["get", "FromYear"], value],
    [">=", ["get", "ToYear"], value]
  ];
}

function closeDetail() {
  selectedId = null;
  elements.detailPanel.hidden = true;
  if (ready) map.setFilter("selected-outline", ["==", ["get", "id"], -1]);
}

function makeLink(label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = `${label} ↗`;
  link.target = "_blank";
  link.rel = "noreferrer";
  return link;
}

function localizedName(name) {
  const cleaned = name.replace(/^\(|\)$/g, "");
  const feature = collection?.features.find((item) => item.properties.Name === cleaned)
    || modernCollection?.features.find((item) => item.properties.Name === cleaned);
  return feature?.properties.NameZh || cleaned;
}

function showDetail(properties) {
  selectedId = properties.id;
  elements.detailTitle.textContent = properties.NameZh;
  elements.detailOriginal.textContent = properties.Name;
  const periodLabel = properties.GeometryStatus === "source" ? "几何版本有效期" : "显示区间";
  elements.detailPeriod.textContent = `${periodLabel}：${formatYear(properties.FromYear)} — ${formatYear(properties.ToYear)}`;
  elements.detailArea.textContent = properties.Area > 0
    ? `${Math.round(properties.Area).toLocaleString("zh-CN")} km²`
    : "未提供";
  if (properties.GeometryStatus === "carry-forward") {
    elements.detailGeometryStatus.textContent = `推断延续 · 源几何为 ${formatYear(properties.SourceFromYear)}`;
  } else if (properties.GeometryStatus === "reference") {
    elements.detailGeometryStatus.textContent = "现代参考几何 · 待人工审定";
  } else {
    elements.detailGeometryStatus.textContent = "来源原始几何 · 未按现代岸线裁切";
  }
  if (properties.Components) {
    const members = properties.Components.split(";").map(localizedName).join("、");
    elements.detailRelation.textContent = `复合政治实体 · 成员：${members}`;
  } else if (properties.MemberOf) {
    elements.detailRelation.textContent = `关系成员 · 属于：${localizedName(properties.MemberOf)}`;
  } else {
    elements.detailRelation.textContent = "来源未标注从属关系";
  }
  const nameReviewLabels = {
    wikidata: "Wikidata 中文标签",
    override: "本地译名 · 待审校",
    "natural-earth": "Natural Earth 中文名 · 待审定",
    pending: "待翻译"
  };
  elements.detailNameReview.textContent = nameReviewLabels[properties.NameReview] || "待审校";
  elements.detailSource.textContent = year === 2024
    ? "2024 底稿：Natural Earth 50m · 公共领域 · 待人工审定；保留来源的主权国与地区分类，不代表本项目立场。"
    : "几何来源：Cliopatria v0.2.1 · CC BY 4.0；几何有效期不等于政权建立与灭亡时间。";
  elements.detailLinks.replaceChildren();
  if (properties.Wikipedia) {
    const article = encodeURIComponent(properties.Wikipedia.replaceAll(" ", "_"));
    elements.detailLinks.append(makeLink("Wikipedia", `https://en.wikipedia.org/wiki/${article}`));
  }
  if (/^Q\d+$/.test(properties.Wikidata)) {
    elements.detailLinks.append(makeLink("Wikidata", `https://www.wikidata.org/wiki/${properties.Wikidata}`));
  }
  elements.detailPanel.hidden = false;
  elements.aboutPanel.hidden = true;
  map.setFilter("selected-outline", ["==", ["get", "id"], selectedId]);
}

function updateLabels() {
  if (!ready || !activeCollection) return;
  labelMarkers.forEach((marker) => marker.remove());
  labelMarkers = [];
  const zoom = map.getZoom();
  const limit = zoom < 2 ? 45 : zoom < 3.5 ? 60 : 90;
  const candidates = activeCollection.features
    .filter((feature) => (
      feature.properties.role !== "composite"
      && feature.properties.FromYear <= year
      && feature.properties.ToYear >= year
    ))
    .sort((a, b) => (
      Number(b.properties.GeometryStatus === "carry-forward") - Number(a.properties.GeometryStatus === "carry-forward")
      || b.properties.LabelPriority - a.properties.LabelPriority
    ));
  const seenNames = new Set();
  const features = [];
  for (const feature of candidates) {
    if (seenNames.has(feature.properties.NameZh)) continue;
    seenNames.add(feature.properties.NameZh);
    features.push(feature);
    if (features.length === limit) break;
  }
  features.forEach((feature) => {
    const properties = feature.properties;
    if (!properties.LabelPoint) return;
    const label = document.createElement("div");
    label.className = "polity-label";
    label.textContent = properties.NameZh;
    if (properties.GeometryStatus === "carry-forward") label.classList.add("is-inferred");
    if (properties.role === "composite") label.classList.add("is-composite");
    labelMarkers.push(new maplibregl.Marker({ element: label, anchor: "center" })
      .setLngLat(properties.LabelPoint)
      .addTo(map));
  });
}

function updateActiveCount() {
  if (!activeCollection) return;
  const active = activeCollection.features.filter((feature) => (
    feature.properties.FromYear <= year && feature.properties.ToYear >= year
  ));
  const inferred = active.some((feature) => feature.properties.GeometryStatus === "carry-forward");
  const suffix = year === 2024 ? " · 现代参考层（待审定）" : inferred ? " · 含推断延续几何" : "";
  elements.activeCount.textContent = `${formatYear(year)} · ${active.length.toLocaleString("zh-CN")} 个政治实体记录${suffix}`;
}

function setYear(nextYear) {
  year = Math.max(MIN_YEAR, Math.min(MAX_YEAR, Math.round(nextYear)));
  elements.yearLabel.textContent = formatYear(year);
  elements.yearInput.value = year;
  elements.yearSlider.value = year;
  const size = stepSize(year);
  elements.stepLabel.textContent = `${year < 1500 ? "历史时期" : "现代时期"}每次前进 ${size} 年`;
  document.querySelectorAll("[data-year]").forEach((button) => {
    button.classList.toggle("is-active", Number(button.dataset.year) === year);
  });
  const nextCollection = year === 2024 ? modernCollection : collection;
  if (ready && nextCollection !== activeCollection) closeDetail();
  if (ready) {
    activeCollection = nextCollection;
    const activeFeatures = activeCollection.features.filter((feature) => (
      feature.properties.FromYear <= year && feature.properties.ToYear >= year
    ));
    map.getSource("cliopatria").setData({ type: "FeatureCollection", features: activeFeatures });
    map.setFilter("polity-fill", activeFilter(year));
    map.setFilter("polity-line", activeFilter(year));
    if (selectedId !== null) {
      const selected = activeCollection.features[selectedId];
      if (!selected || selected.properties.FromYear > year || selected.properties.ToYear < year) closeDetail();
    }
    updateLabels();
  }
  updateActiveCount();
  if (year === MAX_YEAR && playing) stopPlayback();
}

function moveYear(direction) {
  const size = stepSize(year);
  setYear(year + direction * size);
}

function stopPlayback() {
  playing = false;
  if (playTimer !== null) clearInterval(playTimer);
  playTimer = null;
  elements.playButton.innerHTML = "▶ <span>播放</span>";
  elements.playButton.setAttribute("aria-label", "播放");
}

function startPlayback() {
  if (!ready) return;
  if (year === MAX_YEAR) setYear(MIN_YEAR);
  playing = true;
  elements.playButton.innerHTML = "Ⅱ <span>暂停</span>";
  elements.playButton.setAttribute("aria-label", "暂停");
  const interval = 700 / SPEEDS[speedIndex];
  playTimer = setInterval(() => moveYear(1), interval);
}

function bindControls() {
  elements.yearSlider.addEventListener("input", (event) => setYear(Number(event.target.value)));
  elements.yearInput.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    if (Number.isFinite(value)) setYear(value);
  });
  document.querySelector("#previous-year").addEventListener("click", () => moveYear(-1));
  document.querySelector("#next-year").addEventListener("click", () => moveYear(1));
  elements.playButton.addEventListener("click", () => playing ? stopPlayback() : startPlayback());
  elements.speedButton.addEventListener("click", () => {
    speedIndex = (speedIndex + 1) % SPEEDS.length;
    elements.speedButton.textContent = `${SPEEDS[speedIndex]}×`;
    if (playing) {
      stopPlayback();
      startPlayback();
    }
  });
  document.querySelectorAll("[data-year]").forEach((button) => {
    button.addEventListener("click", () => setYear(Number(button.dataset.year)));
  });
  document.querySelector("#close-detail").addEventListener("click", closeDetail);
  document.querySelector("#about-button").addEventListener("click", () => {
    elements.aboutPanel.hidden = !elements.aboutPanel.hidden;
    elements.detailPanel.hidden = true;
  });
  document.querySelector("#close-about").addEventListener("click", () => {
    elements.aboutPanel.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement) return;
    if (event.code === "Space") {
      event.preventDefault();
      playing ? stopPlayback() : startPlayback();
    } else if (event.key === "ArrowLeft") {
      moveYear(-1);
    } else if (event.key === "ArrowRight") {
      moveYear(1);
    } else if (event.key === "Escape") {
      closeDetail();
      elements.aboutPanel.hidden = true;
    }
  });
}

function addDataLayers(base) {
  const baseSources = {
    "natural-earth-land": base.land,
    "natural-earth-lakes": base.lakes,
    "natural-earth-rivers": base.rivers,
    "natural-earth-coastline": base.coastline
  };
  Object.entries(baseSources).forEach(([id, data]) => {
    const source = { type: "geojson", data };
    if (id === "natural-earth-land") source.attribution = "Natural Earth · Public domain";
    map.addSource(id, source);
  });
  map.addLayer({
    id: "land-fill",
    type: "fill",
    source: "natural-earth-land",
    paint: { "fill-color": "#293d34" }
  });

  map.addSource("cliopatria", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: activeCollection.features.filter((feature) => (
        feature.properties.FromYear <= year && feature.properties.ToYear >= year
      ))
    },
    attribution: "Cliopatria © Seshat Global History Databank · CC BY 4.0 | 2024 reference: Natural Earth · Public domain"
  });
  const colorExpression = ["match", ["get", "color"]];
  COLORS.forEach((color, index) => colorExpression.push(index, color));
  colorExpression.push(COLORS[0]);
  map.addLayer({
    id: "polity-fill",
    type: "fill",
    source: "cliopatria",
    filter: activeFilter(year),
    paint: {
      "fill-color": colorExpression,
      "fill-opacity": ["match", ["get", "role"], "composite", 0.3, 0.76]
    }
  });
  map.addLayer({
    id: "lake-fill",
    type: "fill",
    source: "natural-earth-lakes",
    paint: { "fill-color": "#102a34" }
  });
  map.addLayer({
    id: "river-line",
    type: "line",
    source: "natural-earth-rivers",
    paint: { "line-color": "#37616b", "line-width": 0.65, "line-opacity": 0.75 }
  });
  map.addLayer({
    id: "coastline-line",
    type: "line",
    source: "natural-earth-coastline",
    paint: { "line-color": "#799486", "line-width": 0.65, "line-opacity": 0.35 }
  });
  map.addLayer({
    id: "polity-line",
    type: "line",
    source: "cliopatria",
    filter: activeFilter(year),
    paint: { "line-color": "rgba(235, 241, 220, 0.62)", "line-width": 0.55 }
  });
  map.addLayer({
    id: "selected-outline",
    type: "line",
    source: "cliopatria",
    filter: ["==", ["get", "id"], -1],
    paint: { "line-color": "#efffba", "line-width": 2.4 }
  });
  ready = true;
  elements.loading.hidden = true;
  setYear(year);
}

async function fetchGeoJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  const data = await response.json();
  if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) {
    throw new Error(`${path} 不是有效的 FeatureCollection`);
  }
  return data;
}

async function loadData() {
  try {
    elements.loadingDetail.textContent = "正在加载陆地、海洋、水系、中文名称与历史边界…";
    const [historical, modern, land, lakes, rivers, coastline] = await Promise.all([
      fetchGeoJson("./data/cliopatria.geojson"),
      fetchGeoJson("./data/modern-2024.geojson"),
      fetchGeoJson("./data/natural-earth/land.geojson"),
      fetchGeoJson("./data/natural-earth/lakes.geojson"),
      fetchGeoJson("./data/natural-earth/rivers_lake_centerlines.geojson"),
      fetchGeoJson("./data/natural-earth/coastline.geojson")
    ]);
    collection = historical;
    modernCollection = modern;
    activeCollection = collection;
    addDataLayers({ land, lakes, rivers, coastline });
  } catch (error) {
    elements.loading.classList.add("is-error");
    elements.loading.querySelector("strong").textContent = "本地数据加载失败";
    elements.loadingDetail.textContent = `${error.message}。请先运行数据准备脚本，再通过本地 HTTP 服务打开。`;
    console.error(error);
  }
}

function initializeMap() {
  map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": "#102a34" } }]
    },
    center: [12, 24],
    zoom: 1.25,
    minZoom: 0.7,
    maxZoom: 10,
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
    renderWorldCopies: false
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.on("load", loadData);
  map.on("zoomend", updateLabels);
  map.on("click", "polity-fill", (event) => {
    const feature = event.features?.find((item) => item.properties.role !== "composite")
      || event.features?.[0];
    if (feature) showDetail(feature.properties);
  });
  map.on("mouseenter", "polity-fill", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "polity-fill", () => { map.getCanvas().style.cursor = ""; });
}

bindControls();
setYear(year);
initializeMap();
