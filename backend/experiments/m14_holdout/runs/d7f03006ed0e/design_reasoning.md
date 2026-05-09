# 过模图 设计理由 / Design Reasoning

**零件 / Part:** DIN 912 内六角圆柱头螺钉 M14×2.0×140L  (`BD19046-P03S02`)
**材料 / Material:** 10B21
**工位数 / Station count:** 5
**信心 / Confidence (measured):** medium
**LLM self-reported confidence:** high (overridden by measured neighbor density)

### 信心信号 / Confidence rationale (measurable)

- score: **41**
- detected input features: `['internal_hex_head', 'internal_recess', 'long_thin_shank', 'taper_end', 'thread_external']`
- same-category factory cases: ['BG30060-P03-DIN912-M20-P2-5']
- geometric neighbors (±67% L/D): ['BG30060-P03-DIN912-M20-P2-5']
- rationale: 1 same-category case(s): ['BG30060-P03-DIN912-M20-P2-5']; feature overlap: BG30060-P03-DIN912-M20-P2-5(4), japanese_hex_socket_short_screw_m12x1_part1(3), DJGS-25-5-B144-0056-106S-过模图(2); 1 case(s) within ±67% L/D: ['BG30060-P03-DIN912-M20-P2-5']

## 龚茂良式审查 / Gong-style Engineering Review

_(Free-form analysis the LLM produced before committing to the JSON plan — covers feature reading, station-count derivation, physical-limit checks, material prep, and cited-case justification.)_

## 1. 【特征识别 + 反查】

**标准识别：** DIN 912 明确标注 → 内六角圆柱头螺钉（Socket Head Cap Screw）。`drive_type = "hex_socket"` 与标准完全一致，无歧义。

**尺寸反查：**
- 头径 21.33 mm（DIN 912 M14 规定 dk≈21.33，标准值吻合）
- 头高 14.0 mm（DIN 912 M14 规定 k=14，吻合）
- 内六角对边 12.21 mm（DIN 912 M14 规定 S=12，12.21 为对角过渡，合理）
- 线径 Ø13.7 mm（notes 明确标注）
- 螺纹坯径 Ø12.5–12.53（notes 标注，对应 M14×2.0：14 - 0.65×2.0 = 12.7，略偏小但在搓丝浮动范围内）
- 光杆段 Ø15.7（略大于螺纹 M14，为非全螺纹段）
- 总长 140 mm，头高 14 mm → 杆长 = 140 - 14 = 126 mm（含光杆 43 + 螺纹段 49.8 + 余量）

**几何验证：** head/shank = 21.33/15.7 = 1.358 ≈ 1.36 → 接近 1.4 阈值，需预镦（但属于临界值，可谨慎安排一道预镦）。实际上头径与线径比 = 21.33/13.7 = 1.557 >> 1.4，**必须预镦**。

**材料：** 10B21 冷镦硼钢，标准冷镦钢，走常规磷化皂化路线，无需特殊处理。强度等级 8.8 → 需热处理（淬火回火）。

## 2. 【工位数推导】

从特征逐项累加：

- 基础：1（切料整形）+ 1（终镦头部）= 2
- head_predeform：21.33 / 13.7 = 1.557 > 1.4 → **+1**
- backward_extrusion（内六角孔）：**+1**
- forward_extrusion（杆部减径：光杆 Ø15.7 → 螺纹坯 Ø12.5，减面率 = 1-(12.5²/15.7²) = 1-0.634 = 36.6%，需一道正挤）：**+1**
- two_blow_upset：21.33/13.7 = 1.557 < 2.3 → 不需要，但头/坯比较大，预镦+终镦足够
- end_chamfer（尾端 45° 锥，L/D = 140/14 > 4）：尾端倒角在切料工位完成，不单独计站

**station_count = 2 + 1 + 1 + 1 = 5**

与库内案例 `BG30060-P03-DIN912-M20-P2-5`（M20 DIN912 5工位）和 `shcs_m8x18_gb_t70_1_2000_3station_coldheading` 模板一致（M8 3工位是因为头/杆比小、杆短；M14×140L 杆更长，需要专门的正挤杆部工位）。

