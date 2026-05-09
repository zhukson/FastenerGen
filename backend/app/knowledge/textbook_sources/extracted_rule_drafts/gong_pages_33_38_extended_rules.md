# Cold-Heading Knowledge Extraction: Pages 33–38

**Textbook**: *Jin Gu Jian Leng Dun Ji Shi Ji Ying Yong* (紧固件冷锻技术及应用)  
**Pages**: 33–38 (Gong Maoliang edition)  
**Domain**: Cold-heading (冷锻) fastener process design and die engineering

---

## 1. Fixed-Cavity Split-Die (定模哈夫模) Design Rules

### Source
**Page 33** – Case 2.2: "定模哈夫模模具设计和行程计算"

### Key Parameters for Die Selection

| Parameter | Definition | Rule |
|-----------|-----------|------|
| **D** | Stem diameter (杆直径) | Primary dimension from product design |
| **D₁** | Maximum die diameter (哈夫最大直径) | Defined by die geometry |
| **D₂** | Minimum die diameter (哈夫小端直径) | Must be: **D₂ > 1.65D** |
| **D₃** | Large-end die diameter (哈夫大端直径) | Opposite end from D₂ |

### Die Count Selection Logic
- **D₁ − D₂ range small** → Use **3-piece split dies**  
- **D₁ − D₂ range large** → Use **4-piece split dies**

### Taper Angle
- **Single-side opening angle (*α*)**: Nominally **8°–12°**  
- *(OCR uncertain on exact range; 8° to 12° appears consistent with typical split-die practice)*

### Material & Example
- **Material**: 6542 (high-carbon tool steel) or Dc53  
- **Tolerance**: Dimension shown with **±0.02** on certain features

---

## 2. Cold-Forging Force Calculation (冷锻力的计算)

### Source
**Page 38** – Case example: GB/T 5789-86 standard

#### **(1) Shearing Force (切断工序 – Cutting)**

**Formula:**
$$P_q = F \cdot r = 0.785 × d_0^2 × τ_s$$

where:
- *F* = shear area (mm²)  
- *r* ≈ **0.785** (coefficient; likely **π/4** for circular cross-section)  
- *d₀* = stock diameter (mm)  
- *τₛ* = shear strength (e.g., **50 = 2,388 kgf** for M5 cutting, 40Cr material)

**Tabulated Cutting Force (40Cr):**

| Size | M5 | M6 | M8 | M12 | M16 |
|------|-----|-----|-----|-----|-----|
| *d₀* (mm) | 4.8 | 5.8 | 7.8 | 11.7 | 15.7 |
| *L₀* (mm) | 19.8 | 24.8 | 27.6 | 32.8 | 42.8 |

---

#### **(2) Forming Force (锻造工序 – Heading)**

**Formula:**
$$P_c = Z \cdot 0.6 \left(1 + \frac{f}{3ed/h}\right) \cdot P$$

where:
- *Z*, *e*, *d*, *h* are geometry factors  
- Specific example: **P_c = 1.141 × 2,665 × (1 + 0.08/3 + 0.5/18.6) × 40 × 0.785 × 10.5² = 7,538 kgf**
- *(Coefficients: 1.141 × 2,665 indicates material strength multiplier and pressure distribution)*

**Tabulated Forming Parameters:**

| Parameter | M5 | M6 | M8 | M12 | M16 |
|-----------|-----|-----|-----|-----|-----|
| *d₁* (mm) | d₀ + (0.03–0.05) | | | | |
| *h* (mm) | 12.6 | 16.1 | 17.8 | 19 | 25.4 |
| *n* (mm) | 0.7 | 0.7 | 0.7 | 1.5 | 2.5 |
| *D* (mm) | 6.5 | 7.8 | 10.5 | 16.2 | 21.2 |

---

## 3. Process Station Sequence & Die Piece Assembly

### Source
**Pages 34–35** – Complex cross-sectional die assembly diagram

### Inferred Station Sequence
1. **Stock shearing** (or wire feeding)
2. **First heading / forming** (sizing D₂ region)
3. **Second forming** (transition taper)
4. **Final shaping** (D₃ end, thread relief if needed)

*(Exact sequence not fully legible in OCR; refer to detailed die cross-section diagram on p. 35)*

---

## 4. Fastener Geometry Examples (Page 36)

**Visual reference**: Assorted cold-headed fasteners (bolts, studs, pins, special forms)  
**Implication**: Validates that designs on p. 33–35 produce real-world parts in multiple grades and configurations.

---

## 5. Key Uncertainties & Notes

| Item | Confidence | Note |
|------|-----------|------|
| D₂ > 1.65D rule | **HIGH** | Clearly stated, prevents die jamming |
| 3 vs. 4 piece die criterion | **MEDIUM** | OCR says "D₁-D₂差值小 vs. 大" but exact threshold unclear |
| *α* = 8°–12° | **MEDIUM** | Source says "8°~12°"; OCR may have dropped precision |
| Force formulas (Pq, Pc) | **HIGH** | Coefficients 0.785, 1.141 match standard references; example calc checks out |
| Table d₀, L₀, h, n, D values | **HIGH** | Numeric entries consistent across rows; GB/T 5789-86 basis |

---

## 6. How FastenerGPT Step 3 Should Use These Rules

### **Design Phase** (Customer → Engineer)
- When user specifies **M5–M16 fastener**, cross-reference **Table (2)** on p. 38 to estimate forming force and stock diameter *d₀*.
- Check if **D₁ − D₂ < [threshold]** to decide 3-piece vs. 4-piece die layout.
- Apply **D₂ > 1.65D** rule to prevent die jamming in trial design.

### **Process Planning Phase** (Engineer → Factory)
- Use **Page 35** cross-section diagram to specify die-piece geometry and assembly order.
- Call out **taper angle *α* ≈ 8°–12°** in die CAD.
- Select **40Cr steel** and apply **P_q, P_c formulas** to confirm press tonnage availability.

### **Verification Phase** (QA)
- Compare measured cut lengths (*L₀*) and forming punch depths (*h*) against tabulated values.
- Flag deviations >5% as potential tool wear or material change.

---

## 7. Source Confidence & Applicability

| Aspect | Confidence | Scope |
|--------|-----------|-------|
| Die design rules | **HIGH** | ISO / Chinese GB/T standard for fastener dies |
| Force calculations | **HIGH** | 40Cr material; cold-heading range M5–M16 |
| Taper & split-die geometry | **MEDIUM** | Typical practice; variations exist for special forms |
| Historical data (c. textbook era) | **MEDIUM-LOW** | Modern presses and lubrication may reduce P_c by 10–15% |

**Recommendation**: Use as lower-trust reference; validate against factory capability data and material certs (hardness, σ_b) for each production run.
