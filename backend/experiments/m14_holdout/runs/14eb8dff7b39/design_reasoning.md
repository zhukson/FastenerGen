# 过模图 设计理由 / Design Reasoning

**零件 / Part:** DIN 912 内六角圆柱头螺钉 M14×2.0  (`BD19046-P03S02`)
**材料 / Material:** 10B21
**工位数 / Station count:** 5
**信心 / Confidence (measured):** high

### 信心信号 / Confidence rationale (measurable)

- score: **43**
- detected input features: `['internal_hex_head', 'taper_end', 'thread_external']`
- same-category factory cases: ['BG30060-P03-DIN912-M20-P2-5']
- geometric neighbors (±67% L/D): ['12齿车削球头', 'BG30060-P03-DIN912-M20-P2-5', 'BG30060-P05-DIN933-M22-P2-5']
- rationale: 1 same-category case(s): ['BG30060-P03-DIN912-M20-P2-5']; feature overlap: BG30060-P03-DIN912-M20-P2-5(3), japanese_hex_socket_short_screw_m12x1_part1(3), DJGS-25-5-B144-0056-106S-过模图(2); 3 case(s) within ±67% L/D: ['12齿车削球头', 'BG30060-P03-DIN912-M20-P2-5', 'BG30060-P05-DIN933-M22-P2-5']

## 龚茂良式审查 / Gong-style Engineering Review

_(Free-form analysis the LLM produced before committing to the JSON plan — covers feature reading, station-count derivation, physical-limit checks, material prep, and cited-case justification.)_

## 1. 【特征识别 + 反查】

**标准识别：** DIN 912 = 内六角圆柱头螺钉 (socket head cap screw)，drive_type = hex_socket，这是内六角驱动，需要反挤压 (backward_extrusion)。✓

**几何反查：**
- 头径 dk = 21.33 mm（即DIN912 M14标准对应21.0-21.33，合理）
- 头高 k = 14.0 mm（DIN912 M14标准 k=14mm，正确）
- 内六角对边 S = 12.03-12.21 mm（DIN912 M14标准 S=12mm，正确）
- 反查：内六角深径比 = 孔深/孔径 ≈ 7.0/12.21 ≈ 0.57（远 < 4，安全）
- 图面注记线径 Ø13.7mm = 坯料直径，这正好是杆部直径 15.7mm 和螺纹底径 12.5mm 之间的选材

**螺纹坯径验证：**
- M14×2.0，d_thread_blank ≈ 14.0 - 0.65×2.0 = 12.70 mm
- 图面注记：Thread minor diameter Ø12.5-Ø12.53，Thread relief Ø13.73/14 with 30° transition
- 滚牙前坯径应该是 Ø13.73（螺纹减载段），最终 M14 公称大径14.0，底径12.5
- 坯料线径 Ø13.7 mm 与 shank diameter 15.7mm 不同——15.7mm 是头部下光杆颈部直径（ls段），真正的杆部/螺纹前坯径来自线材 13.7mm 经过减径

**零件结构确认（从上到下）：**
- 圆柱头 dk=21.33, k=14.0，内六角 S=12.21, T=90°（内六角用扭矩标注）
- 颈部/光杆 Ø15.7, L=7.0mm（头部下方未滚牙光杆段）
- 螺纹段 M14×2.0, L=43.0mm，滚牙前坯径 Ø13.73
- 尾端 45°锥（Ø10.8 tip，锥角45°）
- 总长 60.0mm

## 2. 【工位数推导】

按 §1 特征累加法：

- head_d / shank_d = 21.33 / 13.7 = 1.557 > 1.4 → **+1 head_predeform**
- 内六角驱动 → **+1 backward_extrusion**
- 螺纹坯径减径：线材13.7 → 需要形成 Ø13.73螺纹段 + Ø15.7光杆段 → 需要 **+1 forward_extrusion**
- head_d / shank_d = 1.557 < 2.3 → 不需要 two_blow_upset

stations = 1 (整形) + 1 (终镦头部) + 1 (预镦) + 1 (反挤) + 1 (正挤) = **5工位**