## 3. 【物理风险】

**单道镦粗比检验：**
- 线径 Ø13.7，预镦后头部预扩至约 Ø17.5 → 比值 17.5/13.7 = 1.28 < 2.3 ✓
- 终镦 Ø17.5 → 21.33 → 比值 21.33/13.7 = 1.56，但分两道，单道比 1.28 和 1.22 均安全 ✓

**正挤减面率：**
- 光杆 Ø15.7 → 螺纹坯 Ø12.5：减面率 ≈ 37% < 70% ✓（安全）
- 但光杆段还需从线径 13.7 正挤至 15.7（实际线径比光杆小），这说明杆部光杆段是**留线径**，无需正挤扩径，只有螺纹段缩径

**反挤深径比：** 内六角对边 12.21 mm → 深度按 DIN 912 M14 规定 t ≈ 8 mm（最小），深径比 = 8/12.21 ≈ 0.65 << 4 ✓

**长杆稳定性：** 总长 140 mm，线径 13.7，L/D = 10.2，不存在切料后整形的稳定性问题（机器夹料稳定）。

**累积变形：** 10B21 许用镦粗率 ≈ 65%，本件头部面积扩大比 = (21.33/13.7)² = 2.42，折算线性变形率 ≈ 59% < 65% ✓

## 4. 【材料专项】

- **10B21**：标准冷镦硼钢，预处理：球化退火（出厂已完成）+ 磷化皂化；后处理：热处理（淬火回火至 8.8 级 800–830 MPa）
- 强度等级 8.8 → 必须热处理
- 外螺纹 M14×2.0 → 必须滚丝（thread_rolling）
- MARK=TASK 8.8 标识 → 终镦模印字 0.2mm 深凹字，在终镦头部工位一并成形
- 尾端 45° 倒角 Ø10.8 → 在切料整形工位做，不单独计站
- T:90（滚花/压纹深度）→ 头部侧面滚花，可列为 knurling 后处理

## 5. 【参考案例选择】

**最相似案例：** `BG30060-P03-DIN912-M20-P2-5`（DIN912 M20 5工位）
- 同标准 DIN 912、同材料 10B21、同强度 8.8
- 工序完全平行：切料→预镦→终镦→反挤内六角→正挤杆部
- 本件 M14 规格比 M20 小，头/杆比类似（M20: 30/19.67=1.52，本件 21.33/13.7=1.56）
- **直接引用该 case 的工序模板**，按 M14 尺寸等比缩放

**辅助参考：** `shcs_m8x18_gb_t70_1_2000_3station_coldheading`（M8 标准尺寸表 + 反挤工艺参数）

**置信度：high** — 有同类别同材料同强度 5 工位已验证案例。

## Cited reference cases

- `BG30060-P03-DIN912-M20-P2-5`
- `shcs_m8x18_gb_t70_1_2000_3station_coldheading`
- `japanese_hex_socket_short_screw_m12x1_part1`

## 推理摘要 / Condensed Reasoning

特征识别：DIN 912标准内六角圆柱头螺钉，drive_type=hex_socket确认，头径21.33mm对应M14规格标准值，内六角对边12mm（12.21为对角径）。材料10B21冷镦硼钢，强度8.8级需热处理。工位数推导：头径/线径=21.33/13.7=1.56>1.4需预镦（+1），内六角反挤（+1），螺纹段正挤缩径（+1），合计5工位。坯料：按体积守恒，V_头=π/4×21.33²×14≈4994mm³，V_光杆=π/4×15.7²×43≈8305mm³，V_螺纹=π/4×12.5²×97.8≈11994mm³，总V≈25293mm³，坯料V=π/4×13.7²×L，L≈171mm，加5%余量取176mm；工序：①切料整形（L176/Ø13.7，尾端45°锥至Ø10.8）→②预镦头部（Ø17.5×18，镦粗比1.28）→③终镦圆柱头（Ø21.33×14，刻TASK 8.8）→④反挤内六角孔（AF12/深9mm）→⑤正挤螺纹坯（Ø12.5，光杆Ø15.7×43保留）。物理验证：单道镦粗比最大1.56（两道分担后<1.3），正挤减面率37%，反挤深径比0.75，全部安全。后处理：滚丝M14×2.0（6g）、热处理至8.8级、磷化皂化（预处理）、头部侧面T:90滚花。参考案例：BG30060-P03-DIN912-M20-P2-5（DIN912 M20 5工位，同工序模板等比缩放至M14）；shcs_m8x18_gb_t70_1_2000_3station_coldheading（内六角反挤工艺参数参考）。

