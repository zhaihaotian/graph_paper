# Argument Graph Fingerprinting — AI vs Human-Written Papers

## 1. 数据与目的

**目标**：把每篇论文 Introduction 解析成**论证结构图**（argument graph），在图上算指标，比较 AI 生成论文与人写论文的结构差异。

**数据集**：80 篇论文（2026-05-01 corpus 翻倍）
- **AI** (n=40)：FARS corpus AI-generated papers（FA 系列）
  - 原 20 篇：FA0001–FA0047
  - 新增 20 篇：FA0058–FA0235（来自 fars_30_sample 未用部分）
- **Human** (n=40)：
  - 11 篇 anchor papers（真实被 AI 引用的 2024–2026 论文）
  - 9 篇 ICLR 2025 Oral
  - 新增 20 篇 ICLR 2025 Poster（iclr25_30_sample 中选 20）

---

## 2. 图的定义

有向图。节点 = 一个 claim，边 = claim 之间的论证关系。

### 2.1 节点类型（7 类）

| Type | 定义 | 举例 |
|---|---|---|
| **Context** | 领域/问题设定，field-level 框架（含 "However …"型领域问题） | "LLMs undergo extensive alignment training" |
| **Prior_Work** | 中性描述某个前人方法做了什么 | "SafeLoRA projects LoRA weight updates to preserve safety directions (Hsu 2024)" |
| **Limitation** | 评价性批评某个**具体 Prior_Work** 在 Y 上不足 | "However, SafeLoRA uses fixed parameters, suboptimal when EM risk varies" |
| **Method** | 本文提出的方法/组件 | "We propose canary-controlled adaptive interleaving" |
| **Result** | 本文实证结果/数字/ablation | "5.39% misalignment vs 7.15% baseline (25% reduction)" |
| **Proof** | 指向 Figure/Table/Appendix 的支撑材料 | "as shown in Fig. 1 (bottom)" |
| **Contribution** | 末尾贡献列表条目 | "We introduce Abstain-Test benchmark" |

**关键区分**：
- Context vs Limitation：问题是不是针对具体 Prior_Work 的批评？领域级的 "However" 仍是 Context。
- Prior_Work vs Limitation：中性描述 vs 评价性不足。

### 2.2 边类型（5 类）

| Kind | 含义 | 硬性判定规则 |
|---|---|---|
| **elaboration** | 具体化/展开；兜底 | 无 marker 命中时的默认 |
| **contrast** | A 正面/基线 → B 反转 | 必须有 marker：However / Yet / But / 然而 / 但是 |
| **consequence** | A 的因果/逻辑后果 | 必须有 marker：Therefore / Hence / 因此 / 所以 |
| **evidence** | B 是支撑 A 的 Result 或 Proof | B 类型 ∈ {Result, Proof} |
| **addresses** | Method/Contribution 显式解决某个 Limitation | 跨段 + 两端共享**独特**技术词（如 "diversity collapse"） |

### 2.3 拓扑属性（自动算）

- `fork node`：out_degree ≥ 2
- `join node`：in_degree ≥ 2

---

## 3. Claim 抽取流程（5 阶段）

**Stage 1 — 句子切分**
按 `.` `?` `!` `。` `？` `！` 切句。一句通常 = 一个节点。并列枚举（"harms include A, B, C"）→ 父 + 子节点。

**Stage 2 — 节点分类**
每句归入 7 类之一。Tie-breaker：`Contribution > Method > Result > Limitation > Prior_Work > Context`。记录 `id`、`type`、`text`（verbatim）、`display_label`（短）、`citations`（数 `[n]` 或 `(Author, Year)`）。

**Stage 3 — 边抽取（两阶段）**
- **Pass 1 相邻句**：marker 命中 → typed kind；否则 elaboration 兜底
- **Pass 2 cross-pair scan**：扫所有 Method↔Limitation、Contribution↔Limitation 对，找 `addresses`（要求两端共享独特术语）

