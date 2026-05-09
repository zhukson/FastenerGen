# Cold-Heading Knowledge Extraction: Pages 39–44

## Document Provenance
- **Source:** 冷镦技术及应用 (Cold-Heading Technology & Application)
- **Section:** Chapter 5 — Automatic Cold-Heading Machine Types & Parameters
- **Pages:** 39–44 (Gong, Maoliang textbook)
- **Focus:** Die design, machine type nomenclature, and main parameters for cold-heading fasteners

---

## Key Formulas & Numeric Thresholds

### Forming Force Calculation (Page 39)
**Formula:**
$$P_c = v \cdot 2O_s \left( 1 + \frac{Hf}{3ad/h} \right) \cdot F = 1 \times 1970 \times (10.08/3 + 18/4.9) \times 40.785 \times 18^2$$

**Result:** $P_c = 19,548\text{ kgf}$  
**Material:** 40Cr; heat-treated; ball-pressed; HB800-87 ✓  
**Cold-heading capacity:** 61,591 kgf (GJB/F83-84 standard forming force); 65,000 kgf  
*[Uncertainty: OCR degradation on some coefficients; verify against original diagram]*

### Hex-Bolt Thread Pitch Standard References (GB/T 5789, GB/T 5780)
- Standard series: M5–M42 (common industrial range)
- **Hex across-flats to diameter rule:**  
  $$d_{\text{across-corner}} = 1.155 \times d_{\text{across-flat}} + (2\text{ to }10)\text{ mm}$$

### Typical M-Size & Max Upsetting Dimensions (Page 39 Table)
| Size | M5 | M6 | M8 | M12 | M16 |
|------|----|----|----|----|-----|
| **C (MIN)** | 1.0 | 1.1 | 1.2 | 1.8 | 2.6 |
| **d_c (MAX)** | 11.8 | 14.2 | 18 | 26.6 | 35 |
| **d_s (MAX)** | 5 | 6 | 8 | 12 | 16 |
| **S (HEAD DIMENSION)** | 7.64 | 9.64 | 12.57 | 17.57 | 23.16 |

*[Note: Numeric confidence medium; cross-reference against GB/T standards]*

---

## Station Sequence & Die Design Rules

### Three-Part Punch Design (Page 41: 印芯卸铲长轴工艺变形图)
**Die configurations shown for stations 0#, 1#, 2#, 3#:**

- **Station 0#** (Blank/Reference):  
  L = 108.07 mm; cylindrical length only

- **Station 1#** (Initial form):  
  - Total length: 115 mm  
  - Working section: 104.6 mm  
  - Lead-in taper: 30° angle; R4.5 radius  
  - Hex forming begins; ⌀6 spec  
  - ✓ **Rule:** Taper lead ≥ 30° to ensure smooth entry

- **Station 2#** (Intermediate form):  
  - Length: 107 mm  
  - Cylindrical body: 96.7 mm  
  - Shoulder section: 25 mm  
  - ⌀5.5 final diameter  
  - Radius blend R4.5 (9.6–5.5 transition)  
  - ✓ **Rule:** Intermediate steps reduce draft & stress

- **Station 3#** (Final form):  
  - Length: 100 mm  
  - Tapered exit: 45° angle  
  - R3.3 & R0.8 blends  
  - Final ⌀4.4 neck  
  - ✓ **Rule:** Steep final draft (45°) for ejection; fine radii for thread run-off

### Advanced Punch Geometry (Page 42: 印芯卸铲长轴工艺变形图 2)
**Stations 4#–6# (higher-precision or multi-feature fasteners):**

- **Station 4#:**  
  - Complex form with chamfer & transitional blends  
  - R0.2 and R1.3 micro-radii (for stress concentration reduction)  
  - Datum R1–R2 control (±0.03 mm tolerance on shoulder)

- **Station 5#:**  
  - Longer shank (75.9 mm); smaller cross-section  
  - ⌀9.81 & ⌀6.46 steps; final ⌀5.65, ⌀4.32  
  - ✓ **Rule:** Intermediate diameter steps must be ≥ 0.5 mm to avoid stick-slip

- **Station 6#:**  
  - Final precision form: N=0.7 mm draft  
  - R1–R2 controlled blend  
  - ⌀9.84±0.03 mm critical tolerance  
  - ✓ **Rule:** Ultra-fine draft (N<1 mm) for final thread/geometry lock-in

---

## Machine Type Nomenclature Rules (Page 43–44)

### Chinese Nomenclature Standard: **Z-Series** (前缘Z型)
**Format:** `Z{stages}/{positions}` + Optional letter suffix

