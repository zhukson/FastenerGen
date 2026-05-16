# 过模图 设计理由 / Design Reasoning

**零件 / Part:** 四方T头内螺纹嵌件（四方头带十字凹槽）  (`DJGS-25-8-B001-0358`)
**材料 / Material:** 106S
**工位数 / Station count:** 6
**信心 / Confidence (measured):** medium

### 信心信号 / Confidence rationale (measurable)

- score: **19**
- detected input features: `['external_flange_head', 'external_square_head', 'thread_external']`
- same-category factory cases: (none)
- geometric neighbors (±67% L/D): ['DJGS-25-5-B144-0056-106S-过模图']
- rationale: no same-category factory case; feature overlap: motorcycle_ebike_shock_absorber_piston_rod_8_33(2), DJGS-22-2-四方通孔-105S-过模图(1), DJGS-24-6-冲铆轴销-YT105S-过模图(1); 1 case(s) within ±67% L/D: ['DJGS-25-5-B144-0056-106S-过模图']

## 龚茂良式审查 / Gong-style Engineering Review

_(Free-form analysis the LLM produced before committing to the JSON plan — covers feature reading, station-count derivation, physical-limit checks, material prep, and cited-case justification.)_

## 1. 【特征识别 + 反查】

零件描述：四方T头紧固件，带内螺纹（四方法兰T头螺母/嵌件）。

关键特征逐条分析：
- **头部类型**: "flange" + notes说"四方头带4-R2.5圆角" → 这是**四方头**（不是六角头，不是内六角驱动），最终需切边修整成四方外形
- **头部尺寸**: diameter=17.65，height=3.0。注意17.65是四方头对角距（外接圆），四方头对边距 = 17.65/√2 ≈ 12.48mm，或者17.65是外接圆直径，需要切边形成四方形
- **杆部**: diameter=7.93，length=14.0，overall_length=17.0mm（头高3.0 + 杆长14.0 = 17.0mm ✓）
- **内螺纹特征**: description说"internal thread"，notes说"头部带十字凹槽特征"——注意：**十字凹槽是头部驱动特征（如十字槽/刻线），不是内螺纹孔本身**。但description明确说带internal thread，推断杆部有内螺纹（需攻丝）或头部有十字凹槽成形
- **head/shank比**: 17.65/7.93 ≈ 2.23，接近单道镦粗极限2.3，需要分两次预镦
- **材料106S**: 这是冷镦钢牌号（工厂自定义，非不锈钢），按普通碳钢冷镦工艺处理
- **机型YT-106S**: 六工位冷镦机（与案例DJGS-25-5-B144-0056-106S同机型）

**几何反查**：
- 若17.65为外接圆直径，四方边长 = 17.65/√2 × √2 = 17.65mm（边长对角），实际四方对边距 ≈ 17.65 × cos45° × 2 ≈ 12.5mm
- 更可能：17.65是切边前圆坯直径，切边后形成四方头，四方头对边距约=17.65×(√2/2)×？…实际case DJGS-22-2中外径15.05对应四方15.05×15.05
- 头部高度3.0mm，较薄的T头法兰特征

**十字凹槽**：头部带十字凹槽特征 → 这需要在成形过程中在头部顶面压出十字槽（类似于驱动槽），可在终镦时一并成形，或后续加工

## 2. 【工位数推导】

基础：station_count = 1(整形) + 1(终镦) + N_features

特征累加：
- head_d/shank_d = 17.65/7.93 ≈ 2.23，非常接近2.3极限，>1.4 → **+1 head_predeform**（初镦聚料）
- 2.23 < 2.3，理论上不需要强制二次预镦，但为安全建议分两次 → 边界情况，保守+1 → **+1 two_blow_upset**（预镦→二镦）
- 四方头需切边 → **+1 head_trim（trimming）**
- 内螺纹/通孔（description说internal thread，杆部需攻丝）：若是通孔需**+1 piercing**；若是盲孔则仅需攻丝（后处理）。根据"T头螺母/嵌件"描述，很可能是通孔件
- 十字凹槽：可在终镦头部时一并成形，**不额外加工位**

推导：1(整形坯料) + 1(预镦头部) + 1(二次镦粗头部) + 1(终镦四方头+十字槽) + 1(切边四方) + 1(冲通孔) = **6工位**

参考机型YT-106S = 六工位，与推导完全吻合。

## 3. 【物理风险】

- **头部镦粗比**：从线径≈8.0mm → 头部圆坯直径≈18mm（切边前），比值=18/8=2.25，接近2.3上限
  - 分两道预镦：第1道8.0→12mm（比值1.5），第2道12→17mm（比值1.42）→ 安全
- **杆部**：basic圆柱，无减径，不需要forward_extrusion
- **内螺纹/通孔冲孔**：后道工序，冲孔模分离，不影响头部成形
- **L/D验证**：blank_L/blank_D估算，头部体积+杆部体积，后算blank尺寸
- **头高3mm很薄**：终镦时需注意充填，采用封闭镦锻，γ≈1.75-2.0

## 4. 【材料专项】

材料106S：工厂自定义冷镦钢（参考案例DJGS-25-5-B144-0056-106S同用此材料），属普通碳钢冷镦用料，类似10B21。
- 预处理：磷化+皂化（标准冷镦预处理）
- 后处理：若有内螺纹 → thread_tapping（攻丝）；根据产品用途可能需要电镀/表面处理
- 无需中间退火（变形量不超极限，且非不锈钢/铝合金）

## 5. 【参考案例选择】