**Stage 4 — 渲染**
`render_graph.py` 确定性布局 SVG：7 个 y-zone + zone 内按拓扑深度分 sub-row + fork/join 虚线框 + citation 右侧圆点。

**Stage 5 — 硬校验**
- `validate_graph.py`：schema 合规（type/kind 白名单、Contribution 出边规则）
- `coverage_check.py`：源 PDF 每句都有对应节点，**要求 ≥85% 覆盖**
- 12 项 manual audit checklist

---

## 4. 指标（9 个，分 4 组）

所有指标基于 JSON 计算，不依赖渲染。

### A. 全图结构（3）

---

**A1. `sum_node_degree`** — 图的连通总量

- **定义**：全图所有节点的 `(in_degree + out_degree)` **之和**（不平均）
- **算法**：`Σ (in_degree[v] + out_degree[v])` over all nodes
- **等价形式**：= 2 × |edges|（每条边对两端各贡献 1 个 in 和 1 个 out）
- **含义**：整张图里 claim-to-claim 关系的总条数（双向计）。越大 = 论证链越密集。
- **结果**：AI **34.2** / Human **60.8** → **1.78×**

---

**A2. `graph_longest_path`** — 图的深度

- **定义**：图中最长 DAG 路径的节点数
- **算法**：DFS + memoization，从每个节点向下延伸找最长链，带 cycle 保护（addresses 反向边可能构成环）
- **含义**：最长的"论证接力链"有几跳。AI 论文扁平，人写深。
- **结果**：AI **12.55** / Human **23.95** → **1.91×**

---

**A3. `max_width`** — 图的宽度

- **定义**：各 zone 里 "top-level 节点"数的最大值
- **top-level 的定义**：该节点没有来自同 zone 的入边（即它是该 zone 的"主线"节点，不是 sub-claim）
  - 举例：Contribution 有 4 个 main + 10 个 sub-claim（通过 elaboration 从 main 连出），则 top-level=4
- **算法**：`max(count(n in zone Z where no in-edge from zone Z) for Z in all zones)`
- **含义**：任何论证类型在"主干道"最多塞了多少并列节点。
- **结果**：AI **3.15** / Human **3.80** → 1.21×（差异小；这个指标 AI 的 3-bullet contribution 和人写的 3-4 个 main contribution 差不多）

### B. Prior_Work 引用分析（3）

---

**B1. `pw_node_count`** — Prior_Work 节点总数

- **定义**：图中 `type=Prior_Work` 的节点数
- **算法**：`count(n for n in nodes if main_type(n.type) == "Prior_Work")`
- **含义**：intro 里提到了多少个独立 prior work（含 sub-claim）
- **结果**：AI **2.15** / Human **4.35** → 2.02×

---

**B2. `pw_top_level_count`** — Prior_Work 多样性

- **定义**：Prior_Work zone 里 top-level 节点数（**不数 sub-claim**）
- **算法**：`count(n for n in PW_nodes if no same-zone in-edge)`
  - 举例：如果有 N4 "两类 prior work" + N4a "category 1" + N4b "category 2"，top-level 只算 N4（或者算 N4a/N4b 如果 N4 不存在）
- **含义**：独立的 prior work **线索数**——多样性。AI 论文往往只有 1-2 条 prior work 线索，人写多源。
- **结果**：AI **1.20** / Human **1.65** → 1.38×

---

**B3. `pw_avg_cites`** — Prior_Work 人均 citation

- **定义**：Prior_Work 节点 citation 的平均值
- **算法**：`sum(n.citations for n in PW_nodes) / pw_node_count`
- **含义**：每个 Prior_Work claim 有几篇参考文献支撑。低 = 每个 PW 是"1 篇 named anchor"，高 = 每个 PW 聚合多源。
- **结果**：AI **0.89** / Human **1.73** → 1.94×

---

**B4. `pw_total_cites`** — Prior_Work 总引用量

