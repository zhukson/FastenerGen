# Cold-Heading Rules Extraction
**Source:** *Gong Maoliang* Pages 57–62 (Appendices 8–11)

---

## Rule 1: Wire Material Grade Cross-Reference (Appendix 8)
**Provenance:** Pages 57–58

| Aspect | Value |
|--------|-------|
| **Purpose** | Domestic and international designation correspondence for cold-heading and cold-extrusion wire materials |
| **Status** | Reference table; exact grades obscured by OCR noise |
| **Usage in Step 3** | When specifying raw-material wire, match customer drawing codes (CN/US/EU/JP) to equivalent material properties |
| **Uncertainty** | OCR text heavily degraded; manual cross-check against source image required for specific grades |

---

## Rule 2: Die Material Grade Cross-Reference (Appendix 9)
**Provenance:** Page 59

| Aspect | Value |
|--------|-------|
| **Key Materials** | TCMo2V2Si (cold-work die) |
| **Japanese Classification** | V10–V60 (material usage categories) |
| **Taiwan/HQ Designations** | Tungsten carbide (硬质合金) segregated: mainland, Taiwan, Japan variants for die cavity manufacture |
| **Punch/Ejector Pin Materials** | SKH-9(H9), SKH-35(H55), SKH-59(M42), ASP-30, 60 (in order of application) |
| **Usage in Step 3** | Select die material grade based on production volume and part geometry; cross-check tooling cost vs. life expectancy |
| **Uncertainty** | Table structure incomplete in OCR; confirm material codes against die-maker specification sheets |

---

## Rule 3: Blank Softening Treatment (Appendix 10)
**Provenance:** Page 60–61

### General Principles
- **Purpose:** Reduce hardness, increase ductility, eliminate residual stress, improve microstructure before and between multi-stage extrusion
- **Optimal microstructure:** Spheroidized annealing (球化退火)
  - Lower hardness and strength
  - Higher plasticity
  - Effect scales with carbon content

### Temperature & Hardness Thresholds (Selected Examples)

| Material | Treatment | Pre-HBS | Post-HBS | Notes |
|----------|-----------|---------|----------|-------|
| Steel 1070A–1200 | 420°C anneal | — | 15–19 Rc | — |
| Aluminum 5A02 (LF2) | 390–400°C | — | 28–33 HRB | Air cool |
| Aluminum 2A14 (LD10) | 400–420°C | — | 150 | Space cool |
| Titanium Ti-T4 | 710–720°C | — | 38–42 | — |
| **Stainless 1Cr18Ni9Ti** | — | 200 HBS | 130–140 HBS | — |
| Bearing steel 6Cr15 | ≤350°C | 174–192 HRB | — | Cool to 680°C |

**Usage in Step 3:**  
- Specify annealing temperature range and hardness window for each alloy before extrusion  
- Verify incoming stock hardness; reject if outside post-treatment range

**Uncertainty:** Exact treatment times and furnace atmosphere (air, controlled) partially obscured; cross-check with supplier datasheets

---

## Rule 4: Blank Surface Treatment (Appendix 11)

**Provenance:** Page 62

### Physics Principle
- **Extrusion pressure (steel):** up to **2500 MPa** unit pressure  
- **Without lubrication:** microparticles weld to die cavity → surface damage → friction ↑ → die life ↓  
- **Purpose of surface treatment:** Create support layer → store lubricant → reduce friction

### Phosphate Coating (磷化处理) — Steel & Alloy Steel

#### Characteristics
1. **Microstructure:** Thin crystalline salt film with pores/micropores
   - Oil absorption: **13× higher** than bare steel surface
   - Friction coefficient (uncoated): 0.108 → (phosphated): 0.013
   
2. **Adhesion & Plasticity:** Bonds well to substrate; deforms with base metal
   - Substrate elongation 38% → phosphate layer retains 89%
   - Remains attached even after cold-extrusion with angular dies
   
3. **Thermal stability:** Maintains high-viscosity lubricant properties at **300°C** (extrusion temperature)

4. **Isolation:** Separates deformed metal from die cavity; prevents direct contact

5. **Lubrication synergy:** Reacts chemically with oil/emulsion lubricants → insoluble zinc stearate (硬脂酸锌) precipitate
   - Bonds tightly to blank surface
   - Effect is chemical, not just adsorptive

#### Process Steps (Pre-Phosphating)
- Acid pickle (removal of scale & oxide)
- Chemical degreasing
- Phosphating treatment
- Neutralization

**Usage in Step 3:**  
- Mandate phosphate coating for all steel blanks before extrusion  
- Specify oil absorption ≥ 10× bare steel as acceptance criterion  
- Pair with suitable lubricant for optimal friction reduction

**Uncertainty:** Specific phosphating bath chemistry and dwell time not included in OCR; defer to Appendix 11 process details (page 62 cut-off)

---

## Step 3 Integration Checklist

| Step | Rule Applied |
|------|--------------|
| **Material Selection** | Cross-reference wire grade (Rule 1); verify annealing hardness (Rule 3) |
| **Die Specification** | Select die material per volume/geometry (Rule 2) |
| **Blank Prep** | Phosphate-coat all steel; target hardness window (Rule 4) |
| **Process Control** | Monitor friction coefficient; flag lubricant compatibility with coating (Rule 4) |
| **Quality Gate** | Reject blanks outside post-anneal hardness; inspect coating adhesion |

---

## Uncertainty Summary

- **Pages 57–58 (Appendix 8):** Grade correspondence table OCR degraded; manual image review needed
- **Page 59 (Appendix 9):** Die material codes present but surrounding context incomplete
- **Pages 60–61 (Appendix 10):** Temperature ranges clear; treatment times and furnace atmosphere need verification
- **Page 62 (Appendix 11):** Process flowchart truncated; exact phosphating bath composition missing