最相似案例：
1. **DJGS-22-2-四方通孔-105S-过模图**（5工位，四方法兰+通孔，切边为最终四方形）→ 直接引用切边站和通孔冲孔顺序
2. **DJGS-25-5-B144-0056-106S-过模图**（6工位，同材料106S，同机型YT-106S，法兰头部+冲孔）→ 引用工艺节奏
3. relevant_subprocesses中 **DJGS-22-2四方通孔station_n=5(trimming)**：切边为最终四方形15.05×15.05，4-R1.5，与本件R2.5圆角四方头非常类似

主要区别：本件头部极薄（3mm），且description说T头带internal thread，比DJGS-22-2的简单通孔法兰更复杂。

Confidence：**medium**（有同材料案例，有类似四方法兰切边案例，但T头+十字槽+内螺纹组合没有完全相同的factory case）

## Cited reference cases

- `DJGS-22-2-四方通孔-105S-过模图`
- `DJGS-25-5-B144-0056-106S-过模图`
- `DJGS-25-2-B120-0044-YT105S-过模图`

## 推理摘要 / Condensed Reasoning

特征识别：四方头（切边前外接圆Φ17.65）+十字凹槽+内螺纹通孔，材料106S普通冷镦钢，机型YT-106S（六工位）。head/shank比≈2.23接近极限，分两道预镦安全（第1道Φ8→Φ12.5，比值1.56；第2道Φ12.5→Φ16.5，比值1.32）。工位推导：1整形+1预镦+1二镦+1终镦（含十字槽）+1切边四方+1冲通孔=6工位，与YT-106S机型匹配。十字凹槽在终镦工位同步压入冲头成形，不额外增加工位。切边工位参考案例DJGS-22-2-四方通孔-105S（station5 trimming，四方15.05×15.05, 4-R1.5），本件对应四方R2.5圆角更大。冲通孔后续需攻丝（thread_tapping）成内螺纹。坯料估算：头部体积≈π/4×17.65²×3.0≈733mm³，杆部体积≈π/4×7.93²×14.0≈691mm³，通孔减料≈π/4×6.0²×17.0≈481mm³，净体积≈943mm³，加5%余量≈990mm³，坯径Φ8.0则blank_L≈990/(π/4×8²)≈19.7mm，取22.5mm含切料损耗。材料106S无需中间退火，标准磷化皂化润滑。

## 工位概览 / Station overview

| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |
|---|---|---|---|---|---|
| 0 | (blank) | cylinder | 22.5 | 8.0 | 原料下料 |
| 1 | upsetting | cylinder | 22.8 | 8.08 | 第一工位：整形坯料，端部倒角，确保端面平整，为头部聚料做准备 |
| 2 | upsetting | headed | 18.5 | 12.5 | 第二工位：一次预镦，将头部料团镦粗至Φ12.5mm，杆径基本保持，头部呈圆台形 |
| 3 | upsetting | headed | 17.3 | 16.5 | 第三工位：二次预镦，头部扩径至Φ16.5mm，为终镦四方头提供足够体积，头部角部预留R2.0过渡 |
| 4 | heading | headed | 17.0 | 18.5 | 第四工位：终镦头部至Φ18.5，同步压入十字凹槽特征，R2.5圆角预备四方切边后保留 |
| 5 | trimming | T_head | 17.0 | 17.65 | 第五工位：切边修整为最终四方头外形，4-R2.5圆角，外接圆直径Φ17.65，对边距约12.48mm，去除飞边，头高定型3.0mm |
| 6 | piercing | T_head | 17.0 | 17.65 | 第六工位：冲通孔Φ6.0，为后续攻内螺纹预备底孔，孔端倒角C0.5 |

## 后处理 / Post-processes

thread_tapping, hardness_inspection

## 规则校验 / Rule checks

| Check | Severity | Result | Message |
|---|---|---|---|
| `v2_positive_dimensions` | error | pass | All blank/station dimensions are positive |
| `v2_station_numbering` | error | pass | Station numbers are sequential |
| `v2_reference_citations` | error | pass | Design cites at least one Tier 1 worked case |
| `v2_final_length_vs_product` | info | pass | Final station length is within 0.0% of product length |
| `v2_volume_conservation` | info | pass | Blank/final volume ratio 0.79 is reasonable |
| `v2_station_deformation_s1` | info | pass | Station 1 deformation is within demo guardrails |
| `v2_station_deformation_s2` | info | pass | Station 2 deformation is within demo guardrails |
| `v2_station_deformation_s3` | info | pass | Station 3 deformation is within demo guardrails |
| `v2_station_deformation_s4` | info | pass | Station 4 deformation is within demo guardrails |
| `v2_station_deformation_s5` | info | pass | Station 5 deformation is within demo guardrails |
| `v2_station_deformation_s6` | info | pass | Station 6 deformation is within demo guardrails |
| `v2_material_allowable_upset_rate` | info | pass | Max single-station upset shortening 18.9% is within material Ep≈68% |
| `v2_ld_blow_count` | info | pass | Blank L/D=2.81; forming blow count is plausible |
| `v2_socket_or_recess_operation` | info | pass | No socket/recess-specific station required |
| `v2_hole_or_internal_thread_operation` | info | pass | Hole/internal-thread feature has a matching piercing/tapping station or note |
| `v2_large_head_staging` | info | pass | Large head/shank ratio 2.23 is split across staged preforming |
| `v2_material_surface_prep` | info | pass | Material/forming difficulty has softening, surface prep, or lubrication note |