- **定义**：所有 Prior_Work 节点 citation 之和
- **算法**：`Σ n.citations for n in PW_nodes`
- **含义**：intro 的 prior-work 章节总共引了多少篇文献。**最直接**反映"过往文献的回顾广度"。
- **结果**：AI **2.05** / Human **7.25** → **3.54×**（最大差距之一）

### C. Limitation scope（1）

---

**C1. `lim_scope_avg_cites`** — Limitation 批评的 critique surface（v3: per-paper PW union）

- **直觉**：整篇 paper 的 Limitation 总共批评了多少篇 prior work？
- **算法**（v3，2026-05-01 更新）：
  1. 对每个 Limitation L 做**反向 BFS**（excluding `addresses` 反向边）
  2. 在第一个有 PW 祖先的 BFS 层，构造 **L 的 coverage 集合** =（PW 祖先）∪（它们的 PW elaboration children）
  3. 如果 coverage 里至少有一个 cited PW（cites>0），记录这个 coverage；否则继续往上一层
  4. 全文聚合：所有 L 的 coverage **取并集**（无重复）
  5. paper 的 `lim_scope_avg_cites` = sum(p.cites for p in 并集)
- **为什么改 v2 → v3**：
  - v2 是 per-Lim avg → per-paper mean，平均掉了 "Human paper 不仅每个 Lim 范围广，还有更多 Lim" 的双重效应
  - v3 直接看整篇 paper 的 critique surface 总和，捕获了 breadth × count 的乘积
- **含义**：
  - 低值（1-2）→ paper 整体只批评 1-2 篇 prior work（典型 AI：single anchor 论文）
  - 高值（5+）→ paper 整体批评一大片 prior work（典型 Human：multi-thread Limitation cluster）
- **结果（v3 算法 + n=80）**：
  - AI **1.73** / Human **4.65** → **2.70×**
  - 比 v2 (2.05×) 信号更强，因为捕获了 paper-level 的 Lim 数量效应

**辅助样本数**：`lim_scope_sample_count` — 这篇 paper 里有多少 Lim 贡献到了 union
- AI 2.12 / Human 3.98 → 1.87×

### D. Method 分析（2）

---

**D1. `method_node_count`** — 方法复杂度

- **定义**：图中 `type=Method`（含 `Method: component` 等 subtype）的节点数
- **算法**：`count(n for n in nodes if main_type(n.type) == "Method")`
- **含义**：方法描述被拆成几个 claim。AI 通常是 "we propose X with A/B/C 3 components"；人写常有分阶段、多组件、设计动机、数学推导等多个 claim。
- **结果**：AI **3.15** / Human **8.35** → **2.65×**

---

**D2. `method_pw_reach_avg`** — Method 的 idea 来源深度

**详细讲解（你问的）**：

- **定义**：每个 Method 节点**反向 BFS** 能触达的**不同 Prior_Work 节点数**的平均
- **算法**：
  ```
  for each Method node M:
      visited = {M}
      frontier = [M]
      while frontier not empty (max 15 steps):
          next_frontier = []
          for node in frontier:
              for predecessor in in_edges[node]:  # follow edges BACKWARD
                  if predecessor not in visited:
                      visited.add(predecessor)
                      next_frontier.append(predecessor)
          frontier = next_frontier
      pw_reached = visited ∩ Prior_Work_node_ids
      record |pw_reached|
  avg = mean of all records
  ```

- **举例**：假设图结构是
  ```
  N1 [Context] → N2 [Prior_Work] → N4 [Limitation] → N6 [Method_main] → N7 [Method_component]
                 N3 [Prior_Work] → N4
  ```
  - 从 N6（Method_main）反向 BFS：visits N4, N2, N3, N1 → PW 集合 = {N2, N3} → count = **2**
  - 从 N7（Method_component）反向 BFS：visits N6, N4, N2, N3, N1 → PW 集合 = {N2, N3} → count = **2**
  - avg = **2.0**

