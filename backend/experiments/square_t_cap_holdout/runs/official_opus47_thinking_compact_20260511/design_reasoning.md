# 过模图 设计理由 / Design Reasoning

**零件 / Part:** 四方法兰T头内螺纹嵌件  (`DJGS-25-8-B001-0358`)
**材料 / Material:** 106S
**工位数 / Station count:** 6
**信心 / Confidence (measured):** medium
**LLM self-reported confidence:** high (overridden by measured neighbor density)

### 信心信号 / Confidence rationale (measurable)

- score: **19**
- detected input features: `['external_flange_head', 'external_square_head', 'thread_external']`
- same-category factory cases: (none)
- geometric neighbors (±67% L/D): ['DJGS-25-5-B144-0056-106S-过模图']
- rationale: no same-category factory case; feature overlap: motorcycle_ebike_shock_absorber_piston_rod_8_33(2), DJGS-22-2-四方通孔-105S-过模图(1), DJGS-24-6-冲铆轴销-YT105S-过模图(1); 1 case(s) within ±67% L/D: ['DJGS-25-5-B144-0056-106S-过模图']

## 龚茂良式审查 / Gong-style Engineering Review

_(Free-form analysis the LLM produced before committing to the JSON plan — covers feature reading, station-count derivation, physical-limit checks, material prep, and cited-case justification.)_

1. 【特征识别 + 反查】
零件描述为"方形T头+内螺纹"(类似T形螺母/嵌件)：头部直径17.65、高3、四角R2.5 → 这是四方头**对角距**(e),则四方对边距 a ≈ 17.65/√2 ≈ 12.48mm,带4个R2.5倒圆。头部"十字凹槽"是装配定位/驱动用反挤特征。杆部D7.93×L14为带内螺纹的实心套筒(给后续攻丝/滚内牙的预孔)。所以最终件含: ①方形法兰头(需切边) ②头顶十字凹(反挤) ③通孔(冲孔) ④后工序攻丝。Vision 标记 drive_type=none 与十字槽矛盾,实际十字槽是反挤特征而非螺丝刀槽,不冲突。材料 106S = 工厂代号冷镦碳钢,按常规磷皂化路线。

2. 【工位数推导】不查表:
- base = 1(切料) + 1(终镦头部) = 2
- head/shank = 17.65/7.93 = 2.23,接近单道极限2.3 → +1 head_predeform
- 十字凹反挤 → +1 backward_extrusion
- 内螺纹底孔通孔 → +1 piercing
- 方头需切边(方变R角四方) → +1 trimming
- 杆段无减径,不加 forward_extrusion
- stations = 2 + 4 = **6 站** ✓

3. 【物理风险】
- D比 2.23 单道极限边缘 → 必须分两道镦粗(S2聚料→S3终镦),不一次冲到2.23
- 反挤十字槽很浅(深≈1mm,D≈3.5mm),深径比≪4,安全
- 冲通孔 D4.2 (M5底孔预估)穿透14mm壁厚,深径比≈3.3,圆孔极限6,安全
- 切边后4-R2.5方头几何与 DJGS-22-2 四方通孔 (10×10/4-R1.5) 同族
- blank L/D = 19.5/8.0 ≈ 2.44 < 2.8,首站镦粗稳定

4. 【材料专项】106S 工厂代号冷镦碳钢 → 球化退火来料 + 磷化 + 皂化润滑。无强度等级标注,不强制热处理。内螺纹后处理需 thread_tapping(冷镦无法直接成形内牙)。无表面镀层要求。

5. 【参考案例选择】最相似:**DJGS-22-2-四方通孔-105S-过模图**(四方法兰+通孔+R角切边,同族同材料级,5站序为 镦聚料→镦圆+反挤→镦四方+反挤孔→冲孔→切边)。本件多一个十字凹反挤特征,因此在其基础上拆出独立的预镦站 → 6站。另外参考 DJGS-25-5-B144-0056(同 106S,头部反挤+冲孔)证明工艺路线可行。Confidence = **high**(同材料、同特征族、同尺寸量级)。

## Cited reference cases

