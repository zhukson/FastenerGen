# Session 9: Prompt + Die Parameter Quality

Read @CLAUDE.md for full project context. Sessions 5–8 must be complete.

## Goal

LLM output passes all verification checks on the first attempt ≥ 80% of the time. Die dimensions are proportionally correct for the input part. Process plans show the right station count and the arithmetic is visible in the reasoning. No more obviously wrong proportions (die OD < 2× bore, punch larger than head cavity, etc.).

---

## Task 1: Process Planning Prompt Improvements

### File: `backend/app/ai/prompts/process_planning.py`

### 1a: Add chain-of-thought arithmetic instruction

Add a `<required_thinking>` block at the end of PP_USER_TEMPLATE that tells the LLM to compute before outputting JSON:

```
<required_thinking>
Before outputting JSON, compute in a <thinking> block (will be stripped from output):

1. Part volume:
   V_shank = π/4 × shank_diameter² × shank_length = ?
   V_head  = π/4 × head_diameter²  × head_height  = ?
   V_total = V_shank + V_head = ? mm³

2. Blank wire diameter selection:
   - d_blank must be ≥ shank_diameter (wire cannot be smaller than shank)
   - d_blank should be ≤ shank_diameter × 1.12 (avoid excessive extrusion)
   - Choose from standard wire sizes: 4.0, 4.5, 5.0, 5.5, 5.8, 6.0, 6.2, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0mm

3. Blank length from volume conservation:
   L_blank = V_total / (π/4 × d_blank²) × 1.02 (2% flash allowance)

4. Max upset ratio per station:
   upset_ratio = head_diameter / d_blank
   - If ≤ 2.3: can be done in 1 heading station
   - If 2.3–3.8: needs 2 heading stations (preform + finish)
   - If > 3.8: consider larger blank wire

5. Station count decision:
   - 1 station if part is simple (upset_ratio ≤ 2.3, no separate extrusion needed)
   - 2 stations for most common bolts (upset + heading)
   - 3 stations if thread blank needs extrusion OR dual-stage heading needed
   - 4 stations for complex geometry (knurl section + separate extrusion + heading)
</required_thinking>
```

### 1b: Reorder template — part first, then examples

Move `{similar_cases}` to AFTER the part description and thinking instruction. Current order puts examples first, which biases the LLM toward copying the example rather than reasoning from the part. New order:

```
<new_part>
{features_json}
</new_part>

<retrieval_quality>{retrieval_quality}</retrieval_quality>

<required_thinking>
... (as above)
</required_thinking>

{similar_cases}

<instruction>
Now output the ProcessPlan JSON...
</instruction>
```

### 1c: Add explicit volume conservation constraint

In the `<instruction>` block, add:
```
CONSTRAINT: blank_diameter × blank_length must satisfy:
  π/4 × blank_diameter² × blank_length ≥ V_total × 0.97
  (volume conservation within 3%, remainder is flash)

If your values violate this, revise before outputting JSON.
```

---

## Task 2: Die Design Prompt — Computed Constraint Injection

### File: `backend/app/ai/prompts/die_design.py`

### 2a: Add computed constraint variables to template

The template currently has general rules ("die OD: 2.5–4× bore"). Replace with part-specific computed values injected at call time:

```python
DD_USER_TEMPLATE = """\
<part>
{features_json}
</part>

<process_plan>
{process_plan_json}
</process_plan>

<dimension_constraints>
Computed from this specific part — use these EXACT values as your starting point:
  blank_wire_diameter:     {blank_dia:.2f} mm
  shank_guide_bore_id:     {bore_id:.3f} mm  (blank × 1.008, clearance fit)
  die_body_od_range:       {die_od_lo:.1f}–{die_od_hi:.1f} mm  (bore × 2.8–3.5)
  heading_punch_od:        {punch_od_heading:.3f} mm  (head_dia × 0.990)
  extrusion_punch_od:      {punch_od_ext:.3f} mm  (shank_dia × 1.002)
  min_working_length:      {min_working_length:.1f} mm  (overall_length × 1.10)
  max_working_length:      {max_working_length:.1f} mm  (overall_length × 1.40)
  clearance_each_side:     {clearance:.3f} mm  (shank_dia × 0.0025)
  die_hardness_min_hrc:    {die_hrc_min} HRC  (workpiece HRC + 20 minimum)
</dimension_constraints>

{similar_die_specs}

<task>
...existing task description...
{schema_json}
</task>
"""
```

