# Cold-Heading Rules Extracted from Gong Maoliang Pages 63–68

## Provenance
- **Source:** 《紧固件冷锻技术及应用》(Cold-Heading Fastener Technology and Application)
- **Author:** Gong Maoliang
- **Pages:** 63–68
- **Content:** Surface treatment and lubrication for ferrous/non-ferrous blanks; hex-head bolt process stages (cutting, initial heading, final heading, trimming)

---

## 1. Black Metal (Steel) Blank Surface Treatment

### Phosphating (磷化处理)
**Standard formula:**
- Zinc Phosphate: ZnO 9 g/L
- Iron Phosphate: H₃PO₄ 23 mg/L  
- Accelerator: KMnO₄ 1 L
- **Acid profile:**  
  - Total acidity: 16–20 points  
  - Free acidity: 2.5–4.5 points
- **Conditions:** 85–95 °C, 30–40 min

### Alkaline Oxidation Pre-treatment (碱氧化处理)
- NaOH: 60–100 g/L
- Na₂CO₃: 60–80 g/L
- Na₃PO₄: 25–80 g/L
- Na₂SiO₃: 10–15 g/L
- **Conditions:** >85 °C, 15–25 min

### Pickling (酸洗)
- H₂SO₄: 120–180 g/L
- NaCl: 8–10 g/L
- **Conditions:** 65–75 °C, 5–10 min

### Neutralization (中和处理)
- Use dilute NaOH to neutralize acid residue on phosphate film
- Prevents acid damage to lubricant

---

## 2. Austenitic Stainless Steel (1Cr18Ni9Ti) Surface Treatment

**Cannot use phosphating** (does not chemically react with phosphate base).

### Oxalic Acid + Oxalate Salts Treatment (草酸盐处理)
**Formula (per 1 L):**
- Oxalic acid: H₂C₂O₄ 50 g
- Ammonium molybdate: (NH₄)₆Mo₇O₂₄ 30 g
- Sodium oxalate: Na₂C₂O₄ 25 g
- Sodium fluoride: NaHF₂ 10 g
- Sodium sulfite: Na₂SO₃ 3 g
- **Pickling time:** ~5 min; then hot-water rinse before oxalate treatment

---

## 3. Colored Metal (Aluminum) Blank Surface Treatment

**Alloys:** 2A11(LY11), 2A12(LY12)

**Goal:** Form oxidation or phosphate film (~porous, dense) to reduce cracking during extrusion and hold lubricant.

### Oxidation Treatment (氧化处理)
1. Gasoline wash (oil removal)
2. Hot-water wash: 60–100 °C
3. Cold running-water rinse
4. **Pickling:** Industrial HNO₃ 400–800 g/L, 2 min
5. Cold-water rinse (2×)
6. **Alkaline oxidation:** NaOH 40–60 g/L, 50–70 °C, 1–4 min  
   *(Target: uniform fine-pore gray-black crystalline film)*
7. Hot running-water rinse

### Phosphating for Aluminum (确化处理)
**Formula:**
- Zinc phosphate: Zn(H₂PO₄)₂ 28 g
- Iron (75% solution): 25 g
- CrO₃: 10 g
- Wetting agent: 0.58 g
- Water: 1 L
- **Conditions:** 55–60 °C, 2–3 min

---

## 4. Pure Copper & Brass (黄铜) Passivation

### Passivation Treatment (钝化处理)
1. Gasoline wash
2. Hot-water wash: 60–100 °C
3. Cold-water rinse (2×)
4. *[Step illegible in OCR]*
5. Cold-water rinse
6. Dry

**Passivant formula:**
- HAF (likely nitric acid compound): 200–250 g/L
- H₂SO₄: 8–16 g/L
- Inhibitor: 30–50 g/L
- **Conditions:** 20 °C, 5–10 s

---

## 5. Lubrication Treatment (润滑处理)

### Black Metal Post-Treatment
After phosphating, use **saponification:**
- **Formula 1:** Sodium stearate (C₁₇H₃₅COONa) 5–9 g/L, water 1 L, 60–70 °C, 10 min
- **Formula 2:** Industrial rapeseed oil (MSE 84%) 200–220 g/L, water 1 L, 50–70 °C
- **Alternative:** Lard or machine oil + MoS₂ (molybdenum disulfide)

### Non-Ferrous Metal Lubrication
See **Table F12-1** (OCR damaged but indicates multiple methods):
- Oil + MoS₂ combinations
- Stearic acid coatings
- Saponified oils adjusted for temperature

---

## 6. Hex-Head Bolt (M6×10) Process Stages

### Stage 0 (Cutting) – GB/T 5782-2000
- Wire diameter: Match GB/T 5782-2000 "heading-rod" profile
- Volume reference for this size: (exact values OCR-dependent, see original table)

### Stage 1 (Initial Heading) – GB/T 5782-2000 → GB/T 5784-86
- Form head blank; transition from cutting profile to near-final head diameter
- Quality: avoid laps, check head-to-rod ratio

### Stage 2 (Final Heading) – GB/T 5784-86
- Finalize head diameter and thickness
- Trim flash; establish thread run-out profile

### Stage 3 (Trimming) – GB/T 5784-86
- Remove excess material (flash)
- Achieve final head form and draft angles

---

## FastenerGPT Step 3 Integration

**Surface Treatment Rule Set:**
1. **Material class** → select treatment pathway:
   - Steel/alloy: alkaline oxidation → pickling → phosphating → saponification → lubricant
   - 1Cr18Ni9Ti stainless: oxalic acid bath → oxalate rinse → lubricant
   - Aluminum (2A11/2A12): gasoline wash → hot/cold rinse → HNO₃ pickle → alkaline oxidation → lubricant
   - Cu/brass: gasoline → hot/cold rinse → passivation (brief)

2. **Temperature/time windows** are strict:
   - Use ±5 °C tolerance for tank temperature
   - Flag if dwelling outside stated minutes (risk of over/under-treatment)

3. **Rinsing sequence matters**: omitting intermediate cold-water rinse risks contamination to next stage

4. **Post-treatment lubricant choice** depends on heading load and surface finish target

---

## Uncertainty Notes

1. **Page 64 OCR (Step 4 in passivation):** One process step is unreadable; likely an acid or rinse step.
2. **Table F12-1 (Page 65–66):** Heavily damaged OCR; column data partially recovered. Manual verification recommended for non-ferrous lubrication recipes.
3. **Numeric exactness:** All g/L and °C values shown; temperature tolerances inferred as ±5 °C where not explicit.
4. **Station volumes (Stage 0, table):** Values for "V1 rod volume" and work-hardening reference volume are present but OCR confidence is moderate; cross-check against GB/T 5782-2000 directly.
