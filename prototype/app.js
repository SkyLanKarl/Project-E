const MIN_YEAR = -3400;
const MAX_YEAR = 2024;
const TIMELINE_NODES = [-3400, -3000, -2000, -1000, -500, 0, 250, 500, 750, 1000, 1250, 1500, 1650, 1800, 1914, 1918, 1939, 1945, 1950, 2000, 2024];
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
  yearHandle: document.querySelector("#year-handle"),
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
  detailAttributes: document.querySelector("#detail-attributes"),
  attributeNote: document.querySelector("#attribute-note"),
  baseSelect: document.querySelector("#base-select"),
  chgisControl: document.querySelector("#chgis-control"),
  chgisToggle: document.querySelector("#chgis-toggle"),
  aboutPanel: document.querySelector("#about-panel")
};

let map;
let collection;
let polityAttributes = { entities: {}, relatedEntities: {}, labels: {} };
let modernCollection;
let activeCollection;
let year = 1800;
let playing = false;
let speedIndex = 0;
let playTimer = null;
let selectedId = null;
let ready = false;
let labelMarkers = [];
let baseMode = new URLSearchParams(window.location.search).get("base") === "dlr" ? "dlr" : "natural-earth";
let chgisCollection = null;
let chgisEnabled = false;

function formatYear(value) {
  if (value === 0) return "公元 0 年";
  return value < 0 ? `公元前 ${Math.abs(value)} 年` : `公元 ${value} 年`;
}

function nearestTimelineIndex(value) {
  let nearest = 0;
  for (let index = 1; index < TIMELINE_NODES.length; index += 1) {
    if (Math.abs(TIMELINE_NODES[index] - value) < Math.abs(TIMELINE_NODES[nearest] - value)) nearest = index;
  }
  return nearest;
}

function timelinePercent(yearValue) {
  return nearestTimelineIndex(yearValue) / (TIMELINE_NODES.length - 1) * 100;
}