### 2b: Inject computed values in `_calc_die_params()`

### File: `backend/app/ai/designer.py`

In `_calc_die_params()`, compute the constraint values before formatting the template:

```python
nom = part.thread.nominal_diameter
blank_dia = plan.blank_diameter
bore_id = blank_dia * 1.008
die_od_lo = bore_id * 2.8
die_od_hi = bore_id * 3.5
punch_od_heading = part.head.diameter * 0.990
punch_od_ext = part.shank.diameter * 1.002
min_wl = part.overall_length * 1.10
max_wl = part.overall_length * 1.40
clearance = part.shank.diameter * 0.0025

# Workpiece HRC lookup for minimum die hardness
_WORKPIECE_HRC = {
    "C1008": 15, "C1010": 15, "10B21": 18,
    "SCM435": 22, "SCM440": 28, "SUS304": 20,
}
wp_hrc = _WORKPIECE_HRC.get(part.material_grade.upper(), 20)
die_hrc_min = wp_hrc + 20

user_msg = DD_USER_TEMPLATE.format(
    features_json=part.model_dump_json(indent=2),
    process_plan_json=plan.model_dump_json(indent=2),
    similar_die_specs=fewshot_xml,
    station_count=plan.total_stations,
    schema_json=json.dumps(_DIE_PARAMETERS_SCHEMA, indent=2),
    blank_dia=blank_dia,
    bore_id=bore_id,
    die_od_lo=die_od_lo,
    die_od_hi=die_od_hi,
    punch_od_heading=punch_od_heading,
    punch_od_ext=punch_od_ext,
    min_working_length=min_wl,
    max_working_length=max_wl,
    clearance=clearance,
    die_hrc_min=die_hrc_min,
)
```

---

## Task 3: Stricter Verification Rules

### File: `backend/app/ai/verification.py`

Add 4 new checks to `DesignVerifier.verify()`:

**Check: die_od_ratio**
```python
for die_param in die_params:
    if die_param.die.inner_diameter and die_param.die.outer_diameter:
        ratio = die_param.die.outer_diameter / die_param.die.inner_diameter
        if ratio < 2.5:
            checks.append(RuleCheck(
                check_name="die_od_ratio",
                passed=False,
                message=f"Station {die_param.station_number} die OD/bore ratio {ratio:.2f} < 2.5 (structurally unsafe)",
                actual_value=f"{ratio:.2f}",
                expected_range="≥ 2.5",
            ))
```

**Check: heading_punch_fits_cavity**
```python
for die_param in die_params:
    if die_param.punch.geometry_type in ("conical", "closed_heading"):
        punch_od = die_param.punch.outer_diameter
        head_dia = part.head.diameter
        if punch_od > head_dia * 1.02:
            checks.append(RuleCheck(
                check_name="heading_punch_fits_cavity",
                passed=False,
                message=f"Station {die_param.station_number} punch OD {punch_od}mm > head_dia {head_dia}mm — punch won't fit in die cavity",
                actual_value=f"{punch_od:.2f}mm",
                expected_range=f"≤ {head_dia * 1.02:.2f}mm",
            ))
```

**Check: working_length_sufficient**
```python
for die_param in die_params:
    min_len = part.overall_length * 0.8
    if die_param.die.working_length < min_len:
        checks.append(RuleCheck(
            check_name="working_length_sufficient",
            passed=False,
            message=f"Station {die_param.station_number} die length {die_param.die.working_length}mm < minimum {min_len:.1f}mm",
        ))
```