- **Z46–6/4** = M6 hex bolt; 4-stage (模) × 4-cavity (冲) machine
- **Z47-N** = Multi-position spiral-rolling combined machine
- **Z41-M** = Multi-position thread-rolling machine  
- **Rule:** Digit 1 = family code; Digits 2–3 = metric size; `/positions` = cavities per stage

### Taiwan/Overseas Nomenclature: **BF-, NF-, BP-series**
- **BF:** Multi-position bolt forming machine
- **NF:** Multi-position nut forming machine
- **BP:** (≥5 positions) compound forming machine
- **Example:** `SJBP-136L` = Siju (思进) M12 hex; 6-stage × 6-cavity; **L** = extended length type

### US Nomenclature: **PumaFX, LeanFX**
- **PumaFX-146M:** medium-size, 6-stage × 6-cavity, high-speed standard type
- **PumaFX-145CF:** medium-size, 5-stage × 5-cavity, special compound forming
- **Rule:** Name-M = standard; -CF = compound; -L = long; -LL = extra-long

---

## Main Machine Parameters (Page 44: §5.2)

### 1. **Maximum Forming Force** (紧国件尺寸)
- Sized per **GB/T 5789** (hex flanged) or **GB/T 5780** (hex head)
- Sum of all stage forming pressures + safety factor (1.2–1.5×)
- Common M-sizes and minimum machine capacity:
  - M5–M8: 8B class (e.g., M8-13B = 13 mm across-flats)
  - M24–M42: 36B–65B class
- ✓ **Rule:** Never undersize machine for large-diameter stock; can use oversized machine for smaller sizes (±2 grade margin only)

### 2. **Maximum Cut-Off Diameter**
- General rule: 2 mm larger than design specification
- Allows for bar-feed stock tolerance

### 3. **Blank-Eject Stroke** (推出行程 K.O.)
- Determined by largest part length and die geometry
- Defines cycle time

### 4. **Die-Cavity Stroke** (上下模推出行程 P.K.O.)
- Controls shank diameter, thread run-off length, punch-travel depth
- **Critical for:** Pitch-forming precision & ejection angle (typically 30°–45°)

### 5. **Number of Stages** (模数)
- Directly from **die process plan** (工艺变形图)
- Common: 2-stage, 3-stage, 4-stage, 6-stage (higher = finer quality, slower cycle)

### 6. **Production Rate** (生产率)
- Function of:
  - Die allowable speed (工艺允许速率)
  - Machine transmission stiffness & precision (RA-rated)
  - Material ductility (热处理)
- **Rule:** Softer materials & finer geometry = lower RPM

### 7. **Material & Heat Treatment**
- 40Cr standard; HB 800–87 (temper state)
- Verify tradeoff: hardness ↔ die life ↔ cycle cost

---

## Application Rules for FastenerGPT Step 3 (Die-Design Advisor)

1. **Input:** Metric size (M5–M42), fastener type (bolt/nut/stud), head geometry  
2. **Lookup:** Match against table (Page 39); confirm GB/T standard  
3. **Estimate forming force:**  
   - Use formula (or look up standard reference table)  
   - Select machine class ≥ 1.2× calculated force  
4. **Stage count:**  
   - Cold-heading ≥2 stages; precision hex ≥4 stages  
   - Refer to published die designs (Pages 41–42 examples)  
5. **Punch taper angles:**  
   - Lead-in: 30°; intermediate: 25°–35°; final exit: 40°–50°  
6. **Blend radii:**  
   - Coarse stages: R2–4 mm; final stage: R0.2–0.8 mm  
   - Avoid sharp corners (stress concentration)  
7. **Machine type selection:**  
   - Cross-reference nomenclature (Z/BF/NF/Puma codes) against capacity & geometry

---

## Uncertainty Notes

| Item | Confidence | Reason |
|------|-----------|--------|
| Forming force formula coefficients | **Medium** | OCR noise on exponents & fractions |
| Hex-across-flats lookup table | **High** | Standard GB/T values; cross-readable |
| Punch geometry (Pages 41–42) | **Medium–High** | Image clarity good; minor dimension uncertainty on micro-radii |
| Machine nomenclature rules | **High** | Text section (p. 43–44) well-preserved |
| Production rate guidelines | **Low** | Only qualitative; no numeric formula given in source |

---

## References
- **Company:** Siju Intelligent (思进智能) — SJBP-305L, SJBP-136L machines  
- **Standards:** GB/T 5789, GB/T 5780  
- **Competitors mentioned:** US (National, PumaFX/LeanFX), Taiwan (CBF, JNF), Korea, Europe