- **含义**：
  - **低（~2）** → Method 仅"站在 1-2 个 Prior_Work 的肩膀上"。典型 AI 模式："我们在 anchor paper X 的基础上改了 Y"。
  - **高（3+）** → Method 综合了多个 Prior_Work 的思想。典型人写模式。

- **结果**：AI **1.95** / Human **3.17** → 1.62×

---

## 5. 均值对比总表

> **2026-05-01 更新（v2）**：corpus 从 40 → 80 翻倍。新增 20 AI（FA0058–FA0235）+ 20 ICLR 2025 Poster。所有 80 graphs 经过 Pass 3 校验 + 4 agent QA review（共 12 处自动修复）。Fingerprint 在更大样本上保持。

### v2 (n=80, AI 40 / Human 40)

| 组 | 指标 | AI | Human | Human/AI |
|---|---|---|---|---|
| A. 结构 | sum_node_degree (Σ in+out = 2\|E\|) | 36.05 | 59.95 | **1.66×** |
| A. 结构 | graph_longest_path (深度) | 13.68 | 23.95 | **1.75×** |
| A. 结构 | max_width (宽度) | 3.25 | 3.23 | 0.99× |
| B. PW | pw_node_count | 2.30 | 4.38 | **1.90×** |
| B. PW | pw_top_level_count (多样性) | 1.43 | 1.93 | 1.35× |
| B. PW | pw_avg_cites (人均引用) | 0.98 | 1.85 | **1.89×** |
| B. PW | **pw_total_cites (总引用, strongest)** | **2.15** | **7.42** | **3.45×** |
| C. Lim | lim_scope_avg_cites (paper critique surface, v3 union, strongest) | 1.73 | 4.65 | **2.70×** |
| D. Method | method_node_count (复杂度) | 3.42 | 7.33 | **2.14×** |
| D. Method | method_pw_reach_avg | 2.20 | 3.37 | **1.53×** |
| 引用 | total_cites | 5.12 | 17.95 | **3.50×** |
| 引用 | cite_density (cites/node) | 0.32 | 0.67 | **2.12×** |

### v1 (n=40) 对比 — 看趋势是否稳定

| 指标 | v1 AI | v1 Human | v2 AI | v2 Human | v2 ratio change |
|---|---|---|---|---|---|
| pw_total_cites | 2.15 | 7.65 | 2.15 | 7.42 | 3.56× → 3.45× |
| method_node_count | 3.15 | 8.35 | 3.42 | 7.33 | 2.65× → 2.14× |
| graph_longest_path | 12.75 | 24.15 | 13.68 | 23.95 | 1.89× → 1.75× |
| pw_node_count | 2.40 | 4.60 | 2.30 | 4.38 | 1.92× → 1.90× |
| lim_scope_avg_cites | 1.18 | 2.36 | 1.18 | 2.67 | 2.01× → 2.26× |

**观察**：
- **`pw_total_cites` 3.45×**（vs v1 3.56×）：最强信号在 80 篇上**保持**
- **`method_node_count` 从 2.65× → 2.14×**：人写均值从 8.35 降到 7.33（ICLR Poster 比 Oral 短一点），AI 从 3.15 升到 3.42（新 FA papers 略复杂）
- **`graph_longest_path` 从 1.89× → 1.75×**：略微收窄，但仍接近 2×
- **`lim_scope_avg_cites` 从 2.01× → 2.26×**：反而**变强**，说明人写 Limitation 反向 BFS 找到的 PW 比之前更聚合
- **`max_width` 从 1.21× → 0.99×**：完全消失。说明这个指标本来就弱，n 大了之后无差距
- 整体：**主要 fingerprint（PW citation 体量、Method 复杂度、Limitation 批评范围）保持**

---

## 6. 结论（报告用 narrative）