**Check: clearance_in_range**
```python
for die_param in die_params:
    if die_param.clearance_mm is not None:
        if die_param.clearance_mm < 0.005 or die_param.clearance_mm > 0.05:
            checks.append(RuleCheck(
                check_name="clearance_in_range",
                passed=False,
                message=f"Station {die_param.station_number} clearance {die_param.clearance_mm:.3f}mm out of range [0.005, 0.050]",
            ))
```

### Retry context improvement

In `designer.design()`, when verification fails and a retry is triggered, pass the specific failed checks with expected values back to the LLM:

```python
if not verif.passed:
    failed_details = "\n".join([
        f"  - {c.check_name}: {c.message} (expected: {c.expected_range}, got: {c.actual_value})"
        for c in verif.checks if not c.passed
    ])
    retry_context = f"\n<verification_failures>\n{failed_details}\n</verification_failures>\n"
    fewshot_xml = retry_context + fewshot_xml  # prepend to next LLM call
```

---

## Task 4: Switch Die Design to Sonnet for Speed

### File: `backend/app/ai/designer.py`

Process planning stays on Claude Opus 4.7 (hard reasoning). Die parameter calculation is schema-following with computed constraints — use Claude Sonnet 4.6 which is 5× faster and 5× cheaper:

```python
# In _calc_die_params():
response = await self._client.messages.create(
    model="claude-sonnet-4-6",  # was primary_model (Opus)
    max_tokens=4096,
    system=DD_SYSTEM,
    messages=[{"role": "user", "content": user_msg}],
)
```

Add `claude_model_die_design: str = "claude-sonnet-4-6"` to `settings` in `config.py`.

---

## Task 5: Batch Quality Test

### File: `backend/tests/test_parameter_quality.py` (new)

Run 20 M6 synthetic designs and measure quality:

```python
@pytest.mark.asyncio
async def test_die_parameter_quality_m6():
    gen = SyntheticDataGenerator(seed=0)
    results = []
    for i in range(20):
        part, plan, _ = gen.generate_product_die_pair()
        if part.thread.nominal_diameter != 6.0:
            continue
        # Mock LLM and run through verification only
        verifier = DesignVerifier()
        dies = gen.generate_die_parameters(part, plan)
        result = verifier.verify(part, plan, dies)
        results.append(result)

    pass_rate = sum(1 for r in results if r.passed) / len(results)
    assert pass_rate >= 0.80, f"Pass rate {pass_rate:.0%} below 80% target"

    die_od_ratios = [
        dp.die.outer_diameter / dp.die.inner_diameter
        for r_dies in [gen.generate_die_parameters(*gen.generate_product_die_pair()[:2]) for _ in range(10)]
        for dp in r_dies
        if dp.die.inner_diameter
    ]
    assert all(r >= 2.5 for r in die_od_ratios), "Die OD ratio below 2.5"
```

---

## Acceptance Criteria

- [ ] Run 20 M6 designs: ≥ 16/20 pass all verification checks on first attempt
- [ ] Die OD is always in range 2.5–3.5× bore for generated cases
- [ ] Process plan reasoning in `DesignResult.reasoning_summary` mentions the actual upset ratio value
- [ ] Retry count ≤ 1 for ≥ 90% of cases (check `verification_result.attempt` in logs)
- [ ] Die design LLM call latency drops by ≥ 40% (Sonnet vs Opus)
- [ ] `test_parameter_quality.py` passes

## Files Modified
- `backend/app/ai/prompts/process_planning.py`
- `backend/app/ai/prompts/die_design.py`
- `backend/app/ai/designer.py` (inject computed constraints, switch Sonnet for die design)
- `backend/app/ai/verification.py` (4 new checks, better retry context)
- `backend/app/core/config.py` (add `claude_model_die_design`)
- `backend/tests/test_parameter_quality.py` (new)
