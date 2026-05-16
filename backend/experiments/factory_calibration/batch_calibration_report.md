# Calibration Summary: factory_calibration_completed_predictions

- Cases: `1`

## Metric Means

| Metric | Value |
|---|---:|
| `key_dimension_coverage_mean` | 1.000 |
| `key_dimension_coverage_pass_rate` | 1.000 |
| `operation_sequence_similarity_mean` | 0.333 |
| `operation_sequence_similarity_pass_rate` | 0.000 |
| `precedence_constraint_recall_mean` | 0.200 |
| `precedence_constraint_recall_pass_rate` | 0.000 |
| `renderer_geometry_readiness_mean` | 1.000 |
| `renderer_geometry_readiness_pass_rate` | 1.000 |
| `required_operation_recall_mean` | 0.833 |
| `required_operation_recall_pass_rate` | 0.000 |
| `station_count_error_mean` | 0.000 |
| `station_count_error_pass_rate` | 1.000 |
| `station_operation_alignment_mean` | 0.333 |
| `station_operation_alignment_pass_rate` | 0.000 |

## Failure Tags

| Tag | Count |
|---|---:|
| `missing_required_operation` | 1 |
| `station_alignment_error` | 1 |
| `wrong_operation_sequence` | 1 |
| `wrong_precedence` | 1 |

## Case Notes

| Case | Failure Tags | Metric Notes |
|---|---|---|
| DJGS-25-8-B001-0358-四方T帽-106S-过模图 | `missing_required_operation`, `station_alignment_error`, `wrong_operation_sequence`, `wrong_precedence` | missing: forward_extrusion; violated: upsetting before forward_extrusion, forward_extrusion before heading, heading before combined, trimming before piercing |
