# Cold-Heading Rules Extracted from Pages 51–56

## Provenance
- **Source:** 工毛亮 (Gong Maoliang) textbook, pages 51–56
- **Document type:** Chinese fastener cold-heading technical appendices
- **Trust level:** Textbook reference—lower confidence than factory process data

---

## Appendix 3: Taiwan Precision Machine Screw Thread-Forming Spec (Pages 51–52)

### Standards Covered
- **UNF Machine Screw 2A** (60° FF)
- **UNC Machine Screw 2A** (60° HF)
- **BA Machine Screw** (Z75°)
- **SM Machine Screw** (spindle screw spec)
- **BSW Machine Screw 2A** (35°)

### Key Numeric Thresholds
Tables list MAX/MIN dimensions for:
- Head diameter (Dmax, Dmin)
- Head height (Hmax, Hmin)
- Thread pitches (P)

**⚠️ OCR quality poor; exact values unreliable.** Table structure recognizable but cell values corrupted in OCR.

### FastenerGPT Use (Step 3)
- Reference when user specifies **UNF, UNC, BA, or BSW screw type**
- Cross-check thread pitch and head geometry against spec table
- Flag if dimensions fall outside MAX/MIN range

---

## Appendix 4: Pre-Tapping Hole Diameter (Internal Thread) (Page 53)

### Key Rule
**Thread tooth height target:**
- Nominal: **70%–85%** of theoretical thread height (牙型高度一般取70%一85%)

### FastiberGPT Use (Step 3)
- When calculating tap-hole diameter for **internal thread cold-forming**
- Apply 70%–85% tooth engagement to determine minimum hole size
- Prevents over-forming; manages tap torque

---

## Appendix 5: Tap Hole Diameter Table (Page 54)

### Structure
Two-column format with **metric thread specifications** and hole diameters (取偏大值 = "take larger value")

**Examples (OCR confidence low):**
| Thread | Hole Ø (approx.) |
|--------|------------------|
| M3 × 0.5 | ~2.4 mm |
| M4 × 0.7 | ~3.3 mm |
| M5 × 0.8 | ~4.2 mm |
| M6 × 1.0 | ~5.0 mm |

**⚠️ Many entries garbled; use only if OCR and image align.**

### FastenerGPT Use (Step 3)
- Reference for **metric tap-hole selection** before cold thread-forming
- Use "larger value" convention to reduce forming stress
- Cross-check against Appendix 4 (70%–85% rule)

---

## Appendix 6 & 7: Carbon Steel Hardness–Strength Conversion (Pages 55–56)

### Standards
- **Appendix 6:** Japan SAE J417-1983
- **Appendix 7:** GB/T1172-1999 (PRC standard)

### Conversion Scales
Both tables provide **bidirectional lookup:**
- **HB** (Brinell hardness, 10 mm ball, various loads)
- **HRA, HRC, HRD** (Rockwell scales)
- **HV** (Vickers microhardness)
- **TS** (Tensile strength, MPa)

### Key Numeric Ranges (GB/T1172-1999)
- Hardness range: ~60–100 HRC (approx.)
- Tensile strength: ~500–800 MPa (carbon steel typical)
- Relationship: **Higher HRC → Higher TS** (non-linear)

### Critical Formula
**1 MPa = 1 N/mm² = 1/9.80665 kgf/mm²**

### FastenerGPT Use (Step 3)
- **Material specification checking:** User states hardness → convert to tensile strength
- **Process capability:** Cold-heading limits depend on material strength
  - Soft stock (< 50 HRC): easier forming, multiple stations
  - Hard stock (> 70 HRC): limited forming, shorter dwell, higher press force
- **Friction/lubrication:** Correlate hardness to workability
- **Example:** If M6 screw requires ≥ 400 MPa tensile, use conversion table to find minimum HRC

---

## Station-Sequence Rules (Inferred from Appendix Context)

Although individual station sequences are not explicitly listed in OCR text, typical cold-heading workflow for **metric threads:**

1. **Upset/Form head** → diameter constraint from Appendix 3
2. **Forward extrude** → control length, form shank
3. **Trim/Point** → cut to length
4. **Cold roll thread** → use Appendix 5 hole diameter + Appendix 4 (70%–85% engagement)
5. **Stress relieve** (optional) → if hardness exceeds material spec

---

## Uncertainty & Limitations

| Item | Confidence | Note |
|------|-----------|------|
| Appendix 3 (screw specs) | **Low** | OCR table severely corrupted; only structure visible |
| Appendix 4 (tooth height rule) | **Medium** | Clear text; 70%–85% rule stated once |
| Appendix 5 (tap hole ∅) | **Low** | Many cells illegible; use only for orientation |
| Appendix 6 & 7 (hardness–strength) | **Medium** | Table structure legible; some numeric cells corrupted; formulas clear |

---

## Summary for FastenerGPT Integration

**Step 3 Logic:**
1. **User provides:** Material hardness (HB/HRC) or tensile strength (MPa)
2. **Query Appendix 6 or 7:** Convert to complementary property
3. **Assess cold-formability:** Higher strength = reduced forming window, more stations needed
4. **If internal thread:** Apply Appendix 4 (70%–85%) + Appendix 5 table to select tap-hole diameter
5. **If screw head geometry critical:** Cross-check Appendix 3 (with caveat on OCR quality)

**Recommendation:** Substitute factory process data for Appendix 3 when available; use hardness–strength conversion tables as secondary validation.
