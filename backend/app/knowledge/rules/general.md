# 经验库 — 通用冷镦工艺规则 / General Cold-Heading Heuristics

> **来源 / Provenance:** 这些规则从 `cases/` + `standards/` 共 12 个真实工艺案例
> 加 `textbook_cases/` 25 个龚书第 8 章案例归纳而来,**不是教科书原文**。
>
> **使用方式 (重要):** 这些是**推导原则**,不是查表。LLM 应当根据零件特征
> 套用原则**自己算出工位数和工序顺序**,而不是按"哪个产品类别 → 几工位"查答案。

---

## 1. 工位数推导 / Station-count derivation (principle-based)

**不要按产品类别查表。按特征数累加:**

```
station_count = 1 (下料/整形) + 1 (终镦头部) + N_features
```

其中 `N_features` 按零件特征逐项累加:

| 特征 | 何时 +1 | 触发条件 |
|---|---|---|
| **head_predeform** | 头部预镦聚料 | head_d / shank_d > 1.4 (体积扩大需分两道) |
| **backward_extrusion** | 每个反挤特征 | 内六角 / 内梅花 / 凹头 / 内方 |
| **forward_extrusion** | 每个杆部减径段 | 螺纹底径减径 / 阶梯杆 / 锥杆 |
| **head_trim** | 头部修边 | 方头/T头/法兰 (因方变圆需切飞边) |
| **piercing** | 冲通孔 | 通孔件、需后续攻丝 |
| **end_chamfer** | 切尾倒锥 | 尾端 ≥ 30° 倒角 + 长杆件 (L/D > 4) |
| **two_blow_upset** | 强镦粗分二次 | head_d / shank_d > 2.3 (单道极限) |

**推导示例 (LLM 应当这样想,不是查表):**

例 A: 内六角圆柱头螺钉, head_d=20.7, shank_d=13.7, 螺纹底径 12.5
- head/shank = 1.51 > 1.4 → +1 head_predeform
- 内六角 → +1 backward_extrusion
- 螺纹底径减径 (13.73 → 12.5) → +1 forward_extrusion
- head/shank = 1.51 < 2.3 → 不需 two_blow_upset
- **stations = 1 + 1 + 3 = 5**

例 B: 六角法兰螺栓, head_d=24, shank_d=14, 无内特征
- head/shank = 1.71 > 1.4 → +1 head_predeform
- 法兰 (六角变法兰需修边) → +1 head_trim
- 无内特征,无减径
- **stations = 1 + 1 + 2 = 4**

例 C: 长杆铆接螺钉, head_d=14, shank_d=4, L=80
- head/shank = 3.5 > 2.3 → +1 head_predeform, +1 two_blow_upset
- 阶梯杆 (有 2 个减径段) → +2 forward_extrusion
- 尾端倒锥 → +1 end_chamfer
- **stations = 1 + 1 + 5 = 7**

---

## 2. 下料尺寸 / Blank sizing (continuous formulas)

### 直径

`blank_d` 选取目标:
- 优先选**最大杆部直径或螺纹中径附近** (减少最终 forward_extrusion 量)
- 一般 `blank_d ≈ 0.95 – 1.02 × shank_d` (略大,留 forward_extrusion 整形量)
- 当头部需要大幅镦粗 (head_d / shank_d > 1.7) 可适度选小,落在 0.85 – 0.95 × shank_d

观察的真实分布: `blank_d / shank_d` ∈ [0.85, 1.05] in factory cases。

### 长度 (体积守恒)

```
V_blank = V_head + V_shank_pre_extrusion + 5–8% 余量
blank_L = V_blank / (π/4 × blank_d²)
```

实操简化:
- 短件 (成品 L < 30mm): blank_L 约 = 头部体积折算 + 成品 L × 1.0
- 长螺栓 (L > 50mm): blank_L 约 = 头部体积折算 + 成品 L × (1.05 – 1.10)
- 螺纹底径减径段会**伸长** 5–15%, 必须扣除

观察范围: `blank_L / product_L` ∈ [1.05, 2.5] depending on head volume share。

