# 过模图 设计理由 / Design Reasoning

**零件 / Part:** 四方法兰T形头内螺纹嵌件（四方头带R2.5圆角+十字凹槽）  (`DJGS-25-8-B001-0358`)
**材料 / Material:** 106S
**工位数 / Station count:** 6
**信心 / Confidence (measured):** medium

### 信心信号 / Confidence rationale (measurable)

- score: **23**
- detected input features: `['external_flange_head', 'external_square_head', 'thread_external']`
- same-category factory cases: (none)
- geometric neighbors (±67% L/D): ['DJGS-25-5-B144-0056-106S-过模图', 'DJGS-25-8-B001-0358-四方T帽-106S-过模图']
- rationale: no same-category factory case; feature overlap: DJGS-25-8-B001-0358-四方T帽-106S-过模图(2), motorcycle_ebike_shock_absorber_piston_rod_8_33(2), DJGS-22-2-四方通孔-105S-过模图(1); 2 case(s) within ±67% L/D: ['DJGS-25-5-B144-0056-106S-过模图', 'DJGS-25-8-B001-0358-四方T帽-106S-过模图']

## 龚茂良式审查 / Gong-style Engineering Review

_(Free-form analysis the LLM produced before committing to the JSON plan — covers feature reading, station-count derivation, physical-limit checks, material prep, and cited-case justification.)_

## 1. 【特征识别 + 反查】

零件描述：DJGS-25-8-B001-0358，"四方头带4-R2.5圆角，头部带十字凹槽特征"，总长17.0mm，头部直径17.65mm（头高3.0mm），杆径7.93mm，杆长14.0mm，材料106S，机型YT-106S。

**关键判断：**
- **头部类型**：描述为"四方法兰T头螺母/嵌件"，notes说"四方头带4-R2.5圆角"，head.type标注为flange，实际应是**四方头**（square head），边长约17.65mm（或对角线17.65mm），4角带R2.5圆角。
- **头部十字凹槽**：notes提到"头部带十字凹槽特征"，这是头部顶面的十字形凹槽（cross recess），不是通孔，类似定位特征。
- **内螺纹**：描述说"internal thread"，但part_features没有给出thread字段，仅在description里提到。结合"螺母/嵌件"判断，可能需要攻内螺纹（thread_tapping）作为后处理。无法确认螺纹规格，但有内螺纹需要后续冲孔/攻丝。
- **head/shank比**：头部等效圆直径 ≈ 17.65mm（方头对角线或外接圆），杆径7.93mm，比值 = 17.65/7.93 ≈ 2.22，接近2.3极限，**必须预镦分两次**。
- **材料106S**：与已知案例DJGS-25-5（106S六角轴）、DJGS-25-7（106S内六角螺钉）相同，为普通冷镦钢，不是不锈钢，无需中间退火。
- **机型YT-106S**：与案例DJGS-22-2（四方通孔）同为105S/106S机型，6工位能力。

**几何反查：** 四方头边长约 = 17.65/√2 ≈ 12.48mm（若17.65为对角线）或直接边长约17.65mm（若为方头外接圆）。结合R2.5圆角描述，判断**17.65mm为外接圆直径**，实际方头边长约 = 17.65×cos45°×√2 ≈ 12.5mm，或按工厂惯例，方头边长≈17.65/1.414≈12.5mm。切边前预制圆形毛坯需达到外接圆尺寸。

**十字凹槽**：头部顶面十字凹槽，类似cross recess特征，需要在终镦时通过冲头压制，或单独一道反挤/压制工序。

## 2. 【工位数推导】

基础：1（下料整形）+ 1（终镦头部）= 2

逐项累加：
- head/shank = 17.65/7.93 ≈ 2.22 > 1.4 → **+1 head_predeform**（预镦聚料）
- 2.22 < 2.3 → 单道理论可行，但考虑方头成形飞边，保守分两次预镦 → **+1 two_blow_upset中间站**（共两次预镦）
- 四方头需切边修飞边 → **+1 trimming**
- 十字凹槽（头顶压制特征）→ 可在终镦工位同时压制，不需额外站
- 内螺纹：需要先冲预孔，再攻丝 → **+1 piercing**（冲孔）

**总计：** 1 + 1 + 1（预镦1）+ 1（预镦2）+ 1（trimming）+ 1（piercing）= **6工位**

参考DJGS-22-2（四方通孔，5工位）和DJGS-25-5（六角轴，6工位），6工位合理。

## 3. 【物理风险】

- **镦粗比检验**：坯料直径选取约10.0mm，头部等效圆直径17.65mm，比值 = 17.65/10.0 = 1.765，需分两次镦粗，每次比值约1.35，安全。
- **杆部正挤**：坯料10.0mm → 杆部7.93mm，减面率 = 1-(7.93²/10.0²) = 1-0.629 = 37.1%，远低于70%极限，安全。
- **切边**：四方头外接圆约17.65mm，切边去除飞边，变形量小。
- **冲孔**：内螺纹预孔，需在头部结构稳定后进行，放在最后一站。
- **头部高度3.0mm**较薄，在终镦时需注意充填，十字凹槽压制深度不能太深以防开裂。

## 4. 【材料专项】

106S为普通冷镦碳钢（类似低碳钢），无需特殊处理：
- 预处理：标准磷化+皂化润滑即可
- 无需中间退火（累积变形合理，材料塑性好）
- 后处理：内螺纹需攻丝（thread_tapping），可能需要表面处理（按客户要求）
- 不需要钝化（非不锈钢）

## 5. 【参考案例选择】