function eraForYear(yearValue) {
  if (yearValue < -2000) return "远古文明";
  if (yearValue < -500) return "早期帝国";
  if (yearValue < 500) return "古典时代";
  if (yearValue < 1000) return "中世纪早期";
  if (yearValue < 1250) return "中世纪中期";
  if (yearValue < 1500) return "中世纪晚期";
  if (yearValue < 1650) return "大航海时代";
  if (yearValue < 1800) return "近代早期";
  if (yearValue < 1914) return "工业时代";
  if (yearValue < 1918) return "第一次世界大战";
  if (yearValue < 1939) return "战间期";
  if (yearValue < 1945) return "第二次世界大战";
  if (yearValue < 2000) return "战后时期";
  return "当代";
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

function attributeDateYear(value) {
  const match = /^([+-])(\d+)-/.exec(value || "");
  if (!match) return null;
  return Number(match[2]) * (match[1] === "-" ? -1 : 1);
}

function attributeQualifierYears(claim, property) {
  return (claim.qualifiers?.[property] || [])
    .map((value) => attributeDateYear(value.date))
    .filter(Number.isFinite);
}

function attributeMatchesYear(claim, selectedYear) {
  const starts = attributeQualifierYears(claim, "P580");
  const ends = attributeQualifierYears(claim, "P582");
  const points = attributeQualifierYears(claim, "P585");
  if (starts.length && selectedYear < Math.min(...starts)) return false;
  if (ends.length && selectedYear > Math.max(...ends)) return false;
  if (points.length && !points.includes(selectedYear)) return false;
  return true;
}

function attributeHasTime(claim) {
  return ["P580", "P582", "P585"].some((property) => claim.qualifiers?.[property]?.length);
}

function quantityText(claims, fallbackUnit = "") {
  const candidates = claims.filter((claim) => Number.isFinite(claim.value?.amount));
  const sorted = candidates.sort((a, b) => {
    const aYears = attributeQualifierYears(a, "P585");
    const bYears = attributeQualifierYears(b, "P585");
    const aDistance = aYears.length ? Math.abs(aYears[0] - year) : Infinity;
    const bDistance = bYears.length ? Math.abs(bYears[0] - year) : Infinity;
    return aDistance - bDistance
      || Number(b.rank === "preferred") - Number(a.rank === "preferred");
  });
  if (!sorted.length) return "未提供";
  const claim = sorted[0];
  const recordYears = attributeQualifierYears(claim, "P585");
  const record = recordYears.length ? `${formatYear(recordYears[0])}记录` : "年份未注明";
  const unitId = claim.value.unit?.startsWith("http") ? claim.value.unit.split("/").pop() : "";
  const unit = polityAttributes.labels[unitId]?.label || fallbackUnit;
  return `${claim.value.amount.toLocaleString("zh-CN")}${unit ? ` ${unit}` : ""}（${record}）`;
}

function capitalCoordinatesText(entity) {
  const capitals = (entity.capital || []).filter((claim) => attributeMatchesYear(claim, year));
  const values = capitals.map((claim) => {
    const id = claim.value?.id;
    const coordinates = polityAttributes.relatedEntities?.[id]?.capitalCoordinates || [];
    const coordinate = coordinates.find((claim) => claim.rank === "preferred") || coordinates[0];
    if (!Number.isFinite(coordinate?.value?.latitude) || !Number.isFinite(coordinate?.value?.longitude)) return null;
    const label = polityAttributes.labels[id]?.label || id;
    return `${label}：${coordinate.value.latitude.toFixed(4)}, ${coordinate.value.longitude.toFixed(4)}`;
  }).filter(Boolean);
  if (!capitals.length) return "当前年份无匹配记录";
  return values.length ? [...new Set(values)].join("；") : "未提供坐标";
}

function positionsHeldText(entity) {
  const leaders = ["headOfState", "headOfGovernment"].flatMap((field) => (
    (entity[field] || []).filter((claim) => attributeMatchesYear(claim, year))
  ));
  const values = leaders.flatMap((leader) => {
    const id = leader.value?.id;
    const positions = polityAttributes.relatedEntities?.[id]?.positionsHeld || [];
    return positions.filter((claim) => attributeMatchesYear(claim, year)).map((claim) => {
      const person = polityAttributes.labels[id]?.label || id;
      const positionId = claim.value?.id;
      const position = polityAttributes.labels[positionId]?.label || positionId || "未知职务";
      return `${person}：${position}${attributeHasTime(claim) ? "" : "（时间未注明）"}`;
    });
  });
  if (!leaders.length) return "当前年份无匹配记录";
  return values.length ? [...new Set(values)].join("；") : "未提供任职记录";
}

function updatePolityAttributes(properties) {
  const entity = polityAttributes.entities[properties.Wikidata];
  const areaClaims = entity?.area || [];
  const hasGeometryArea = properties.Area > 0;
  const hasWikidataArea = !hasGeometryArea && areaClaims.length > 0;
  elements.detailArea.textContent = hasGeometryArea
    ? `${Math.round(properties.Area).toLocaleString("zh-CN")} km²`
    : hasWikidataArea ? quantityText(areaClaims) : "";
  elements.detailArea.closest("div").hidden = !hasGeometryArea && !hasWikidataArea;
  let visible = 0;
  const showAttribute = (field, text) => {
    const value = document.querySelector(`#attribute-${field}`);
    const unavailable = !text || [
      "未提供", "当前年份无匹配记录", "未提供坐标", "未提供任职记录"
    ].includes(text);
    value.textContent = text;
    value.closest("div").hidden = unavailable;
    if (!unavailable) visible += 1;
  };
  const fields = [
    "capital", "population", "officialLanguage", "religion", "currency",
    "governmentForm", "headOfState", "headOfGovernment", "predecessor", "successor",
    "entityType", "partOf", "hasParts", "administrativeDivisions", "diplomaticRelations", "memberOf"
  ];
  fields.forEach((field) => {
    const claims = entity?.[field] || [];
    let text = "";
    if (field === "population" && claims.length) {
      text = quantityText(claims, "人");
    } else if (claims.length) {
      const matching = claims.filter((claim) => attributeMatchesYear(claim, year));
      text = matching.length
        ? [...new Set(matching.map((claim) => {
          const id = claim.value?.id;
          const label = polityAttributes.labels[id]?.label || id || claim.value?.text || "未知";
          return attributeHasTime(claim) ? label : `${label}（时间未注明）`;
        }))].join("、")
        : "当前年份无匹配记录";
    }
    showAttribute(field, text);
  });
  showAttribute("capitalCoordinates", entity ? capitalCoordinatesText(entity) : "");
  showAttribute("positionsHeld", entity ? positionsHeldText(entity) : "");
  elements.detailAttributes.hidden = visible === 0;
  elements.attributeNote.hidden = visible === 0;
  return visible > 0 || hasWikidataArea;
}

function showDetail(properties) {
  selectedId = properties.id;
  elements.detailTitle.textContent = properties.NameZh;
  elements.detailOriginal.textContent = properties.Name;
  if (properties.role === "chgis-prefecture") {
    elements.detailPeriod.textContent = `政区记录有效期：${formatYear(properties.FromYear)} — ${formatYear(properties.ToYear)}；来自 CHGIS，不代表政权存续期。`;
  } else if (properties.role === "claim" || properties.role === "disputed") {
    elements.detailPeriod.textContent = "非政治实体 · 不适用政权存续时间";
  } else {
    const subject = properties.role === "admin-province" ? "行政区存续时间" : "政权存续时间";
    const hasFrom = Number.isFinite(properties.PolityFromYear);
    const hasTo = Number.isFinite(properties.PolityToYear);
    const fromText = hasFrom
      ? `${properties.PolityFromPrecision < 9 ? "约" : ""}${formatYear(properties.PolityFromYear)}`
      : "";
    const toText = hasTo
      ? `${properties.PolityToPrecision < 9 ? "约" : ""}${formatYear(properties.PolityToYear)}`
      : "";
    let period = "待核实（当前数据未提供独立起止年份）";
    if (hasFrom && hasTo) period = `${fromText} — ${toText}`;
    if (hasFrom && !hasTo) period = `${fromText} 起；结束时间待核实`;
    if (!hasFrom && hasTo) period = `起始时间待核实 — ${toText}`;
    const source = properties.PolityDateSource ? `（${properties.PolityDateSource}，待审校）` : "";
    const multiple = properties.PolityDateMultiple ? "；存在多个候选日期" : "";
    elements.detailPeriod.textContent = `${subject}：${period}${source}${multiple}`;
  }
  if (properties.GeometryStatus === "claim") {
    elements.detailGeometryStatus.textContent = "主张边界 · 起始年及线段版本待核";
  } else if (properties.GeometryStatus === "disputed") {
    elements.detailGeometryStatus.textContent = "争议区域叠加 · 不改变现有边界";
  } else if (properties.GeometryStatus === "carry-forward") {
    elements.detailGeometryStatus.textContent = `推断延续 · 源几何为 ${formatYear(properties.SourceFromYear)}`;
  } else if (properties.GeometryStatus === "reference") {
    elements.detailGeometryStatus.textContent = "现代参考几何 · 待人工审定";
  } else {
    elements.detailGeometryStatus.textContent = "来源原始几何 · 未按现代岸线裁切";
  }
  if (properties.role === "claim") {
    elements.detailRelation.textContent = "非政治实体 · 不作为法定国界";
  } else if (properties.role === "disputed") {
    elements.detailRelation.textContent = "争议区域 · 不表示主权归属结论";
  } else if (properties.role === "chgis-prefecture") {
    elements.detailRelation.textContent = "CHGIS 府级政区 · 仅本地研究层";
  } else if (properties.role === "admin-province") {
    elements.detailRelation.textContent = "中国省级行政区 · 2024 年参考";
  } else if (properties.Components) {
    const members = properties.Components.split(";").map(localizedName).join("、");
    elements.detailRelation.textContent = `复合政治实体 · 成员：${members}`;
  } else if (properties.MemberOf) {
    elements.detailRelation.textContent = `关系成员 · 属于：${localizedName(properties.MemberOf)}`;
  } else {
    elements.detailRelation.textContent = "";
  }
  elements.detailRelation.closest("div").hidden = !elements.detailRelation.textContent;
  const nameReviewLabels = {
    wikidata: "Wikidata 中文标签",
    override: "本地译名 · 待审校",
    "natural-earth": "Natural Earth 中文名 · 待审定",
    "world-bank": "World Bank 来源名称",
    chgis: "CHGIS 中文名称",
    datav: "DataV 中文行政区名 · 待审定",
    pending: "待翻译"
  };
  elements.detailNameReview.textContent = nameReviewLabels[properties.NameReview] || "待审校";
  const hasAttributes = updatePolityAttributes(properties);
  let sourceText;
  if (properties.Source === "CHGIS") {
    sourceText = "来源：CHGIS Version 6. (c) Fairbank Center for Chinese Studies and the Institute for Chinese Historical Geography at Fudan University, Dec 2016. 仅限非商业学术研究；完整图层不得公开再分发。";
  } else if (properties.Source === "World Bank") {
    sourceText = "来源：World Bank Official Boundaries · 高精度现代参考数据 · CC BY 4.0；争议区仅作叠加，不改变现有中国或其他政权边界。";
  } else if (properties.Source === "DataV") {
    sourceText = "来源：阿里云 DataV / 高德行政边界 · 显示副本由 GCJ-02 迭代转换为 WGS 84；原始顶点未抽稀，许可与审定状态待核。DataV 台湾省要素未导入，现有台湾记录仍来自 Natural Earth。";
  } else if (properties.Source === "user-provided") {
    sourceText = "来源：用户提供的十段线 GeoJSON · 几何来源、坐标系与版本待核；1953 年起始显示为当前项目设定，不是该几何自带的史料结论。";
  } else if (year === 2024) {
    sourceText = "2024 底稿：Natural Earth 50m · 公共领域 · 待人工审定；保留来源的主权国与地区分类，不代表本项目立场。";
  } else {
    sourceText = "几何来源：Cliopatria v0.2.1 · CC BY 4.0。";
  }
  let geometryPeriod;
  if (properties.GeometryStatus === "claim") {
    geometryPeriod = `当前显示区间：${formatYear(properties.FromYear)} — ${formatYear(properties.ToYear)}；该区间是项目显示设定，不是已核实的几何版本有效期。`;
  } else if (properties.GeometryStatus === "carry-forward") {
    geometryPeriod = `当前显示区间：${formatYear(properties.FromYear)} — ${formatYear(properties.ToYear)}；源几何版本有效期：${formatYear(properties.SourceFromYear)} — ${formatYear(properties.SourceToYear)}。几何有效期不等于政权存续期。`;
  } else {
    geometryPeriod = `几何版本有效期：${formatYear(properties.FromYear)} — ${formatYear(properties.ToYear)}。几何有效期不等于政权存续期。`;
  }
  const polityDateSource = properties.PolityDateSource
    ? ` 政权日期来源：${properties.PolityDateSource} · 待审校；Wikidata 为 CC0，Wikipedia 为 CC BY-SA 4.0。`
    : "";
  const attributeEntity = polityAttributes.entities[properties.Wikidata];
  const hasWikipediaAttributes = attributeEntity && Object.values(attributeEntity).some((claims) => (
    claims.some((claim) => claim.source === "Wikipedia")
  ));
  const polityAttributeSource = hasAttributes
    ? ` 扩展属性来源：Wikidata（CC0）${hasWikipediaAttributes ? "、Wikipedia（CC BY-SA 4.0）" : ""} · 待审校；按年份筛选或标注记录年份。`
    : "";
  elements.detailSource.textContent = `${sourceText} ${geometryPeriod}${polityDateSource}${polityAttributeSource}`;
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

function labelPointsInView(labelPoint, bounds) {
  const [longitude, latitude] = labelPoint;
  if (latitude < bounds.getSouth() || latitude > bounds.getNorth()) return [];
  const points = [];
  const firstCopy = Math.floor((bounds.getWest() - longitude) / 360);
  const lastCopy = Math.ceil((bounds.getEast() - longitude) / 360);
  for (let copy = firstCopy; copy <= lastCopy; copy += 1) {
    const point = [longitude + copy * 360, latitude];
    if (bounds.contains(point)) points.push(point);
  }
  return points;
}

function updateLabels() {
  if (!ready || !activeCollection) return;
  labelMarkers.forEach((marker) => marker.remove());
  labelMarkers = [];
  const zoom = map.getZoom();
  const bounds = map.getBounds();
  const limit = zoom < 2 ? 45 : zoom < 3.5 ? 60 : 90;
  const sourceFeatures = chgisEnabled && chgisCollection
    ? [...activeCollection.features, ...chgisCollection.features]
    : activeCollection.features;
  const candidates = sourceFeatures
    .filter((feature) => (
      feature.properties.role !== "composite"
      && feature.properties.FromYear <= year
      && feature.properties.ToYear >= year
      && (feature.properties.LabelMinZoom || 0) <= zoom
      && feature.properties.LabelPoint
      && labelPointsInView(feature.properties.LabelPoint, bounds).length > 0
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
    labelPointsInView(properties.LabelPoint, bounds).forEach((point) => {
      const label = document.createElement("div");
      label.className = "polity-label";
      label.textContent = properties.NameZh;
      if (properties.GeometryStatus === "carry-forward") label.classList.add("is-inferred");
      if (properties.role === "composite") label.classList.add("is-composite");
      labelMarkers.push(new maplibregl.Marker({ element: label, anchor: "center" })
        .setLngLat(point)
        .addTo(map));
    });
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

function setYear(nextYear, sliderPosition = null) {
  const index = nearestTimelineIndex(nextYear);
  year = sliderPosition === null
    ? TIMELINE_NODES[index]
    : Math.max(MIN_YEAR, Math.min(MAX_YEAR, Math.round(nextYear)));
  elements.yearLabel.textContent = formatYear(year);
  elements.yearInput.value = year;
  elements.yearSlider.value = sliderPosition ?? index;
  elements.yearHandle.style.left = `${sliderPosition === null ? timelinePercent(year) : sliderPosition / (TIMELINE_NODES.length - 1) * 100}%`;
  document.querySelectorAll("[data-era]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.era === eraForYear(year));
  });
  elements.stepLabel.textContent = "每次前进 1 年";
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
    map.setLayoutProperty("south-china-sea-line", "visibility", year >= 1953 ? "visible" : "none");
    map.setLayoutProperty("south-china-sea-line-hit", "visibility", year >= 1953 ? "visible" : "none");
    map.setLayoutProperty("disputed-fill", "visibility", year === 2024 ? "visible" : "none");
    map.setLayoutProperty("disputed-line", "visibility", year === 2024 ? "visible" : "none");
    if (selectedId !== null) {
      const selected = activeCollection.features[selectedId];
      if (!selected || selected.properties.FromYear > year || selected.properties.ToYear < year) closeDetail();
    }
    if (chgisEnabled) updateChgisFilter();
    updateLabels();
  }
  updateActiveCount();
  if (year === MAX_YEAR && playing) stopPlayback();
}

function timelinePositionForYear(yearValue) {
  if (yearValue <= TIMELINE_NODES[0]) return 0;
  if (yearValue >= MAX_YEAR) return TIMELINE_NODES.length - 1;
  for (let index = 0; index < TIMELINE_NODES.length - 1; index += 1) {
    const left = TIMELINE_NODES[index];
    const right = TIMELINE_NODES[index + 1];
    if (yearValue >= left && yearValue <= right) return index + (yearValue - left) / (right - left);
  }
  return 0;
}

function moveYear(direction) {
  const nextYear = Math.max(MIN_YEAR, Math.min(MAX_YEAR, year + direction));
  setYear(nextYear, timelinePositionForYear(nextYear));
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

function setBaseMode(mode) {
  baseMode = mode === "dlr" ? "dlr" : "natural-earth";
  elements.baseSelect.value = baseMode;
  const url = new URL(window.location.href);
  if (baseMode === "dlr") url.searchParams.set("base", "dlr");
  else url.searchParams.delete("base");
  window.history.replaceState(null, "", url);
  if (!ready) return;
  const useDlr = baseMode === "dlr";
  map.setLayoutProperty("land-fill", "visibility", useDlr ? "none" : "visible");
  map.setLayoutProperty("coastline-line", "visibility", useDlr ? "none" : "visible");
  map.setLayoutProperty("dlr-land-fill", "visibility", useDlr ? "visible" : "none");
  map.setLayoutProperty("dlr-coastline-line", "visibility", useDlr ? "visible" : "none");
}

function updateChgisFilter() {
  if (!chgisCollection) return;
  const activeFeatures = chgisCollection.features.filter((feature) => (
    feature.properties.FromYear <= year && feature.properties.ToYear >= year
  ));
  map.getSource("chgis-prefectures").setData({ type: "FeatureCollection", features: activeFeatures });
  map.setFilter("chgis-fill", activeFilter(year));
  map.setFilter("chgis-line", activeFilter(year));
}

async function setChgisEnabled(enabled) {
  chgisEnabled = enabled;
  elements.chgisToggle.checked = enabled;
  if (enabled && !chgisCollection) {
    try {
      chgisCollection = await fetchGeoJson("./local/chgis-prefectures.geojson");
      map.addSource("chgis-prefectures", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: chgisCollection.features.filter((feature) => (
            feature.properties.FromYear <= year && feature.properties.ToYear >= year
          ))
        },
        attribution: "CHGIS Version 6 · Fairbank Center / Fudan University · local research only"
      });
      map.addLayer({
        id: "chgis-fill",
        type: "fill",
        source: "chgis-prefectures",
        filter: activeFilter(year),
        paint: { "fill-color": "#dca95f", "fill-opacity": 0.2 }
      });
      map.addLayer({
        id: "chgis-line",
        type: "line",
        source: "chgis-prefectures",
        filter: activeFilter(year),
        paint: { "line-color": "#efc27f", "line-width": 0.8 }
      });
    } catch (error) {
      chgisCollection = null;
      chgisEnabled = false;
      elements.chgisToggle.checked = false;
      console.warn("CHGIS local research data unavailable", error);
      return;
    }
  }
  if (chgisCollection) {
    const visibility = chgisEnabled ? "visible" : "none";
    map.setLayoutProperty("chgis-fill", "visibility", visibility);
    map.setLayoutProperty("chgis-line", "visibility", visibility);
    updateChgisFilter();
  }
  updateLabels();
}

function bindControls() {
  elements.chgisControl.hidden = !["localhost", "127.0.0.1"].includes(window.location.hostname);
  elements.chgisToggle.addEventListener("change", (event) => setChgisEnabled(event.target.checked));
  elements.baseSelect.addEventListener("change", (event) => setBaseMode(event.target.value));
  elements.yearSlider.addEventListener("input", (event) => {
    const position = Number(event.target.value);
    const lower = Math.floor(position);
    const upper = Math.min(TIMELINE_NODES.length - 1, Math.ceil(position));
    const fraction = position - lower;
    const interpolatedYear = TIMELINE_NODES[lower] + (TIMELINE_NODES[upper] - TIMELINE_NODES[lower]) * fraction;
    setYear(interpolatedYear, position);
  });
  elements.yearSlider.addEventListener("change", (event) => {
    const position = Number(event.target.value);
    const nearest = Math.round(position);
    if (Math.abs(position - nearest) <= 0.15) setYear(TIMELINE_NODES[nearest]);
  });
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
    const buttonYear = Number(button.dataset.year);
    button.style.left = `${timelinePercent(buttonYear)}%`;
    button.style.transform = "translateX(-50%)";
    button.addEventListener("click", () => setYear(buttonYear));
  });
  document.querySelectorAll("[data-era-year]").forEach((button) => {
    button.addEventListener("click", () => setYear(Number(button.dataset.eraYear)));
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

function addDataLayers(base, claimLine, disputedAreas) {
  const useDlr = baseMode === "dlr";
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
  map.addSource("dlr-coastline", {
    type: "vector",
    tiles: [`${new URL(".", window.location.href).href}tiles/coastline/{z}/{x}/{y}.pbf`],
    minzoom: 0,
    maxzoom: 6,
    attribution: "© DLR 2019-2025. TanDEM-X High-Resolution Coastline - Global, 10m, CC BY 4.0"
  });
  map.addLayer({
    id: "land-fill",
    type: "fill",
    source: "natural-earth-land",
    layout: { visibility: useDlr ? "none" : "visible" },
    paint: { "fill-color": "#293d34" }
  });
  map.addLayer({
    id: "dlr-land-fill",
    type: "fill",
    source: "dlr-coastline",
    "source-layer": "land",
    layout: { visibility: useDlr ? "visible" : "none" },
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
    layout: { visibility: useDlr ? "none" : "visible" },
    paint: { "line-color": "#799486", "line-width": 0.65, "line-opacity": 0.35 }
  });
  map.addLayer({
    id: "dlr-coastline-line",
    type: "line",
    source: "dlr-coastline",
    "source-layer": "land",
    layout: { visibility: useDlr ? "visible" : "none" },
    paint: { "line-color": "#799486", "line-width": 0.65, "line-opacity": 0 }
  });
  map.addLayer({
    id: "polity-line",
    type: "line",
    source: "cliopatria",
    filter: activeFilter(year),
    paint: { "line-color": "rgba(235, 241, 220, 0.62)", "line-width": 0.55 }
  });
  map.addSource("south-china-sea-claim", {
    type: "geojson",
    data: claimLine,
    attribution: "User-provided South China Sea line · review pending"
  });
  map.addLayer({
    id: "south-china-sea-line-hit",
    type: "line",
    source: "south-china-sea-claim",
    layout: { visibility: year >= 1953 ? "visible" : "none" },
    paint: { "line-color": "#f3ca70", "line-width": 16, "line-opacity": 0 }
  });
  map.addLayer({
    id: "south-china-sea-line",
    type: "line",
    source: "south-china-sea-claim",
    layout: { visibility: year >= 1953 ? "visible" : "none" },
    paint: {
      "line-color": "#f3ca70",
      "line-width": 2.2,
      "line-opacity": 0.9,
      "line-dasharray": [2, 1.5]
    }
  });
  map.addSource("world-bank-disputes", {
    type: "geojson",
    data: disputedAreas,
    attribution: "World Bank Official Boundaries · CC BY 4.0"
  });
  map.addLayer({
    id: "disputed-fill",
    type: "fill",
    source: "world-bank-disputes",
    layout: { visibility: year === 2024 ? "visible" : "none" },
    paint: { "fill-color": "#c28bb8", "fill-opacity": 0.3 }
  });
  map.addLayer({
    id: "disputed-line",
    type: "line",
    source: "world-bank-disputes",
    layout: { visibility: year === 2024 ? "visible" : "none" },
    paint: { "line-color": "#efb6dd", "line-width": 1.6, "line-dasharray": [2, 1] }
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

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function fetchGeoJson(path) {
  const data = await fetchJson(path);
  if (data.type === "Feature") return { type: "FeatureCollection", features: [data] };
  if (data.type !== "FeatureCollection" || !Array.isArray(data.features)) {
    throw new Error(`${path} 不是有效的 GeoJSON Feature 或 FeatureCollection`);
  }
  return data;
}

async function loadData() {
  try {
    elements.loadingDetail.textContent = "正在加载陆地、海洋、水系、中文名称、政权资料与历史边界…";
    const [historical, modern, attributes, land, lakes, rivers, coastline, claimLine, disputedAreas] = await Promise.all([
      fetchGeoJson("./data/cliopatria.geojson"),
      fetchGeoJson("./data/modern-2024.geojson?v=20261105-polity-audit"),
      fetchJson("./data/polity-attributes.json"),
      fetchGeoJson("./data/natural-earth/land.geojson"),
      fetchGeoJson("./data/natural-earth/lakes.geojson"),
      fetchGeoJson("./data/natural-earth/rivers_lake_centerlines.geojson"),
      fetchGeoJson("./data/natural-earth/coastline.geojson"),
      fetchGeoJson("./data/south-china-sea-line.geojson"),
      fetchGeoJson("./data/world-bank-disputed.geojson")
    ]);
    collection = historical;
    modernCollection = modern;
    polityAttributes = attributes;
    activeCollection = collection;
    addDataLayers({ land, lakes, rivers, coastline }, claimLine, disputedAreas);
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
    renderWorldCopies: true
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.on("load", loadData);
  map.on("zoomend", updateLabels);
  map.on("moveend", updateLabels);
  map.on("click", "polity-fill", (event) => {
    const feature = event.features?.find((item) => item.properties.role !== "composite")
      || event.features?.[0];
    if (feature) showDetail(feature.properties);
  });
  map.on("click", "south-china-sea-line-hit", (event) => {
    if (event.features?.length) showDetail(event.features[0].properties);
  });
  map.on("click", "disputed-fill", (event) => {
    if (event.features?.length) showDetail(event.features[0].properties);
  });
  map.on("click", "chgis-fill", (event) => {
    if (event.features?.length) showDetail(event.features[0].properties);
  });
  map.on("mouseenter", "polity-fill", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "polity-fill", () => { map.getCanvas().style.cursor = ""; });
  map.on("mouseenter", "south-china-sea-line-hit", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "south-china-sea-line-hit", () => { map.getCanvas().style.cursor = ""; });
  map.on("mouseenter", "disputed-fill", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "disputed-fill", () => { map.getCanvas().style.cursor = ""; });
  map.on("mouseenter", "chgis-fill", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "chgis-fill", () => { map.getCanvas().style.cursor = ""; });
}

setBaseMode(baseMode);
bindControls();
setYear(year);
initializeMap();
