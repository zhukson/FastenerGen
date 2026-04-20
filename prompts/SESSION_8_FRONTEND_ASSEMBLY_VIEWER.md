# Session 8: Frontend Assembly Viewer

Read @CLAUDE.md for full project context. Sessions 5–7 must be complete (workpiece + assembly STLs exist).

## Goal

The 3D viewer shows the full forming story. Per station: punch (blue) + die (grey, semi-transparent) + workpiece (orange) in the same Three.js scene. A "Process Story" strip below the viewer shows all intermediate workpiece shapes in sequence. Station tabs switch between all these views.

After this session, a factory owner watching the demo sees the metal being progressively formed from wire blank to finished bolt — exactly the "aha" moment the product needs.

---

## Task 1: Multi-Mesh ThreeDViewer

### File: `frontend/src/components/ThreeDViewer.tsx`

### 1a: URL resolution for 3 meshes per station

Replace the single `resolveStlUrl()` with `resolveStationMeshes(stationNum)`:

```typescript
type StationMeshes = {
  punch?: string;
  die?: string;
  workpiece?: string;
  assembly?: string;
};

function resolveStationMeshes(
  stationNum: number | "assembly",
  design: DesignResult,
  designId: string
): StationMeshes {
  const byType = (type: string, sn: number | null) =>
    design.output_files.find(
      f => f.file_type === type && f.station_number === sn
    );

  if (stationNum === "assembly") {
    // Show all assemblies side by side — handled separately
    return {};
  }

  const sn = stationNum as number;
  const fileName = (f?: OutputFile) =>
    f ? apiClient.downloadFile(designId, f.file_path.split("/").pop()!) : undefined;

  return {
    punch:     fileName(byType("punch_stl", sn)),
    die:       fileName(byType("die_stl", sn)),
    workpiece: fileName(byType("workpiece_stl", sn)),
    assembly:  fileName(byType("assembly_preview", sn)),
  };
}
```

Prefer loading the pre-built `assembly.stl` when available (single mesh, already positioned). Fall back to loading individual meshes separately.

### 1b: Three.js multi-mesh loader

Replace the single STL load `useEffect` with a multi-mesh version:

```typescript
useEffect(() => {
  if (!canvasRef.current) return;
  const meshes = resolveStationMeshes(activeStation, design!, designId!);
  const url = meshes.assembly || null;
  const individualUrls = url ? null : meshes;

  // ... setup scene, camera, lights (same as before) ...

  const loader = new STLLoader();

  if (url) {
    // Load pre-built assembly
    loader.load(url, (geometry) => {
      const mat = new THREE.MeshPhongMaterial({ color: 0x5a7fa8, specular: 0x444444 });
      addMeshToScene(geometry, mat);
    });
  } else {
    // Load individual meshes with distinct materials
    const configs = [
      { url: individualUrls?.punch,     color: 0x4a9eff, name: "punch" },
      { url: individualUrls?.die,       color: 0x888888, transparent: true, opacity: 0.75, name: "die" },
      { url: individualUrls?.workpiece, color: 0xf5a623, name: "workpiece" },
    ];
    Promise.all(
      configs
        .filter(c => c.url)
        .map(c => new Promise<void>((resolve) => {
          loader.load(c.url!, (geometry) => {
            const mat = new THREE.MeshPhongMaterial({
              color: c.color,
              transparent: c.transparent ?? false,
              opacity: c.opacity ?? 1.0,
              specular: 0x333333,
              shininess: 60,
            });
            addMeshToScene(geometry, mat);
            resolve();
          });
        }))
    ).then(() => {
      fitCameraToScene(camera, scene);
      setLoaded(true);
    });
  }
}, [activeStation, designId]);
```

Add a `fitCameraToScene(camera, scene)` helper that computes the bounding box of all meshes and positions the camera to see them all.

### 1c: Color legend overlay

Add a small legend div (absolute positioned, bottom-left of canvas):
```tsx
{loaded && (
  <div className="absolute bottom-3 left-3 flex flex-col gap-1 text-xs">
    <div className="flex items-center gap-1.5">
      <div className="w-3 h-3 rounded-sm bg-[#4a9eff]" /> <span className="text-gray-300">Punch</span>
    </div>
    <div className="flex items-center gap-1.5">
      <div className="w-3 h-3 rounded-sm bg-[#888888] opacity-75" /> <span className="text-gray-300">Die</span>
    </div>
    <div className="flex items-center gap-1.5">
      <div className="w-3 h-3 rounded-sm bg-[#f5a623]" /> <span className="text-gray-300">Workpiece</span>
    </div>
  </div>
)}
```

### 1d: Assembly tab — side-by-side view

When `activeStation === "assembly"`, load all `assembly_preview` STLs (one per station) and space them along the X axis:

```typescript
if (activeStation === "assembly") {
  const assemblyFiles = design.output_files.filter(f => f.file_type === "assembly_preview");
  const spacing = 80; // mm between assemblies
  assemblyFiles.forEach((f, i) => {
    loader.load(apiClient.downloadFile(designId, f.file_path.split("/").pop()!), (geo) => {
      const mat = new THREE.MeshPhongMaterial({ color: 0x5a7fa8 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.x = i * spacing;
      scene.add(mesh);
    });
  });
}
```

