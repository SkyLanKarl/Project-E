# Project E · 全球动态历史边界研究

[![GitHub Pages 部署状态](https://github.com/SkyLanKarl/Project-E/actions/workflows/pages.yml/badge.svg)](https://github.com/SkyLanKarl/Project-E/actions/workflows/pages.yml)

**在线访问：[https://skylankarl.github.io/Project-E/](https://skylankarl.github.io/Project-E/)**

这是一个用于历史研究的静态网站雏形。当前版本以 Cliopatria 的历史政权几何为核心，结合 Natural Earth 的陆地、海洋、水系和 2024 年现代参考层，探索时间轴、地图缩放、双语名称及来源追溯等交互。

> 当前展示的是按年份过滤的政治实体快照，不是连续军事战线，也不代表对历史主权、现实主权或争议地区归属的立场。

## 当前功能

- 展示公元前 3400 年至公元 2024 年的政治实体几何记录；
- 年份滑块、精确跳转、常用年份及播放速度控制；
- 世界地图支持左右无限循环平移，几何和中文标签随世界副本显示；
- 本地世界陆地、海洋、海岸线、河流和湖泊，无在线底图依赖；
- 按缩放级别显示中文名称，详情保留英文原名及 Wikidata 链接；
- 区分来源原始几何、复合政治实体、关系成员和推断延续几何；
- 墨西哥 1913—1919 年采用单独确认的 1912 年几何延续规则；
- 2024 年以 Natural Earth 为现代参考层；中国大陆及港澳改用 DataV 省级几何，台湾继续保留 Natural Earth 原记录；
- 1953 年起显示用户提供的南海断续线，作为来源及版本待核的主张边界，不作为法定国界；
- 静态部署到 GitHub Pages，推送 `main` 后自动更新。

## 研究口径与限制

- **几何版本有效期不等于政权存续期。**详情以来源区记录几何年份；政权存续时间取自 Wikidata 的建立时间（P571）和解散/废止时间（P576），与几何字段分开保存，仍需人工审校。缺失时标为待核实，只有建立日期时不推断为“至今”；存在多个候选日期时明确提示。
- **不强行统一岸线。**Cliopatria 与 Natural Earth 的岸线可能不一致；历史层保留原始几何，不为了视觉效果按现代岸线裁切。
- **不把政治实体记录数当作独立国家数。**复合政体、成员政体、殖民地和其他政治实体需要分别解释。
- **不自动填补历史缺口。**当前仅墨西哥 1913—1919 年应用了明确的延续案例，并在地图和详情中标注为推断。
- **2024 年参考层尚未完成人工审定。**Natural Earth 与 DataV 仅作为底稿；DataV 显示副本由 GCJ-02 转换为 WGS 84，未抽稀顶点，其许可、主权国及地区分类仍需继续审核。
- **非政治实体不参与领土归属。**锡亚琴冰川与南极洲已移出政治实体层，不并入任何国家；争议地区的实际控制与主权主张应在未来分层记录。
- 中文名称来自 Wikidata 或本地待审校译名表，不应视为已经完成的历史名词审定。
- 当前尚无连续战线插值、边界段稳定对应关系、事件—边界关联和完整修订审核机制。

## 本地运行

网站不需要 Node.js 或前端构建。安装 Python 3 后，在仓库根目录运行：

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory prototype
```

然后访问：

```text
http://127.0.0.1:8000/
```

请通过本地 HTTP 服务打开，不要直接双击 `index.html`，否则浏览器可能阻止 GeoJSON 加载。

## 数据来源与许可

| 内容 | 来源 | 许可 | 使用说明 |
|---|---|---|---|
| 历史政权几何、年份区间 | [Cliopatria v0.2.1](https://github.com/Seshat-Global-History-Databank/cliopatria/tree/v0.2.1) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 保留署名、许可链接和修改说明 |
| 陆地、水系、海岸线及 2024 年参考底稿 | [Natural Earth](https://www.naturalearthdata.com/) | 公共领域 | 保留来源说明，继续审核历史适用性 |
| DLR 海岸实验数据（可选对照模式） | [DLR TanDEM-X High-Resolution Coastline 2010–2015](https://doi.org/10.15489/entfdgi5es81) | CC BY 4.0 | © DLR 2019-2025；默认底版不变，使用 `?base=dlr` 启用实验对照 |
| 2024 年现代国家／地区及争议叠加层 | [World Bank Official Boundaries](https://datacatalog.worldbank.org/search/dataset/0038272/world-bank-official-boundaries) | CC BY 4.0 | 保留 World Bank 署名；争议区只叠加，不替换现有边界 |
| CHGIS 府级本地研究层 | [CHGIS Version 6](https://dataverse.harvard.edu/dataverse/chgis_v6) | 非商业学术／教育使用，禁止未经许可公开再分发 | 仅在本地 `prototype/local/` 使用，不上传或部署完整图层 |
| 2024 年中国省级边界 | [阿里云 DataV](https://geo.datav.aliyun.com/) | 待核实 | 原始坐标为 GCJ-02；显示副本转换为 WGS 84，未抽稀 |
| 中文名称、政权日期及结构化属性 | [Wikidata](https://www.wikidata.org/) | [CC0 1.0](https://www.wikidata.org/wiki/Wikidata:Copyright) | 英文原名与实体 ID 同时保留，历史属性仍需审校 |
| 缺失政权字段的备选补充 | [English Wikipedia](https://en.wikipedia.org/) | [CC BY-SA 4.0](https://en.wikipedia.org/wiki/Wikipedia:Text_of_the_Creative_Commons_Attribution-ShareAlike_4.0_International_License) | 仅补 Wikidata 空字段；保存条目链接、修订号和修改来源，不覆盖已有值 |
| 地图渲染 | [MapLibre GL JS 5.6.0](https://github.com/maplibre/maplibre-gl-js) | BSD-3-Clause | 许可文本位于 `prototype/vendor/maplibre-LICENSE.txt` |

不同来源的代码、几何、文本和图片应分别记录许可。本项目没有将上游整个数据包视为可无条件复用。

## 目录结构

```text
.
├── .github/workflows/pages.yml       # GitHub Pages 自动部署
├── prototype/
│   ├── index.html                   # 页面结构
│   ├── styles.css                   # 地图与时间轴样式
│   ├── app.js                       # 地图、年份、标签和详情交互
│   ├── config/name-overrides.json   # 本地中文译名覆盖表
│   ├── config/entity-qid-overrides.json # 经审查的实体 QID 纠错规则
│   ├── scripts/
│   │   ├── fetch_labels.py          # 分批获取 Wikidata 中文标签
│   │   ├── fetch_polity_dates.py    # 分批获取 Wikidata 政权起止日期
│   │   ├── fetch_polity_attributes.py # 下载首都、人口及其他政权属性
│   │   ├── audit_wikipedia_qids.py  # 审查 Wikipedia 条目与 QID 对应关系
│   │   └── prepare_data.py          # 生成网站使用的精简数据
│   ├── data/                        # 可直接部署的处理后数据与许可
│   └── vendor/                      # 本地 MapLibre 及许可
├── 全球动态历史边界项目_开源项目与数据调研.md
└── README.md
```

`data/raw/` 和 `upstream/` 仅用于本地原始数据与上游代码研究，已由 `.gitignore` 排除。网站所需的处理后数据已经包含在仓库中，因此克隆后可直接运行。

## 重新生成数据

仅在需要更新原始数据或译名时执行。准备脚本会读取本地的 Cliopatria、Natural Earth 和 Wikidata 缓存，并重新生成 `prototype/data/`：

```bash
python prototype/scripts/prepare_data.py
```

如需重新获取 Wikidata 中文标签和政权起止日期，先安装 `requests`，再运行：

```bash
python -m pip install requests
python prototype/scripts/fetch_labels.py
python prototype/scripts/fetch_polity_dates.py
python prototype/scripts/prepare_data.py
```

首都及坐标、人口、面积、官方语言、宗教、货币、政治体制、国家元首、政府首脑、人物任职、前身、继承者、实体类型、组成、行政区划、外交关系和成员身份可获取并接入网站详情的“政权资料”区域。详情按当前年份筛选带时间限定的记录，无时间限定的记录会明确标注；人口和面积显示距当前年份最近的记录及其年份：

```bash
python prototype/scripts/fetch_polity_attributes.py
python prototype/scripts/fetch_wikipedia_infoboxes.py
python prototype/scripts/prepare_data.py
```

原始数据需要分别放置在 `data/raw/cliopatria/`、`data/raw/natural-earth/` 和 `data/raw/wikidata/`；这些原始文件不随仓库分发。

## CHGIS 本地研究层

CHGIS 时间序列府级数据仅用于本地非商业研究。生成文件写入被 Git 忽略的 `prototype/local/`，不会上传或部署：

```bash
.venv/Scripts/python prototype/scripts/prepare_chgis_local.py
```

本地页面顶部会出现“CHGIS 府级（本地）”开关。公开 GitHub Pages 不显示该入口。当前接入的是 WGS 84 时间序列府级多边形；1820/1911 的西安 1980 图层尚未接入。

## 自动部署

GitHub Actions 工作流位于 `.github/workflows/pages.yml`。每次推送到 `main` 时，会直接把 `prototype/` 发布到 GitHub Pages，无构建步骤。

也可以在 [Actions 页面](https://github.com/SkyLanKarl/Project-E/actions/workflows/pages.yml) 手动触发部署。

## 后续研究路线

1. 选择一个资料充分的短期战争或战区，而非立即拼接全球全部历史；
2. 制作 15—30 个有明确来源的战线关键帧；
3. 建立政治实体、边界段、几何版本、历史事件、来源与修订记录；
4. 明确区分法定国界、实际控制线、军事战线和主张边界；
5. 对任何推断延续或视觉插值保留证据、方法和审核状态；
6. 完成“播放时间轴 → 查看战线变化 → 点击边界段 → 查看事件解释与资料来源”的闭环。