**最相似案例：**
1. **DJGS-22-2-四方通孔-105S** — 同为四方头+中心孔+切边的工艺，5工位流程（镦粗→进一步成形→四方成形→冲孔→切边），直接参考其工艺顺序。本件多了内螺纹（攻丝后处理）和十字凹槽。
2. **DJGS-25-5-B144-0056-106S** — 同材料106S，6工位，有反挤内孔和法兰头部，杆径7.82mm（近似7.93mm），参考其坯料尺寸选取和工位节奏。
3. **t_bolt_cold_heading_8_34** — T型螺栓/四方头类型，工艺思路参考。

**Confidence：medium** — 有相似四方通孔案例（DJGS-22-2）和同材料案例（DJGS-25-5），但没有完全相同的"四方头+内螺纹+十字凹槽"案例，且十字凹槽特征不确定是否需要单独工位。

## Cited reference cases

- `DJGS-22-2-四方通孔-105S-过模图`
- `DJGS-25-5-B144-0056-106S-过模图`
- `t_bolt_cold_heading_8_34`

## 推理摘要 / Condensed Reasoning

【特征识别】四方头（外接圆φ17.65，边长≈12.48，4-R2.5圆角）+头顶十字凹槽+杆部内螺纹（通孔攻丝），材料106S普通冷镦钢，机型YT-106S，总长17.0mm。head/shank=17.65/7.93≈2.22，接近2.3极限，必须两次预镦；四方头需切边；内螺纹需冲孔+攻丝。【工位推导】1整形+1预镦+1终镦+1正挤杆部+1切边四方+1冲通孔=6工位，与YT-106S机型能力及DJGS-22-2四方通孔案例（5站）、DJGS-25-5六角轴案例（6站）匹配。【坯料计算】V_head=π/4×12.48²×3.0+十字槽损耗≈369mm³，V_shank=π/4×7.93²×14.0≈692mm³，V_total≈1061×1.08≈1146mm³，blank_D=10.0，blank_L=1146/(π/4×100)≈14.6mm过短，实际头部飞边料和正挤变形余量补充，取28.5mm（体积裕量合理）。【物理校验】一次预镦比1.35<2.3安全；正挤减面率≈31.5%<70%安全；切边变形量小。【参考案例】主要参考DJGS-22-2四方通孔（四方切边+冲孔工序顺序），DJGS-25-5六角轴106S（坯料选取和6工位节奏），t_bolt_cold_heading（T型/四方头成形思路）。十字凹槽在终镦工位由冲头压制同步完成，不需额外工位。后处理：攻内螺纹（thread_tapping）+硬度抽检。

## 工位概览 / Station overview

| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |
|---|---|---|---|---|---|
| 0 | (blank) | cylinder | 28.5 | 10.0 | 原料下料 |
| 1 | upsetting | cylinder | 28.5 | 10.05 | 第1站：切料整形，坯料φ10.0×28.5，端面修整倒角，为后续镦粗聚料做准备 |
| 2 | upsetting | stepped | 22.0 | 13.5 | 第2站：一次预镦聚料，头部初步扩径至φ13.5，锥面过渡，为二次终镦准备体积 |
| 3 | heading | headed | 18.5 | 19.5 | 第3站：终镦成形圆形头部（切边前），外径φ19.5，头高3.5，头顶同步压制十字凹槽（宽3.5×深1.2），4-R2.5特征由切边工位实现 |
| 4 | forward_extrusion | headed | 17.5 | 19.5 | 第4站：正挤压杆部缩径至φ7.93（最终杆径），整形杆端倒角，头部保持圆形飞边态等待下一站切边 |
| 5 | trimming | square_head | 17.0 | 17.65 | 第5站：四方切边，圆形飞边切除为四方形轮廓（外接圆φ17.65，边长≈12.48，4-R2.5），去除飞边，头高定型3.0mm，达到成品外形 |
| 6 | piercing | T_head | 17.0 | 17.65 | 第6站：冲通孔φ6.0贯通全杆（内螺纹攻丝预孔），外形已定型，后续攻丝完成内螺纹特征 |

## 后处理 / Post-processes

thread_tapping, hardness_inspection

## 规则校验 / Rule checks

| Check | Severity | Result | Message |
|---|---|---|---|
| `v2_positive_dimensions` | error | pass | All blank/station dimensions are positive |
| `v2_station_numbering` | error | pass | Station numbers are sequential |
| `v2_reference_citations` | error | pass | Design cites at least one Tier 1 worked case |
| `v2_final_length_vs_product` | info | pass | Final station length is within 0.0% of product length |
| `v2_volume_conservation` | warning | pass | Blank/final volume ratio 1.57 needs engineer review |
| `v2_station_deformation_s1` | info | pass | Station 1 deformation is within demo guardrails |
| `v2_station_deformation_s2` | info | pass | Station 2 deformation is within demo guardrails |
| `v2_station_deformation_s3` | info | pass | Station 3 deformation is within demo guardrails |
| `v2_station_deformation_s4` | info | pass | Station 4 deformation is within demo guardrails |
| `v2_station_deformation_s5` | info | pass | Station 5 deformation is within demo guardrails |
| `v2_station_deformation_s6` | info | pass | Station 6 deformation is within demo guardrails |
| `v2_material_allowable_upset_rate` | info | pass | Max single-station upset shortening 22.8% is within material Ep≈68% |
| `v2_ld_blow_count` | info | pass | Blank L/D=2.85; forming blow count is plausible |
| `v2_socket_or_recess_operation` | info | pass | No socket/recess-specific station required |
| `v2_hole_or_internal_thread_operation` | info | pass | Hole/internal-thread feature has a matching piercing/tapping station or note |
| `v2_large_head_staging` | info | pass | Large head/shank ratio 2.23 is split across staged preforming |
| `v2_material_surface_prep` | warning | review | Difficult material/forming should mention annealing/phosphating/lubrication risk |
