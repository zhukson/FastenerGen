# Session 10: Frontend Polish

Read @CLAUDE.md for full project context. Sessions 5–9 must be complete.

## Goal

The UI looks like a real product, not a prototype. A factory owner watching the demo can follow the AI's reasoning, understand what was retrieved, and download exactly what they need in one click. Zero rough edges on the critical demo path.

After this session: the full demo flow (upload → generate → review → download) feels polished and professional.

---

## Task 1: ReasoningPanel — Retrieved Case Cards

### File: `frontend/src/components/ReasoningPanel.tsx`

Replace the raw JSON / plain text dump of retrieved cases with proper cards.

### 1a: RetrievedCaseCard component

```tsx
function RetrievedCaseCard({ case: c, rank }: { case: RetrievedCase; rank: number }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-gray-400">#{rank}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
          c.confidence === "high"   ? "bg-green-900 text-green-300" :
          c.confidence === "medium" ? "bg-yellow-900 text-yellow-300" :
                                      "bg-red-900 text-red-300"
        }`}>{c.confidence}</span>
      </div>
      <p className="font-medium text-white">{c.part_spec}</p>
      <p className="text-gray-400 text-xs mt-1">
        {c.head_type} · {c.material_grade} · {c.station_count} stations
      </p>
      <div className="mt-2 text-xs text-gray-500">
        Similarity: {(c.similarity_score * 100).toFixed(0)}%
      </div>
    </div>
  );
}
```

Show up to 3 cards in a horizontal row under "Retrieved Cases" section header.

### 1b: Retrieval quality badge

Show a badge next to "Retrieved Cases":
- `exact_match` → green "Exact Match"
- `relaxed` → yellow "Similar"
- `no_match` → red "No Match — LLM reasoning only"

```tsx
const QUALITY_BADGE: Record<string, { label: string; className: string }> = {
  exact_match: { label: "Exact Match", className: "bg-green-900 text-green-300" },
  relaxed:     { label: "Similar",     className: "bg-yellow-900 text-yellow-300" },
  no_match:    { label: "No Match",    className: "bg-red-900 text-red-300" },
};
```

### 1c: Collapsible reasoning text

Wrap the long LLM reasoning text in a collapsible `<details>` / `<summary>`:

```tsx
<details className="mt-3">
  <summary className="text-xs text-blue-400 cursor-pointer hover:text-blue-300">
    Show AI reasoning ({reasoningLines} lines)
  </summary>
  <pre className="mt-2 text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">
    {design.reasoning_summary}
  </pre>
</details>
```

---

## Task 2: ProcessFlowDiagram — SVG Station Flow

### File: `frontend/src/components/ProcessFlowDiagram.tsx`

Replace the current placeholder (if any) with an SVG flow diagram showing the forming sequence.

### Station box layout:

```
[ Blank ] → [ S1 Upsetting ] → [ S2 Heading ] → [ S3 Extrusion ] → [ Finished ]
```

Each box shows:
- Station number + operation type
- Key parameter: upset_ratio or reduction %
- Color: same as workpiece (orange-toned) for active, gray for inactive

```tsx
export function ProcessFlowDiagram({ plan, activeStation, onSelectStation }: Props) {
  const steps = [
    { label: "Blank", key: 0, sub: `⌀${plan.blank_diameter.toFixed(1)}×${plan.blank_length.toFixed(0)}L` },
    ...plan.stations.map(s => ({
      label: `S${s.station_number}`,
      key: s.station_number,
      sub: getOperationLabel(s.operation_type),
    })),
  ];

  return (
    <svg
      viewBox={`0 0 ${steps.length * 120 - 20} 72`}
      className="w-full"
    >
      {steps.map((step, i) => (
        <g key={step.key} onClick={() => onSelectStation(step.key)} className="cursor-pointer">
          {/* Arrow between boxes */}
          {i > 0 && (
            <line
              x1={i * 120 - 10} y1={36}
              x2={i * 120 + 10} y2={36}
              stroke="#4b5563" strokeWidth={2}
              markerEnd="url(#arrow)"
            />
          )}
          {/* Station box */}
          <rect
            x={i * 120 + 12} y={12}
            width={88} height={48}
            rx={6}
            fill={activeStation === step.key ? "#1e3a5f" : "#1f2937"}
            stroke={activeStation === step.key ? "#3b82f6" : "#374151"}
            strokeWidth={activeStation === step.key ? 2 : 1}
          />
          <text x={i * 120 + 56} y={32} textAnchor="middle" fill="white" fontSize={11} fontWeight="bold">
            {step.label}
          </text>
          <text x={i * 120 + 56} y={46} textAnchor="middle" fill="#9ca3af" fontSize={9}>
            {step.sub}
          </text>
        </g>
      ))}
      <defs>
        <marker id="arrow" markerWidth={6} markerHeight={6} refX={3} refY={3} orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#4b5563" />
        </marker>
      </defs>
    </svg>
  );
}
```

Wire it into the design detail page above the 3D viewer.

---

## Task 3: FileDownloadPanel — Grouped by Station

### File: `frontend/src/components/FileDownloadPanel.tsx`

Group output files by station instead of a flat list.

### Layout:

```
Production Files
  [⬇ Production Drawing .dxf]  [⬇ Process Breakdown .dxf]

Station 1 — Upsetting
  [⬇ punch.dxf]  [⬇ die.dxf]  [⬇ punch.stl]  [⬇ die.stl]