**AI 论文的结构指纹**：
1. **扁平**：论证链平均 12.75 跳，人写 24.15 跳
2. **单线 Prior_Work**：只有 1-2 条独立前人工作线索
3. **PW 人均引用低**：每个 PW 节点只挂 ~0.9 篇引用（**"每个 PW = 1 篇 named anchor"**）
4. **Limitation 批评单点**：反向找到的最近被引 PW 只有 1.18 cite（批评的是具体单篇）
5. **Method 简单**：只有 ~3 个 claim（主方法 + 1-2 组件）
6. **Method 扎根浅**：Method 反向只能触达 ~2.2 个 Prior_Work

**人写论文**：
1. **深**：论证链深度接近 AI 两倍（24 跳）
2. **多线**：Prior_Work 有 2+ 条独立线索
3. **多源引用**：每个 PW 节点平均挂近 1.8 篇引用
4. **Limitation 批评广**：反向找到的 PW 祖先 citations 均值 2.36（批评一整类方法）
5. **Method 复杂**：~8 个 claim（主方法 + 多组件 + 理论/动机）
6. **Method 扎根深**：反向触达 3+ 独立 Prior_Work

---

## 7. 文件清单

- `ai/`、`human/` — 80 张图的 JSON + SVG（40 AI + 40 Human）
- `pdfs/{ai,human}/` — 80 篇原始 PDF
- `intros/{ai,human}/` — 80 篇 introduction 纯文本
- `metrics.csv` — 6 个核心指标 × 80 行
- `metrics_plots.png` — 6 指标 boxplot + p-value
- `blind_reviews_input/` + `blind_reviews_output/` — LLM 盲评实验
- `index.html` — 静态查看站
- `REPORT.md` — 本文件
- **`skill/` — Skill 工具链（repo 内自包含副本）**
  - `SKILL.md` — 抽取流程规范（5 stages + Pass 3）
  - `render_graph.py` — SVG 渲染（fork/join 自动检测）
  - `validate_graph.py` — schema 校验 + Pass 3 Limitation source check
  - `coverage_check.py` — 覆盖率硬校验（与源 PDF 比对）
  - `compute_metrics.py` — 6 个核心指标计算
  - `plot_metrics.py` — boxplot + Mann-Whitney U
  - `classify_papers.py` — Logistic Regression + Random Forest，5-fold CV
  - `EXAMPLE.json` / `EXAMPLE.svg` — schema 参考样例
- 系统级 skill 安装位置：`~/.claude/skills/argument-graph-extractor/`（与 `skill/` 内容一致，由 Claude Code 自动加载）

---

## 8. Pass 3 修复（2026-05-01）

**动机**：原 Pass 1 抽边规则只看相邻句、按 marker 触发 kind，没有强制"Limitation 必须由 Prior_Work 引出"的语义约束。结果是只要源文本是 `[PW] [Result] However [Limitation]` 这种结构（人写常见），抽出来的图就成了 `Result → Limitation`，PW 那一步被中间的 Result 挡住——给出"Limitation 凭空冒出"的假象。

**新规则**（SKILL.md Stage 3 Pass 3，validate_graph.py 强制 warning）：

> 每个 Limitation 节点的入边来源 type ∈ {Prior_Work, Limitation}，excluding `addresses` back-references（这些是 Method/Contribution 反向回指，代表 resolve 不代表 source）。

三种修复方式：

| Case | 适用 | 操作 |
|---|---|---|
| **(a) Re-type → Context** | L 是 paper-theme-aligned 的领域级 framing，没有具体被 critique 的 PW | 改 type，不动边 |
| **(b) 加 PW → L 边** | 上游已有相关 PW 节点，L 实际批评的是它（"However its …" 模式） | 加显式 contrast/elaboration 边，原相邻边降级为 elaboration |
| **(c) 拆 buried PW** | L 的文本里嵌入了某 PW 的描述+citation（一句话兼描述 + 批评） | 把描述部分切出新的 PW 节点，L 文本缩到只剩批评 |

