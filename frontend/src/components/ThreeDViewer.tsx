"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, type DesignResult, type OutputFile } from "@/lib/api";

type ViewerProps = {
  stlUrl?: string;
  designId?: string;
  design?: DesignResult;
  height?: number;
};

export function ThreeDViewer({ stlUrl: propStlUrl, designId, design, height = 480 }: ViewerProps) {
  // Station tab selection
  const stations =
    design?.process_plan?.stations.map((s) => s.station_number) ?? [];
  const [activeStation, setActiveStation] = useState<number | "assembly">(
    stations[0] ?? "assembly"
  );
  const [loaded, setLoaded] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Determine the STL URL to load
  const resolveStlUrl = (): string | undefined => {
    if (propStlUrl) return propStlUrl;
    if (!design || !designId) return undefined;

    const stationNum =
      activeStation === "assembly" ? null : (activeStation as number);
    let file: OutputFile | undefined;

    if (stationNum !== null) {
      file = design.output_files.find(
        (f) =>
          f.file_type === "die_stl" && f.station_number === stationNum
      );
      if (!file)
        file = design.output_files.find(
          (f) => f.file_type === "punch_stl" && f.station_number === stationNum
        );
    } else {
      file = design.output_files.find((f) => f.file_type === "punch_stl");
    }

    if (!file) return undefined;
    const fileName = file.file_path.split("/").pop() ?? "";
    return apiClient.downloadFile(designId, fileName);
  };

  const stlUrl = resolveStlUrl();

  useEffect(() => {
    if (!stlUrl || !canvasRef.current) return;
    setLoaded(false);

    let cleanup = () => {};

    (async () => {
      const THREE = await import("three");
      const { OrbitControls } = await import(
        // @ts-expect-error -- dynamic three addons import
        "three/examples/jsm/controls/OrbitControls.js"
      );
      const { STLLoader } = await import(
        // @ts-expect-error -- dynamic three addons import
        "three/examples/jsm/loaders/STLLoader.js"
      );

      if (!canvasRef.current) return;
      const el = canvasRef.current;
      const w = el.clientWidth || 600;
      const h = height - (stations.length > 0 ? 40 : 0);

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(w, h);
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setClearColor(0x111827);
      el.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 5000);
      camera.position.set(100, 80, 150);

      scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
      dirLight.position.set(100, 200, 100);
      scene.add(dirLight);
      scene.add(new THREE.GridHelper(200, 20, 0x444444, 0x333333));

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;

      const loader = new STLLoader();
      loader.load(
        stlUrl,
        (geometry: THREE.BufferGeometry) => {
          const mat = new THREE.MeshPhongMaterial({
            color: 0x5a7fa8,
            specular: 0x888888,
            shininess: 80,
          });
          const mesh = new THREE.Mesh(geometry, mat);
          geometry.computeBoundingBox();
          const box = geometry.boundingBox!;
          const center = new THREE.Vector3();
          box.getCenter(center);
          mesh.position.sub(center);
          scene.add(mesh);
          setLoaded(true);
        },
        undefined,
        (err: unknown) => console.error("STL load error", err)
      );

      let frameId: number;
      const animate = () => {
        frameId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      };
      animate();

      cleanup = () => {
        cancelAnimationFrame(frameId);
        renderer.dispose();
        if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
      };
    })();

    return () => cleanup();
  }, [stlUrl, height, stations.length]);

  const tabHeight = stations.length > 0 ? 40 : 0;
  const viewerHeight = height - tabHeight;

  if (!stlUrl && !design) {
    return (
      <div
        className="w-full flex items-center justify-center bg-gray-900 text-gray-400"
        style={{ height }}
      >
        <div className="text-center">
          <p className="text-4xl mb-3">🔩</p>
          <p className="font-medium">3D Viewer</p>
          <p className="text-sm mt-1 text-gray-500">
            {designId ? "No 3D models generated" : "No model loaded"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col" style={{ height }}>
      {/* Station tabs */}
      {stations.length > 0 && (
        <div className="flex items-center gap-1 px-3 py-2 bg-gray-800 border-b border-gray-700">
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
            Assembly
          </button>
        </div>
      )}

      {/* Canvas */}
      <div className="relative flex-1">
        {!stlUrl ? (
          <div
            className="w-full h-full flex items-center justify-center bg-gray-900 text-gray-400"
            style={{ height: viewerHeight }}
          >
            <div className="text-center text-sm">No 3D file for this station</div>
          </div>
        ) : (
          <>
            <div ref={canvasRef} className="w-full h-full" style={{ height: viewerHeight }} />
            {!loaded && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900 text-gray-400">
                <div className="text-center">
                  <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  <p className="text-sm">Loading 3D model…</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