---

## 3. 工位顺序原则 / Station-order principles

**核心原则: 先聚料,再成形,再细节。** 不要按"标准件模板"或"异形模板"查序列。

### 排序规则

1. **第 1 站永远是 `combined` / `upsetting`** —— 切料 + 整形,工件保持柱状
2. **若需 `head_predeform`**: 紧跟第 1 站,锥形过渡为下一站终镦做准备
3. **`heading` (终镦头部)**: 头部最终外径达成
4. **`backward_extrusion`**: 一定在 heading 之后(头部已成形,才能反挤)。多个反挤按"先大后小"
5. **`forward_extrusion`**: 一般在最后 1–2 站(避免后续工序破坏精度)。多段减径按"先粗减后精修"
6. **`trimming` / `piercing`**: 永远在结构成形完成后

### 不变约束

- 反挤之前头部必须已基本成形(否则反挤压力会破坏头型)
- 正挤减径段一旦做完,**禁止**在其后做镦粗(会失稳)
- 两次同向变形(如 2 道镦粗)之间最好插一道整形或退火点(冷加工硬化)

---

## 4. 物理极限 / Physical limits (从教材抽取的硬约束)

| 约束 | 极限值 | 来源 |
|---|---|---|
| 单道镦粗比 (D_out / D_in) | ≤ 2.3 | 龚书 Ch.8 + 1模2冲教程 |
| 单道镦粗高度比 (h_in / d_in) | ≤ 2.5 (l/d 镦锻规则) | 龚书 |
| 单道镦粗截面缩短率 Ep | 材料相关,见 verifier 表 | 1模2冲教程 25.7-2 |
| 正挤减面率 | ≤ 70% (一般 50–60% 最稳) | 龚书 |
| 反挤六角孔深径比 | ≤ 4 | 龚书 |
| 反挤圆孔深径比 | ≤ 6 | 龚书 |
| 体积守恒 (blank vs final) | 0.85 – 1.45 | 真实工厂案例统计 |

**关键认知**: 这些是材料物理硬约束,**不是经验软建议**。verifier 强制检查。

## 5. 后处理 / Post-processes (按特征,非按类别)

| 触发特征 | 必加后处理 |
|---|---|
| 任何外螺纹 | `thread_rolling` |
| 任何强度等级标注 ≥ 8.8 | `heat_treatment` |
| 任何内螺纹孔(攻丝孔) | `thread_tapping` (在 piercing 后) |
| 表面镀层 (Zn, Ni, 磷化) | 客户图标注才加,与冷镦无关 |

**不要按"产品类别"决定后处理**,按特征。

## 6. 材料适用性 / Material applicability

冷镦钢的工艺极限**几乎与牌号无关** —— 只要是合格冷镦钢,镦粗比 ≤ 2.3 通用。
材料牌号主要影响:
- **变形抗力**(影响模具寿命,不影响工序设计)
- **允许累积变形量** (Ep, 在 verifier 里有表)
- **是否需热处理** (高强度等级才需)

直接照抄客户图的材料牌号,**不要**因为材料推断工序数。

---

## 应用到 Step 3 的明确指令

LLM 在 Step 3 应按以下顺序思考:

1. **数特征**: 头部形状、内特征(六角/梅花/凹头)、杆部减径段数、尾端倒锥
2. **算 head/shank 比**: 决定要不要 head_predeform 和是不是 two_blow_upset
3. **套 §1 公式**: stations = 1 + 1 + N_features
4. **按 §3 顺序原则**排站
5. **按 §2 体积守恒**算 blank
6. **按 §4 物理极限**自检 (verifier 还会再检一遍)
7. **`cited_case_ids` 引用 2–3 个具有相似特征的案例** (不一定要同产品类别;
   可以是"它的反挤工序参考自 X","它的预镦比例参考自 Y")

**反模式 (不要做):**
- ❌ "这是某某标准件 → N 站" (查表)
- ❌ "我没见过这种件,所以保守用 6 站" (没推导)
- ❌ "引用最像的整件案例" (整件常找不到近邻;按特征引用更可靠)
