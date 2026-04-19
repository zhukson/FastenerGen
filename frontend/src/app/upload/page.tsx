"use client";

import { DrawingUploader } from "@/components/DrawingUploader";

export default function UploadPage() {
  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Upload Drawing</h1>
      <p className="text-gray-500 mb-6">
        Upload a product drawing to generate die designs. Supported formats: PDF, DWG, DXF, JPG, PNG.
      </p>
      <DrawingUploader />
    </div>
  );
}