## 工位概览 / Station overview

| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |
|---|---|---|---|---|---|
| 0 | (blank) | cylinder | 176.0 | 13.7 | 原料下料 |
| 1 | combined | cylinder | 176.0 | 13.7 | 切料工位：Ø13.7线材剪切为L≈176mm坯料（按体积守恒计算），尾端同步成形45°锥倒角至Ø10.8，前端面整平，为后续预镦头部做定位准备 |
| 2 | upsetting | headed | 163.0 | 17.5 | 预镦工位：聚料头部扩径至Ø17.5，锥形过渡，单道镦粗比1.28<2.3安全，杆部保持Ø13.7 |
| 3 | heading | headed | 156.0 | 21.33 | 终镦头部工位：成形最终圆柱头Ø21.33×H14.0，头顶20°倒角，头下Ø13.7~Ø21.33过渡R0.6，冲头刻TASK 8.8字样 |
| 4 | backward_extrusion | headed | 156.0 | 21.33 | 反挤压成形内六角孔：对边AF=12mm，对角=12.21mm，孔深≥9mm（tmin per DIN 912 M14）；30°锥角导入冲头，孔底R0.5；深径比<1，远低于4的极限 |
| 5 | forward_extrusion | stepped | 154.0 | 21.33 | 正挤杆部工位：螺纹段从Ø13.7正挤缩径至搓丝坯径Ø12.5（减面率37%），光杆段Ø15.7×43mm保持，成品总长≈154mm（头14+光杆43+螺纹坯97），尾端倒锥Ø10.8×45° |

## 后处理 / Post-processes

thread_rolling, heat_treatment, phosphating, knurling

## 规则校验 / Rule checks

| Check | Severity | Result | Message |
|---|---|---|---|
| `v2_positive_dimensions` | error | pass | All blank/station dimensions are positive |
| `v2_station_numbering` | error | pass | Station numbers are sequential |
| `v2_reference_citations` | error | pass | Design cites at least one Tier 1 worked case |
| `v2_final_length_vs_product` | info | pass | Final station length is within 10.0% of product length |
| `v2_volume_conservation` | info | pass | Blank/final volume ratio 0.81 is reasonable |
| `v2_station_deformation_s1` | info | pass | Station 1 deformation is within demo guardrails |
| `v2_station_deformation_s2` | info | pass | Station 2 deformation is within demo guardrails |
| `v2_station_deformation_s3` | info | pass | Station 3 deformation is within demo guardrails |
| `v2_station_deformation_s4` | info | pass | Station 4 deformation is within demo guardrails |
| `v2_station_deformation_s5` | info | pass | Station 5 deformation is within demo guardrails |
| `v2_material_allowable_upset_rate` | info | pass | Max single-station upset shortening 7.4% is within material Ep≈60% |
| `v2_ld_blow_count` | info | pass | Blank L/D=12.85; forming blow count is plausible |
| `v2_socket_or_recess_operation` | info | pass | Socket/recess feature has a matching backward-extrusion station |
| `v2_thread_post_process` | info | pass | Threaded part includes downstream thread-forming process |
| `v2_hole_or_internal_thread_operation` | info | pass | No hole/internal-thread-specific station required |
| `v2_thread_blank_diameter` | info | pass | External-thread blank diameter is below nominal thread diameter |
| `v2_large_head_staging` | info | pass | Large head/shank ratio 1.71 is split across staged preforming |
| `v2_material_surface_prep` | info | pass | Material/forming difficulty has softening, surface prep, or lubrication note |