**修复结果**（16 violations / 14 papers）：

| Case | 数量 | 代表性例子 |
|---|---|---|
| A | 3 | FA0013 N3, ICLR_KAN N3+N4 — 论文主题就是论 X 的局限 |
| B | 5 | FA0007 N6, FA0027 N6, FA0012_anchor N10, ICLR_InferenceScaling N11, ICLR_KAN N20b |
| C | 8 | FA0005 N7, FA0027 N4, FA0034 N6, FA0035 N8, FA0001_anchor N11, FA0008_anchor N3, FA0013_anchor N5, ICLR_WizardMath N22 |

**对指标的影响**（cite 总量守恒）：
- `pw_node_count` AI +0.25 / Human +0.25 — Case C 新增的 buried-PW 节点
- `pw_total_cites` AI +0.10 / Human +0.40 — cite 从 Limit 节点搬到 PW 节点
- `lim_node_count` AI -0.20 / Human -0.10 — Case A 把 3 个 Limit 改成 Context
- `method_pw_reach_avg` AI +0.25 / Human +0.15 — Method 反向 BFS 触达更多 PW

**对 fingerprint 的影响**：差距没缩小。AI vs Human 在 `pw_node_count` 仍 1.92×，`pw_total_cites` 仍 3.56×，`method_pw_reach_avg` 仍 1.51×。AI 论文"单 anchor + 浅 PW"指纹在更严格的图上保持。

**修改前快照**：保存在 `before_pw_lim_fix/`（14 个 JSON+SVG + 旧 metrics.csv），可直接 diff 对比。

---

## 9. Corpus 翻倍（2026-05-01）

**动机**：n=40 太小，无法做显著性检验或训分类器。翻倍到 n=80（AI 40 / Human 40），同时引入 ICLR Poster 维度（不只 Oral）。

**新数据**：
- **+20 AI papers** (FA0058–FA0235)：从 `analemma_fars_papers/rag_novelty_workspace_2026-03-19/fars_30_sample` 选 20 篇之前未用的 FARS papers
- **+20 ICLR 2025 Poster**：从 `iclr25_30_sample` 选 20 篇 ICLR 2025 接收 paper（非 oral）

**流程**：
1. PDF 拷贝到 `pdfs/{ai,human}/` 用统一命名
2. **6 个并行 extraction subagent**（每个 6-7 篇），按 SKILL.md 五阶段+Pass 3 抽 JSON 并 render SVG
3. **4 个并行 QA reviewer agent**（每个 10 篇），核查 type/edge/coverage，应用了 12 处自动修复（主要是边类型 marker 严格度）
4. 全语料 `validate_graph.py` 80/80 OK，0 warning
5. 重算 `metrics.csv`、重生成 `index.html`

**新增 paper 列表**：

AI（20）: FA0058, FA0063, FA0069, FA0073, FA0074, FA0115, FA0116, FA0153, FA0163, FA0172, FA0175, FA0181, FA0191, FA0193, FA0201, FA0209, FA0213, FA0214, FA0231, FA0235

ICLR Poster（20）: RaNA, AutoGDA, BSTaR, PatchTraining, CausalConcept, ContractivePolicy, FasterCache, PerplexityCorr, Anonymizer, ActBeacon, MRAGBench, MiniCoreset, AsyncMoE, HeadKV, OfflineHRL, OpenWorldRL, OscSSM, StemOB, TransformerSq, metabench

**主要发现**：fingerprint 在 n=80 上保持（详见 §5 总表）。`pw_total_cites`、`lim_scope_avg_cites`、`method_node_count` 三大信号都通过翻倍稳定性测试。

**接下来可以做**：
1. 现在样本足够做 t-test / Mann-Whitney U（n=40 each）
2. 训分类器（logistic / random forest）报 AUC
3. 把 ICLR Poster vs Oral vs anchor 三类 human paper 拆开看是否同质