---

## Task 2: Process Story Strip

### File: `frontend/src/components/StationViewer.tsx`

Replace the placeholder div with a horizontal scrollable strip. One thumbnail per station (station 0 = blank, station 1..N = intermediate shapes).

Each thumbnail is a 100×120px mini Three.js canvas showing the workpiece silhouette from that station.

```tsx
export function StationViewer({ design, designId, activeStation, onSelectStation }: Props) {
  const stations = [0, ...design.process_plan.stations.map(s => s.station_number)];

  return (
    <div className="flex items-end gap-3 overflow-x-auto py-3 px-2">
      {stations.map((sn) => (
        <WorkpieceThumbnail
          key={sn}
          stationNumber={sn}
          designId={designId}
          design={design}
          active={activeStation === sn}
          onClick={() => onSelectStation(sn)}
          label={sn === 0 ? "Blank" : `S${sn} ${getOperationLabel(design, sn)}`}
        />
      ))}
    </div>
  );
}
```

### WorkpieceThumbnail component

A small component that loads a single workpiece STL into a tiny Three.js canvas:

```tsx
function WorkpieceThumbnail({ stationNumber, designId, design, active, onClick, label }) {
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const file = design.output_files.find(
      f => f.file_type === "workpiece_stl" && f.station_number === stationNumber
    );
    if (!file || !canvasRef.current) return;
    const url = apiClient.downloadFile(designId, file.file_path.split("/").pop()!);

    // Tiny Three.js scene — fixed camera, no controls
    (async () => {
      const THREE = await import("three");
      const { STLLoader } = await import("three/examples/jsm/loaders/STLLoader.js");
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(100, 110);
      renderer.setClearColor(0x111827);
      canvasRef.current!.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      scene.add(new THREE.AmbientLight(0xffffff, 0.8));
      const dl = new THREE.DirectionalLight(0xffffff, 1.0);
      dl.position.set(50, 100, 50);
      scene.add(dl);

      const camera = new THREE.OrthographicCamera(-25, 25, 30, -30, 0.1, 1000);
      camera.position.set(60, 20, 60);
      camera.lookAt(0, 0, 0);

      new STLLoader().load(url, (geo) => {
        geo.computeBoundingBox();
        const center = new THREE.Vector3();
        geo.boundingBox!.getCenter(center);
        const mesh = new THREE.Mesh(geo, new THREE.MeshPhongMaterial({ color: 0xf5a623 }));
        mesh.position.sub(center);
        scene.add(mesh);
        renderer.render(scene, camera);
      });

      return () => { renderer.dispose(); canvasRef.current?.removeChild(renderer.domElement); };
    })();
  }, [stationNumber, designId]);

  return (
    <div
      onClick={onClick}
      className={`flex flex-col items-center cursor-pointer rounded-lg p-1 transition-colors
        ${active ? "bg-blue-900 ring-2 ring-blue-400" : "hover:bg-gray-800"}`}
    >
      <div ref={canvasRef} className="rounded overflow-hidden" style={{ width: 100, height: 110 }} />
      <p className="text-xs text-gray-400 mt-1 text-center leading-tight max-w-[100px]">{label}</p>
    </div>
  );
}
```

---

## Task 3: Wire Process Story into Design Detail Page

### File: `frontend/src/app/designs/[id]/page.tsx`

Below the main `ThreeDViewer`, add the `StationViewer` strip:

```tsx
<div className="mt-3 bg-gray-900 rounded-xl border border-gray-700 px-3">
  <p className="text-xs text-gray-500 pt-2 pb-1">Forming Sequence</p>
  <StationViewer
    design={design}
    designId={id}
    activeStation={activeStation}
    onSelectStation={setActiveStation}
  />
</div>
```

Lift the `activeStation` state up from `ThreeDViewer` to the page so both components share it. When user clicks a thumbnail, the main viewer updates.

---

## Task 4: api.ts — Add workpiece_stl and assembly_preview types

### File: `frontend/src/lib/api.ts`

Add `"workpiece_stl"` and `"assembly_preview"` to the `OutputFile.file_type` union if not already present.

---

## Acceptance Criteria

- [ ] Station 1 tab in 3D viewer shows punch (blue) + die (grey transparent) + workpiece (orange)
- [ ] Die is semi-transparent — workpiece partially visible through it
- [ ] Assembly tab shows all station assemblies side-by-side along X axis
- [ ] Color legend is visible in bottom-left of viewer
- [ ] Process Story strip renders below the 3D viewer with one thumbnail per station
- [ ] Clicking a thumbnail changes the main viewer to that station
- [ ] Active thumbnail is highlighted with blue ring
- [ ] No console errors when switching stations
- [ ] Station 0 (blank) thumbnail shows a simple cylinder

## Files Modified
- `frontend/src/components/ThreeDViewer.tsx` (major rewrite of Three.js section)
- `frontend/src/components/StationViewer.tsx` (implement from scratch)
- `frontend/src/app/designs/[id]/page.tsx` (add StationViewer, lift activeStation state)
- `frontend/src/lib/api.ts` (add file_type literals)
