# Cold-Heading Rules Extraction
## Source: gong_maoliang_Page45_50 (Pages 45–50)

---

## 1. SI Units & Conversion (Pages 46–47)
**Provenance:** Appendix 1 – International System of Units (SI)

### Key numeric conversions for pressure, force, viscosity:
- **Force:** 1 kgf = 9.80665 N; 1 lbf = 4.44822 N
- **Pressure:** 1 MPa = 1 N/mm²; 1 Pa = 1 N/m²
- **Viscosity:** 1 cP = 1 mPa·s; 1 St = 1 cm²/s

### SI Prefixes (for material/process parameters):
| Multiple | Symbol | Multiple | Symbol |
|----------|--------|----------|--------|
| 10⁹      | G (giga)     | 10⁻³     | m (milli) |
| 10⁶      | M (mega)     | 10⁻⁶     | μ (micro) |
| 10³      | k (kilo)     | 10⁻⁹     | n (nano)  |

**FastenerGPT Use:** Normalize all process pressure, stress, and viscosity inputs/outputs to SI base units (Pa, N, m).

---

## 2. Thread Rolling/Heading Blank Diameter (Pages 48–50)
**Provenance:** Appendix 2 – GB/T 18685–2002 Standard  
**Scope:** Blanks for rolling/thread-rolling common threads (M1–M42) before forming.

### Blank Diameter Calculation Formula:
$$d_0 = \left( \tan(a/2) / \sqrt{3}P \right) \times \left[ 3d_m(d'-d_m) - 2(d_i'-d_i) \right] + (d+d_m)/2$$

**Where:**
- $d$ = thread major diameter (nominal)
- $d_m$ = thread pitch diameter
- $d_i$ = thread minor diameter
- $P$ = pitch
- $a$ = form angle = 60°

### Blank Diameter Limits (Table F3-1):
- **Thread size range:** M1 to M42 (metric)
- **Tolerance grades:** 4H, 6H (per GB/T 197)
- **Table provides upper/lower limits** for each nominal diameter and grade

**Example (from Table F3-1):**
- M10 × 1.5: ~9.3–9.95 mm (varies by tolerance)
- M12 × 1.75: ~11.2–12.0 mm

### Adjustment Rules (§7):
1. **Wire-drawn/ground blanks:** Use Table F3-1 directly
2. **Turned blanks:** Add surface roughness $R_z$ value to Table F3-1 diameter

### Tool Grade Selection (Table F3-2):
Match thread tolerance class to rolling-die or thread-rolling-wheel precision grade per:
- GB/T 972 (thread-rolling wheels)
- GB/T 971 (thread-rolling dies)

**FastenerGPT Use (Step 3):**
- For any thread-rolling cold-heading process:
  1. Look up nominal diameter $d$ and pitch $P$ in Table F3-1
  2. Select blank diameter based on tolerance grade (4H or 6H)
  3. If turned stock: add $R_z$ roughness allowance
  4. Confirm tool grade matches thread tolerance class
  5. Validate formula if custom sizes (M1–M42 range)

---

## 3. Equipment Reference (Page 45)
**Provenance:** Machine model notation  
- **Machine:** Siebr SJBP-137L (7-die, 8-punch extended-part forming machine)

**Uncertainty Note:** OCR quality poor on page 45; equipment-specific process parameters not reliably extracted.

---

## 4. Uncertainty & Limitations

| Issue | Note |
|-------|------|
| **Page 45 OCR** | Machine diagram and process-station sequence unreadable; only equipment model name captured |
| **Table F3-1** | Some cell values difficult to verify against OCR; recommend consulting original PDF for M30–M42 range |
| **Formula derivation** | Standard references (GB/T 192, 193, 196, 197) not fully transcribed; formula valid for full-tooth-form extrusion only |

---

## Summary for FastenerGPT
- **SI conversion tables** → normalize all inputs/outputs  
- **Blank-diameter tables** → primary lookup for thread-rolling prep (M1–M42)  
- **Tool grade mapping** → ensure die/wheel precision matches thread tolerance  
- **Adjustment rule** → account for surface finish on turned blanks  

**Confidence Level:** High for numeric tables and standard references; low for process flow and machine-specific sequences.
