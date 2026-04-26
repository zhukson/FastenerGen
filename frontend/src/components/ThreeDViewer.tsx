"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, type DesignResult, type OutputFile } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StationMeshes = {
  punch?: string;
  die?: string;
  workpiece?: string;
  assembly?: string;
};

type ViewerProps = {
  stlUrl?: string;
  designId?: string;
  design?: DesignResult;
  height?: number;
  activeStation?: number | "assembly";
  onSelectStation?: (s: number | "assembly") => void;
  hideStationTabs?: boolean;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getFileUrl(file: OutputFile, designId: string): string {
  const fp = file.file_path;
  const marker = designId + "/";
  const idx = fp.indexOf(marker);
  const rel = idx >= 0 ? fp.slice(idx + marker.length) : fp.split("/").pop()!;
  return apiClient.downloadFile(designId, rel);
}

function resolveStationMeshes(
  stationNum: number,
  design: DesignResult,
  designId: string,
): StationMeshes {
  const byType = (type: string, sn: number | null) =>
    design.output_files.find(f => f.file_type === type && f.station_number === sn);
  const toUrl = (f?: OutputFile) => (f ? getFileUrl(f, designId) : undefined);
  return {
    punch:     toUrl(byType("punch_stl", stationNum)),
    die:       toUrl(byType("die_stl", stationNum)),
    workpiece: toUrl(byType("workpiece_stl", stationNum)),
    assembly:  toUrl(byType("assembly_preview", stationNum)),
  };
}

// ---------------------------------------------------------------------------
// Dimension labels (sourced from backend design data, not inferred from mesh)
// ---------------------------------------------------------------------------

type DimLabel = { text: string; anchor: "top" | "side" };

function labelsForRole(
  role: "punch" | "die" | "workpiece",
  stationNum: number,
  design: DesignResult,
): DimLabel[] {
  const dp = design.die_parameters.find(d => d.station_number === stationNum);
  const sp = design.process_plan.stations.find(s => s.station_number === stationNum);

  if (role === "punch" && dp) {
    const out: DimLabel[] = [
      { text: `⌀${dp.punch.outer_diameter.toFixed(2)} mm`, anchor: "side" },
      { text: `L=${dp.punch.working_length.toFixed(1)} mm`, anchor: "top" },
    ];
    return out;
  }
  if (role === "die" && dp) {
    const out: DimLabel[] = [
      { text: `OD ⌀${dp.die.outer_diameter.toFixed(2)} mm`, anchor: "side" },
    ];
    if (dp.die.inner_diameter) {
      out.push({ text: `ID ⌀${dp.die.inner_diameter.toFixed(3)} mm`, anchor: "top" });
    }
    return out;
  }
  if (role === "workpiece" && sp) {
    const out: DimLabel[] = [
      { text: `⌀${sp.output_shape.max_diameter.toFixed(2)} mm`, anchor: "side" },
      { text: `L=${sp.output_shape.overall_length.toFixed(1)} mm`, anchor: "top" },
    ];
    if (sp.upset_ratio) {
      out.push({ text: `upset ${sp.upset_ratio.toFixed(2)}×`, anchor: "top" });
    }
    return out;
  }
  return [];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ThreeDViewer({
  stlUrl: propStlUrl,
  designId,
  design,
  height = 480,
  activeStation: propActiveStation,
  onSelectStation,
  hideStationTabs = false,
}: ViewerProps) {
  const stations = design?.process_plan?.stations.map((s) => s.station_number) ?? [];
  const defaultStation: number | "assembly" = stations[0] ?? "assembly";

  const [internalStation, setInternalStation] = useState<number | "assembly">(defaultStation);
  const activeStation = propActiveStation ?? internalStation;
  const setActiveStation = onSelectStation ?? setInternalStation;

  const [loaded, setLoaded] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);

  const tabsVisible = stations.length > 0 && !hideStationTabs;
  const TAB_H = tabsVisible ? 40 : 0;
  const viewerH = height - TAB_H;

  // Sync internal state when design loads
  useEffect(() => {
    if (stations.length > 0 && !propActiveStation) {
      setInternalStation(stations[0]);
    }
  }, [design?.design_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!canvasRef.current) return;
    if (!design && !propStlUrl) return;

    setLoaded(false);

    // Cancellation flag — prevents stale async loads from affecting the DOM
    // after the effect is cleaned up (handles React Strict Mode double-mount
    // and rapid station switching).
    let cancelled = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let rendererRef: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let labelRendererRef: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let controlsRef: any = null;
    let frameId: number;
    const el = canvasRef.current;

    (async () => {
      const THREE = await import("three");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      const { STLLoader } = await import("three/examples/jsm/loaders/STLLoader.js");
      const { CSS2DRenderer, CSS2DObject } = await import(
        "three/examples/jsm/renderers/CSS2DRenderer.js"
      );

      if (cancelled || !el) return;

      const w = el.clientWidth || 600;

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      rendererRef = renderer;
      renderer.setSize(w, viewerH);
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setClearColor(0x111827);
      el.appendChild(renderer.domElement);

      // CSS2D overlay renderer — draws HTML labels that track world
      // coordinates. Positioned on top of the WebGL canvas.
      const labelRenderer = new CSS2DRenderer();
      labelRendererRef = labelRenderer;
      labelRenderer.setSize(w, viewerH);
      labelRenderer.domElement.style.position = "absolute";
      labelRenderer.domElement.style.top = "0";
      labelRenderer.domElement.style.left = "0";
      labelRenderer.domElement.style.pointerEvents = "none";
      el.appendChild(labelRenderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, w / viewerH, 0.1, 5000);
      camera.position.set(100, 80, 150);

      scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
      dirLight.position.set(100, 200, 100);
      scene.add(dirLight);
      scene.add(new THREE.GridHelper(300, 30, 0x444444, 0x333333));

      const controls = new OrbitControls(camera, renderer.domElement);
      controlsRef = controls;
      controls.enableDamping = true;

      const loader = new STLLoader();

      const makeLabel = (text: string, hex: string) => {
        const div = document.createElement("div");
        div.textContent = text;
        div.style.cssText =
          `color:${hex};background:rgba(17,24,39,0.88);padding:2px 6px;` +
          `border-radius:3px;font-size:10px;` +
          `font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,monospace;` +
          `white-space:nowrap;border:1px solid ${hex}66;` +
          `box-shadow:0 1px 2px rgba(0,0,0,0.4);transform:translate(-50%,-50%)`;
        return new CSS2DObject(div);
      };

      const fitCamera = () => {
        const box = new THREE.Box3();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        scene.traverse((obj: any) => {
          if (obj.isMesh) box.expandByObject(obj);
        });
        if (box.isEmpty()) return;
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        camera.position.set(
          center.x + maxDim * 1.2,
          center.y + maxDim * 0.8,
          center.z + maxDim * 1.5,
        );
        camera.lookAt(center);
        camera.near = maxDim * 0.001;
        camera.far = maxDim * 20;
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.update();
      };

      const addMesh = (
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        geo: any,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        mat: any,
        offsetX = 0,
        labels?: { items: DimLabel[]; hex: string },
      ) => {
        geo.computeBoundingBox();
        const bbox = geo.boundingBox!;
        const center = new THREE.Vector3();
        bbox.getCenter(center);
        const size = new THREE.Vector3();
        bbox.getSize(size);

        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.sub(center);
        mesh.position.x += offsetX;
        scene.add(mesh);

        if (labels && labels.items.length > 0) {
          // Meshes are revolved around Z → length axis is Z, radius in X/Y.
          const halfX = size.x / 2;
          const halfZ = size.z / 2;
          const pad = Math.max(size.x, size.y, size.z) * 0.12 + 2;
          let topCount = 0;
          for (const lbl of labels.items) {
            const obj = makeLabel(lbl.text, labels.hex);
            if (lbl.anchor === "top") {
              // Stack top-anchored labels above the mesh along Z.
              obj.position.set(0, 0, halfZ + pad + topCount * 4);
              topCount += 1;
            } else {
              obj.position.set(halfX + pad, 0, 0);
            }
            mesh.add(obj);
          }
        }
      };

      // --- Load meshes ---

      if (propStlUrl) {
        // Legacy single-STL mode
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        loader.load(propStlUrl, (geo: any) => {
          if (cancelled) return;
          const mat = new THREE.MeshPhongMaterial({ color: 0x5a7fa8, specular: 0x888888, shininess: 80 });
          addMesh(geo, mat);
          fitCamera();
          setLoaded(true);
        });
      } else if (design && designId) {
        if (activeStation === "assembly") {
          // Show all station assemblies side-by-side
          const assemblyFiles = design.output_files.filter(f => f.file_type === "assembly_preview");
          if (assemblyFiles.length === 0) {
            setLoaded(true);
          } else {
            let remaining = assemblyFiles.length;
            const spacing = 90;
            assemblyFiles.forEach((f, i) => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              loader.load(getFileUrl(f, designId), (geo: any) => {
                if (cancelled) return;
                const mat = new THREE.MeshPhongMaterial({ color: 0x5a7fa8, specular: 0x444444 });
                addMesh(geo, mat, i * spacing);
                remaining--;
                if (remaining === 0) { fitCamera(); setLoaded(true); }
              });
            });
          }
        } else {
          const sn = activeStation as number;
          const meshes = resolveStationMeshes(sn, design, designId);

          const loadIndividual = () => {
            const configs = [
              { url: meshes.punch,     color: 0x4a9eff, hex: "#4a9eff", role: "punch" as const,     transparent: false, opacity: 1.0 },
              { url: meshes.die,       color: 0x888888, hex: "#bbbbbb", role: "die" as const,       transparent: true,  opacity: 0.72 },
              { url: meshes.workpiece, color: 0xf5a623, hex: "#f5a623", role: "workpiece" as const, transparent: false, opacity: 1.0 },
            ].filter((c): c is typeof c & { url: string } => !!c.url);

            if (configs.length === 0) { fitCamera(); setLoaded(true); return; }

            let remaining = configs.length;
            configs.forEach(c => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              loader.load(c.url, (geo: any) => {
                if (cancelled) return;
                const mat = new THREE.MeshPhongMaterial({
                  color: c.color,
                  transparent: c.transparent,
                  opacity: c.opacity,
                  specular: 0x333333,
                  shininess: 60,
                });
                const items = labelsForRole(c.role, sn, design);
                addMesh(geo, mat, 0, { items, hex: c.hex });
                remaining--;
                if (remaining === 0) { fitCamera(); setLoaded(true); }
              });
            });
          };

          // Skip pre-baked assembly STLs when we have a design — the
          // individual-mesh path is what drives dimension labels.
          loadIndividual();
        }
      }

      const animate = () => {
        if (cancelled) return;
        frameId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
        labelRenderer.render(scene, camera);
      };
      animate();
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(frameId);
      if (controlsRef) controlsRef.dispose();
      if (rendererRef) {
        rendererRef.dispose();
        if (el.contains(rendererRef.domElement)) el.removeChild(rendererRef.domElement);
      }
      if (labelRendererRef && el.contains(labelRendererRef.domElement)) {
        el.removeChild(labelRendererRef.domElement);
      }
    };
  }, [propStlUrl, activeStation, designId, design?.design_id, viewerH]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!propStlUrl && !design) {
    return (
      <div
        className="w-full flex items-center justify-center bg-gray-900 text-gray-400"
        style={{ height }}
      >
        <div className="text-center">
          <p className="text-4xl mb-3">🔩</p>
          <p className="font-medium">3D Viewer</p>
          <p className="text-sm mt-1 text-gray-500">No model loaded</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col" style={{ height }}>
      {/* Station tabs */}
      {tabsVisible && (
        <div className="flex items-center gap-1 px-3 py-2 bg-gray-800 border-b border-gray-700 flex-shrink-0">
          {stations.map((sn) => (
            <button
              key={sn}
              onClick={() => setActiveStation(sn)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeStation === sn
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-700"
              }`}
            >
              Station {sn}
            </button>
          ))}
          <button
            onClick={() => setActiveStation("assembly")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              activeStation === "assembly"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-700"
            }`}
          >
            All Stations
          </button>
        </div>
      )}

      {/* Canvas area */}
      <div className="relative flex-1">
        <div
          ref={canvasRef}
          className="w-full h-full"
          style={{ height: viewerH, position: "relative" }}
        />

        {/* Loading spinner */}
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900 text-gray-400 pointer-events-none">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm">Loading 3D model…</p>
            </div>
          </div>
        )}

        {/* Color legend — shown for per-station view with individual meshes */}
        {loaded && activeStation !== "assembly" && (
          <div className="absolute bottom-3 left-3 flex flex-col gap-1 text-xs bg-gray-900/80 rounded-lg px-2 py-1.5 backdrop-blur-sm">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: "#4a9eff" }} />
              <span className="text-gray-300">Punch</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm opacity-75" style={{ background: "#888888" }} />
              <span className="text-gray-300">Die</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ background: "#f5a623" }} />
              <span className="text-gray-300">Workpiece</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
