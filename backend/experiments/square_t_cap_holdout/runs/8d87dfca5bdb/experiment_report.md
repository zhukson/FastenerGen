# Experiment Report: square_t_cap_holdout

- Input: `experiments/square_t_cap_holdout/input/part_features.json`
- Output dir: `experiments/square_t_cap_holdout/runs/8d87dfca5bdb`
- Holdout case: `DJGS-25-8-B001-0358-四方T帽-106S-过模图`
- Prefer category: `square_T_head`

## Result

- Part: 四方T头内螺纹嵌件（四方头带十字凹槽）
- Material: 106S
- Stations: 6
- Confidence: medium
- Verification passed: True
- Cited cases: DJGS-22-2-四方通孔-105S-过模图, DJGS-25-5-B144-0056-106S-过模图, DJGS-25-2-B120-0044-YT105S-过模图

## Metrics

| Metric | Value | Pass | Threshold |
|---|---:|---|---:|
| `station_count_error` | 0.000 | yes | 0.0 |
| `operation_sequence_similarity` | 0.500 | no | 0.75 |
| `station_operation_alignment` | 0.500 | no | 0.7 |
| `key_dimension_coverage` | 1.000 | yes | 0.8 |
| `renderer_geometry_readiness` | 1.000 | yes | 0.8 |

## Expected

- Part: 四方T帽
- Stations: 6
- Operations: upsetting, forward_extrusion, heading, combined, trimming, piercing

## Renderer Handoff

FastenerGen emits ProcessForming JSON. FastenerDrawingEngine accepts this base schema and can produce better drawings when stations also include geometry_25d and optional drawing views/tables.

Artifacts:
- `process_parameters.json`: `experiments/square_t_cap_holdout/runs/8d87dfca5bdb/process_parameters.json`
- `design_reasoning.md`: `experiments/square_t_cap_holdout/runs/8d87dfca5bdb/design_reasoning.md`
- `gong_review.md`: `experiments/square_t_cap_holdout/runs/8d87dfca5bdb/gong_review.md`