Station 2 — Heading
  [⬇ punch.dxf]  [⬇ die.dxf]  ...
```

```tsx
const grouped = groupFilesByStation(design.output_files);

return (
  <div className="space-y-4">
    {grouped.map(group => (
      <div key={group.stationLabel}>
        <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
          {group.stationLabel}
        </h4>
        <div className="flex flex-wrap gap-2">
          {group.files.map(f => (
            <DownloadButton key={f.file_path} file={f} designId={designId} />
          ))}
        </div>
      </div>
    ))}
  </div>
);
```

Each `DownloadButton` shows:
- File format icon (📐 for DXF, 🧊 for STL/STEP)
- Short filename without path
- Size in KB

---

## Task 4: DXF Preview Endpoint + Thumbnail

### File: `backend/app/api/v1/designs.py`

Add a server-side DXF→PNG rasterization endpoint so we can preview DXF files in the browser without requiring AutoCAD:

```
GET /api/v1/designs/{design_id}/preview/{filename}
→ image/png
```

Implementation using ezdxf matplotlib backend:

```python
@router.get("/{design_id}/preview/{filename}")
async def get_file_preview(design_id: str, filename: str):
    """Render DXF as PNG for browser preview."""
    file_path = get_design_file_path(design_id, filename)
    if not file_path.exists():
        raise HTTPException(404)

    if filename.endswith(".dxf"):
        import ezdxf
        from ezdxf.addons.drawing import matplotlib
        import io

        doc = ezdxf.readfile(str(file_path))
        fig = matplotlib.qsave(
            doc.modelspace(),
            None,  # return figure
            dpi=150,
            ltype=matplotlib.LINE_TYPE_RENDERER,
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="#111827")
        buf.seek(0)
        return Response(buf.read(), media_type="image/png")

    raise HTTPException(400, "Preview only supported for DXF files")
```

### DXF thumbnail in FileDownloadPanel

In `FileDownloadPanel`, for `.dxf` files, show a small inline preview image:

```tsx
function DxfPreview({ designId, filename }: { designId: string; filename: string }) {
  const [open, setOpen] = useState(false);
  const previewUrl = apiClient.getPreviewUrl(designId, filename);

  return (
    <>
      <button onClick={() => setOpen(!open)} className="text-xs text-blue-400 hover:underline">
        {open ? "Hide preview" : "Preview"}
      </button>
      {open && (
        <img
          src={previewUrl}
          alt="DXF preview"
          className="mt-2 rounded border border-gray-700 max-w-full"
          style={{ maxHeight: 300 }}
        />
      )}
    </>
  );
}
```

---

## Task 5: Upload Page — Drawing Preview

### File: `frontend/src/app/upload/page.tsx`

After a drawing is uploaded and parsed, show a preview of the uploaded file before showing "Generate Die Design":

```tsx
{uploadResult?.drawing_preview_url && (
  <div className="mt-4 border border-gray-700 rounded-xl overflow-hidden">
    <img
      src={uploadResult.drawing_preview_url}
      alt="Uploaded drawing"
      className="w-full max-h-64 object-contain bg-gray-900"
    />
  </div>
)}
```

The backend already returns `drawing_preview_url` from the `/drawings/upload` endpoint if a PDF was converted to JPEG for Claude vision. Wire this into the upload response type and display it.

---

## Task 6: Design Detail Page — Cost + Latency Badge

### File: `frontend/src/app/designs/[id]/page.tsx`

Show cost and latency metadata in a small info row below the header:

```tsx
{design.metadata && (
  <div className="flex items-center gap-4 text-xs text-gray-500 mt-1">
    <span>⏱ {(design.metadata.generation_time_ms / 1000).toFixed(1)}s</span>
    <span>💰 ${design.metadata.total_cost_usd?.toFixed(4)}</span>
    <span>🔁 {design.metadata.retry_count ?? 0} retries</span>
    <span className="text-gray-600">|</span>
    <span>PP: {design.metadata.process_planning_model?.split('-').slice(-1)[0]}</span>
    <span>DD: {design.metadata.die_design_model?.split('-').slice(-1)[0]}</span>
  </div>
)}
```

---

## Acceptance Criteria

- [ ] ReasoningPanel shows 3 retrieved case cards with confidence badges
- [ ] Retrieval quality badge (Exact Match / Similar / No Match) is visible
- [ ] Reasoning text is collapsible with line count shown
- [ ] ProcessFlowDiagram renders the station sequence as an SVG flow
- [ ] Clicking a station box in the flow diagram switches the 3D viewer
- [ ] FileDownloadPanel groups files by station with section headers
- [ ] DXF preview loads inline when user clicks "Preview"
- [ ] Upload page shows drawing image preview after successful parse
- [ ] Cost + latency badge shows on design detail page
- [ ] No TypeScript errors (`tsc --noEmit` passes)

## Files Modified
- `frontend/src/components/ReasoningPanel.tsx` (case cards, collapsible reasoning)
- `frontend/src/components/ProcessFlowDiagram.tsx` (SVG station flow)
- `frontend/src/components/FileDownloadPanel.tsx` (grouped by station, DXF preview)
- `frontend/src/app/upload/page.tsx` (drawing image preview)
- `frontend/src/app/designs/[id]/page.tsx` (cost/latency badge, wire ProcessFlowDiagram)
- `frontend/src/lib/api.ts` (add getPreviewUrl)
- `backend/app/api/v1/designs.py` (add preview endpoint)
