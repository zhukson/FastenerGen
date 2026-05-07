# 经验库 — 通用冷镦工艺规则 / General Cold-Heading Heuristics

> **来源 / Provenance:** 这些规则是从 `backend/app/knowledge/cases/` 和 `standards/`
> 里的 12 个真实工艺案例（8 个异形件 + 4 个标准件）中归纳出来的，**不是教科书引用**。
> 当数据集扩大到 30+ 案例后需要复核。

---

## 1. 工位数选择 / Station-count selection

按观察到的产品类别 → 典型工位数：

| 产品类别 (product_category) | 典型工位数 | 数据源 |
|---|---|---|
| `ball_head` (车削球头)        | 4   | N=1 |
| `rivet_pin` (冲铆轴销)        | 4   | N=1 |
| `hex_bolt_DIN933`            | 4   | N=2  (M18, M22 都是 4 站) |
| `socket_cap_screw_DIN912`    | 5   | N=2  (M14, M20 都是 5 站) |
| `through_hole_part`          | 5   | N=1 |
| `square_T_head`              | 6   | N=1 |
| `special_shape` (异形)        | 5–6 | N=3 |
| `riveting_screw` (铆接螺钉)    | 7   | N=1  (最多工位，因杆部细长) |

**经验法则：**
- DIN 标准件（hex / socket cap）一般 4–5 工位。
- 头部为方/T形 + 后续切边/冲孔的件比标准件**多 1–2 工位**。
- 杆部细长（成品 D < 8mm）或带细深特征的，工位数往往 **≥ 6**。

## 2. 下料尺寸 / Blank sizing

观察到的 **max_workpiece_D / blank_D 比值** 范围（衡量整体镦粗强度）：

- 标准件 (DIN912/933): 1.54 – 1.70 — 因为头部体积适中
- 多数异形件: 1.38 – 2.30
- 极端情况: 2.73 (`DJGS-25-5-B144-0056` — 大头小杆)

**下料直径选择：**
- 多数案例 blank_D ≈ 0.5 – 0.8 × max_workpiece_D
- 当 max_D / blank_D > 2.3 时，**必须**分两道镦粗（单道物理极限）

**下料长度 = 体积守恒 + 5–10% 余量：**
- 短件（成品 L < 30mm）: blank_L ≈ 1.0 – 2.5 × 成品 L
- 长螺栓 (DIN912/933 标准): blank_L 大致 = 头部体积折算 + 杆部 L × (1 + 5%)

## 3. 工位顺序 / Station-order patterns

**标准件（DIN912/933）模板（5 站典型）：**
1. `combined` — 切料 + 整形（cylinder）
2. `upsetting` — 预镦聚料（headed，过渡锥台）
3. `heading` — 终镦头部成形
4. `backward_extrusion` — 反挤六角孔（DIN912）/ 修边
5. `forward_extrusion` — 正挤螺纹坯（细径段）

**异形件（带方头/T头）模板（6 站典型）：**
1. `upsetting` — 整形/镦粗
2. `forward_extrusion` — 阶梯杆部成形
3. `heading` — 圆头预成形
4. `combined` — 方头压制 + 凹坑
5. `trimming` — 切边修方
6. `piercing` — 冲通孔（如需后续攻丝）

## 4. 物理极限 / Physical limits

- **单道镦粗比 ≤ 2.3**（D_out / D_in）。超过必定开裂或折叠，分两道。
- **正挤减面率 ≤ 70%**（一般 50–60% 最稳）。
- 反挤孔的 **深径比 ≤ 4**（六角孔）/ ≤ 6（圆孔）。
- **方变圆 / 圆变方** 一道做完，但需要 **次工位切边** 修四角飞边。

## 5. 后处理 / Post-processes

按类别归纳的后处理组合：

| 类别 | 典型后处理 |
|---|---|
| 标准螺栓 (DIN912/933) | `thread_rolling` + `heat_treatment` |
| 螺钉/铆接螺钉 | `thread_rolling` + 可选 `heat_treatment` |
| 方T帽（带攻丝孔）| `thread_rolling`（攻内螺纹） |
| 销/铆钉/通孔件 | 无（冷镦后直接出货或电镀） |
| 球头（车削件） | `thread_rolling` + `heat_treatment` |

**默认值：**
- 任何螺纹件都要 `thread_rolling`。
- 强度等级 ≥ 8.8 一般要 `heat_treatment`。
- 表面 `zinc_plating` / `phosphating` 与冷镦工艺无关，按客户要求加。

## 6. 材料对应 / Material codes 

观察到的材料：
- `10B21` — 通用冷镦钢（DIN 标准件）
- `106S` / `105S` / `YT105S` — 客户自定义牌号（异形件常见）

材料一般直接照抄客户图，工艺设计本身**不依赖**材料牌号细节，但镦粗比上限（≤2.3）对所有冷镦钢通用。

---

## 应用到 Step 3 的提示

- 先按 `product_category` 找到典型工位数 → 给出 station_count 候选
- 计算 `max_workpiece_D / blank_D` → 决定要不要分两道镦粗
- 套用对应模板（DIN 标准 vs 异形）作为站序起点，再按客户图特殊特征插入 `combined` / `piercing` 站
- `cited_case_ids` 至少引用 1 个同类别案例 + 1 个最接近尺寸的案例