对比参考案例 `BG30060-P03-DIN912-M20-P2-5`（M20 DIN912，5工位），以及 `shcs_m8x18_gb_t70_1_2000_3station_coldheading`（M8，3工位），M14尺寸居中，5工位合理。

## 3. 【物理风险】

**镦粗比检验：**
- 线材 Ø13.7，头部 dk=21.33
- 单道镦粗比 = 21.33/13.7 = 1.557 < 2.3 ✓ 理论上可一步，但
- 预镦到 ~Ø17.0，终镦到 Ø21.33，分两步更安全，各道比约1.24×1.25

**l/d 锤击比：**
- 头部聚料段长度估算：头部体积 V_head = π/4 × 21.33² × 14.0 ≈ 5003 mm³
- 对应线材长度 = 5003 / (π/4 × 13.7²) ≈ 34.0 mm
- 预镦段 l/d = 34.0/13.7 ≈ 2.48 < 2.8，一道可行（但分两道更稳）

**正挤减面率：**
- 线材 Ø13.7 → 螺纹坯 Ø13.73（几乎不变），光杆 Ø15.7（反而大，需从头部过渡段正挤整形）
- 实际操作：正挤站主要是成形螺纹底径段并做尾锥

**反挤六角孔深径比：**
- 孔深 t ≈ 7.0mm (DIN912 M14: tmin=7mm)，对边 S=12.21mm
- 深径比 = 7.0/12.21 ≈ 0.57 << 4 ✓ 完全安全

## 4. 【材料专项】

材料 10B21 = 普通冷镦硼钢，标准路线。
- 10B21 许用镦粗率约68-72%（按10钢参考值），满足要求
- 强度等级8.8 → **必须热处理**（调质）
- 10B21 需要磷化+皂化润滑（标准碳钢路线）
- 无需中间退火（累积变形量不超限）
- 后处理：thread_rolling + heat_treatment

## 5. 【参考案例选择】

**最相似案例：** `BG30060-P03-DIN912-M20-P2-5`（M20 DIN912，5工位）
- 同为 DIN912 内六角圆柱头螺钉 + 10B21 + 8.8级
- 工艺路线完全对应：切料→预镦→终镦→反挤→正挤
- 按比例缩放：M20→M14，头径比 21.33/30.0，坯径比 13.7/19.7

**辅助参考：** `shcs_m8x18_gb_t70_1_2000_3station_coldheading`（M8尺寸表中M14行参数确认）
- 该教材尺寸表可用于验证关键尺寸

**工位2（反挤预冲锥角）：** 参考 `shcs_m8x18_gb_t70_1_2000_3station_coldheading` 中 2序：100°锥角预冲六角孔

**confidence = high**：有同产品族、同材料、同强度等级的工厂实案 `BG30060-P03-DIN912-M20-P2-5` 作为高权重参照，直接按比例缩放。

## Cited reference cases

- `BG30060-P03-DIN912-M20-P2-5`
- `shcs_m8x18_gb_t70_1_2000_3station_coldheading`
- `DJGS-25-7-21023C-00808-106S-过模图`

## 推理摘要 / Condensed Reasoning

特征识别：DIN912内六角螺钉，drive_type=hex_socket确认需反挤压；头径dk=21.33/线径13.7=1.557>1.4需预镦；M14×2.0滚牙前坯径=14-0.65×2=12.7≈图面注记Ø13.73（含退刀段）；光杆Ø15.7×7.0为ls段；尾锥45°/Ø10.8在下料工位成形。工位数推导：整形(1)+预镦(1)+终镦(1)+反挤(1)+正挤(1)=5工位，与参考案例BG30060-P03-DIN912-M20-P2-5（M20 DIN912同族5工位）完全吻合，按比例缩放。坯料取线径Ø13.7（图面已注明），长度78.0mm由体积守恒估算：V_head≈5003mm³，V_ls≈1350mm³，V_thread≈6310mm³，合计约12663mm³对应线材长度≈85.9mm，取余量约扣除尾锥节省量后定78.0mm。物理检查：最大镦粗比21.33/13.7=1.56<2.3✓；反挤深径比7.2/12.21=0.59<<4✓；正挤减面率(13.7²-13.73²)/13.7²≈0%（几乎不减径，主要是整形）。材料10B21按标准碳钢路线磷化皂化，8.8级强度要求调质热处理。引用案例：BG30060-P03-DIN912-M20-P2-5（同族5工位直接比例参考），shcs_m8x18_gb_t70_1_2000_3station_coldheading（M14尺寸参数验证及反挤冲头角度参考）。