- `DJGS-22-2-四方通孔-105S-过模图`
- `DJGS-25-5-B144-0056-106S-过模图`
- `DJGS-24-6-冲铆轴销-YT105S-过模图`

## 推理摘要 / Condensed Reasoning

本件为四方法兰T头+内螺纹嵌件，头部对角17.65(对边12.48,4-R2.5)+头顶十字凹+通孔(M5内螺纹底孔)。head/shank=2.23 接近单道镦粗极限，须拆为预镦(S2,D比1.7)+终镦(S3,D比1.35)两道。S4 同时反挤头顶十字凹和杆下端冲孔盲孔，S5 冲通孔(深径比≈4，<圆孔极限6)，S6 切四方边R2.5得到最终外形。共6站。主要参考 DJGS-22-2-四方通孔-105S 同族案例(同4方法兰+通孔+R角切边)的5站序，并因多一个十字凹反挤特征拆出独立预镦站。材料 106S 按碳冷镦钢处理，磷化+皂化润滑，内螺纹后工序攻丝。各站镦粗比与反挤/冲孔深径比均在物理极限内。

## 工位概览 / Station overview

| # | 操作 | 工件几何 | L (mm) | D (mm) | 备注 |
|---|---|---|---|---|---|
| 0 | (blank) | cylinder | 19.5 | 8.0 | 原料下料 |
| 1 | combined | cylinder | 19.5 | 8.0 | 第一站切料并端面整形，为后续聚料做准备 |
| 2 | upsetting | headed | 17.5 | 13.6 | 第二站预镦聚料：head/shank=2.23 接近极限，按 §3 拆分为两道镦粗 |
| 3 | heading | headed | 16.8 | 18.4 | 第三站终镦圆头形成法兰雏形，D比 1.35，符合极限 |
| 4 | combined | headed | 17.0 | 18.4 | 第四站反挤头顶十字凹槽+下端预成形冲孔盲孔，深径比均远小于极限 |
| 5 | piercing | headed | 17.0 | 18.4 | 第五站冲通孔，为后续攻丝 M5 内螺纹做准备 |
| 6 | trimming | T_head | 17.0 | 17.65 | 第六站切边成方头R2.5，得到最终件外形 |

## 后处理 / Post-processes

phosphating, saponification, thread_tapping

## 规则校验 / Rule checks

| Check | Severity | Result | Message |
|---|---|---|---|
| `v2_positive_dimensions` | error | pass | All blank/station dimensions are positive |
| `v2_station_numbering` | error | pass | Station numbers are sequential |
| `v2_reference_citations` | error | pass | Design cites at least one Tier 1 worked case |
| `v2_final_length_vs_product` | info | pass | Final station length is within 0.0% of product length |
| `v2_volume_conservation` | warning | pass | Blank/final volume ratio 0.69 needs engineer review |
| `v2_station_deformation_s1` | info | pass | Station 1 deformation is within demo guardrails |
| `v2_station_deformation_s2` | warning | pass | Station 2 deformation is within demo guardrails |
| `v2_station_deformation_s3` | info | pass | Station 3 deformation is within demo guardrails |
| `v2_station_deformation_s4` | info | pass | Station 4 deformation is within demo guardrails |
| `v2_station_deformation_s5` | info | pass | Station 5 deformation is within demo guardrails |
| `v2_station_deformation_s6` | info | pass | Station 6 deformation is within demo guardrails |
| `v2_material_allowable_upset_rate` | info | pass | Max single-station upset shortening 10.3% is within material Ep≈68% |
| `v2_ld_blow_count` | info | pass | Blank L/D=2.44; forming blow count is plausible |
| `v2_socket_or_recess_operation` | info | pass | No socket/recess-specific station required |
| `v2_hole_or_internal_thread_operation` | info | pass | Hole/internal-thread feature has a matching piercing/tapping station or note |
| `v2_large_head_staging` | info | pass | Large head/shank ratio 2.23 is split across staged preforming |
| `v2_material_surface_prep` | info | pass | Material/forming difficulty has softening, surface prep, or lubrication note |
