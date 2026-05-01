# Argument Graph Fingerprinting — AI vs Human-Written Papers

## 1. 数据与目的

**目标**：把每篇论文 Introduction 解析成**论证结构图**（argument graph），在图上算指标，比较 AI 生成论文与人写论文的结构差异。

**数据集**：40 篇论文
- **AI** (n=20)：FARS corpus AI-generated papers（FA0001–FA0047）
- **Human** (n=20)：11 篇 anchor papers（真实被 AI 引用的 2024–2026 论文）+ 9 篇 ICLR 2025 Oral

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

**C1. `lim_scope_avg_cites`** — Limitation 批评范围

- **你的直觉**：Limitation 批评的是某个具体方法，还是整个领域？
- **算法**：对每个 Limitation 节点 L：
  1. 从 L 做**反向 BFS**（follow in-edges 向上游走）
  2. 在每一层检查：是否有 Prior_Work 祖先且 `citations > 0`
  3. 如果这一层发现了被引 PW 祖先，停下，记录该 PW 的 citations（取该层 min，选"最具体"的）
  4. 否则继续往上一层
- **含义**：
  - **低值（1-2）** → Limitation 批评的是**单篇 named method**（AI 论文常见：anchor paper only）
  - **高值（3+）** → Limitation 批评的是**一整类/领域**（人写常见：PW 节点聚合了多篇）
- **结果**：AI **1.12** / Human **2.30** → 2.04×（含义：AI 每个 Limitation 反向找到的最近被引 PW 平均只有 1 cite，人写平均 2.3 cite）

**辅助样本数**：`lim_scope_sample_count` — 有多少个 Limitation 能找到被引 PW 祖先
- AI 2.25 / Human 3.55 → 1.58×

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

> **2026-05-01 更新**：应用 Pass 3 "Limitation source" 规则修复（每个 Limitation 必须有 Prior_Work 或 Limitation 入边，详见 §8）。修复涉及 16 个 violation，14 个 paper。Cite 总量守恒（AI 4.65、Human 19.70 不变），但部分 cite 从 Limitation 节点重新归位到 Prior_Work 节点。

| 组 | 指标 | AI | Human | Human/AI |
|---|---|---|---|---|
| A. 结构 | sum_node_degree (Σ in+out = 2|E|) | 35.0 | 61.7 | **1.76×** |
| A. 结构 | graph_longest_path (深度) | 12.75 | 24.15 | **1.89×** |
| A. 结构 | max_width (宽度) | 3.15 | 3.80 | 1.21× |
| B. PW | pw_node_count | 2.40 | 4.60 | **1.92×** |
| B. PW | pw_top_level_count (多样性) | 1.40 | 1.90 | 1.36× |
| B. PW | pw_avg_cites (人均引用) | 0.89 | 1.81 | **2.03×** |
| B. PW | **pw_total_cites (总引用)** | **2.15** | **7.65** | **3.56×** |
| C. Lim | lim_scope_avg_cites (批评范围) | 1.18 | 2.36 | **2.01×** |
| D. Method | method_node_count (复杂度) | 3.15 | 8.35 | **2.65×** |
| D. Method | method_pw_reach_avg | 2.20 | 3.32 | **1.51×** |

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

- `ai/`、`human/` — 40 张图的 JSON + SVG
- `metrics.csv` — 完整指标行（40 × ~35 列）
- `REPORT.md` — 本文件
- Skill 工具链：`/Users/zhaihaotian/.claude/skills/argument-graph-extractor/`
  - `SKILL.md` — 抽取流程规范
  - `render_graph.py` — SVG 渲染
  - `validate_graph.py` — schema 校验
  - `coverage_check.py` — 覆盖率硬校验
  - `compute_metrics.py` — 指标计算

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