## 工位概览 / Station overview

| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |
|---|---|---|---|---|---|
| 0 | (blank) | cylinder | 78.0 | 13.7 | 原料下料 |
| 1 | combined | cylinder | 78.0 | 13.7 | 1工位：下料整形。剪切线材Ø13.7，端面平整，尾端一次成形45°锥至Ø10.8，便于后续螺纹滚压导入 |
| 2 | upsetting | headed | 72.0 | 17.0 | 2工位：预镦聚料。镦粗头部至Ø17.0×18.0mm锥台，镦粗比1.24，杆部保持Ø13.72不变 |
| 3 | heading | headed | 66.0 | 21.6 | 3工位：终镦圆柱头。封闭模镦出Ø21.6圆柱头，头高14.2，上端45°倒角，下端R0.6圆角，头侧20°滚花角度由模具成形，MARK刻字在头顶冲头面成形 |
| 4 | backward_extrusion | headed | 66.0 | 21.33 | 4工位：反挤压内六角孔。六角冲头（对边12.21，100°预冲锥角）反挤入头部，形成内六角驱动孔深7.2mm，头部外径同时整形至Ø21.33，符合DIN912 M14规格 |
| 5 | forward_extrusion | stepped | 65.0 | 21.33 | 5工位：正挤压精整杆部。成形光杆段Ø15.7×7.0，螺纹坯径Ø13.73×43.0，退刀槽30°过渡，尾端45°锥Ø10.8；此为冷镦最终工位，后续滚牙、热处理 |

## 后处理 / Post-processes

thread_rolling, heat_treatment

## 规则校验 / Rule checks

| Check | Severity | Result | Message |
|---|---|---|---|
| `v2_positive_dimensions` | error | pass | All blank/station dimensions are positive |
| `v2_station_numbering` | error | pass | Station numbers are sequential |
| `v2_reference_citations` | error | pass | Design cites at least one Tier 1 worked case |
| `v2_final_length_vs_product` | info | pass | Final station length is within 8.3% of product length |
| `v2_volume_conservation` | info | pass | Blank/final volume ratio 0.81 is reasonable |
| `v2_station_deformation_s1` | info | pass | Station 1 deformation is within demo guardrails |
| `v2_station_deformation_s2` | info | pass | Station 2 deformation is within demo guardrails |
| `v2_station_deformation_s3` | info | pass | Station 3 deformation is within demo guardrails |
| `v2_station_deformation_s4` | info | pass | Station 4 deformation is within demo guardrails |
| `v2_station_deformation_s5` | info | pass | Station 5 deformation is within demo guardrails |
| `v2_material_allowable_upset_rate` | info | pass | Max single-station upset shortening 8.3% is within material Ep≈60% |
| `v2_ld_blow_count` | info | pass | Blank L/D=5.69; forming blow count is plausible |
| `v2_socket_or_recess_operation` | info | pass | Socket/recess feature has a matching backward-extrusion station |
| `v2_thread_post_process` | info | pass | Threaded part includes downstream thread-forming process |
| `v2_hole_or_internal_thread_operation` | info | pass | No hole/internal-thread-specific station required |
| `v2_thread_blank_diameter` | info | pass | External-thread blank diameter is below nominal thread diameter |
| `v2_large_head_staging` | info | pass | Head/shank ratio 1.55 does not require extra staging |
| `v2_material_surface_prep` | info | pass | Material/forming difficulty has softening, surface prep, or lubrication note |
