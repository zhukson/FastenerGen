"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Accept / Reject / Needs Changes feedback buttons.
 * Feedback submission implemented in Session 4.
 * Every action captured as training data for the data flywheel.
 */
export function FeedbackButtons({ designId }: { designId: string }) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="flex gap-2">
      {(["Accept", "Needs Changes", "Reject"] as const).map((action) => (
        <button
          key={action}
          onClick={() => setSelected(action)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors",
            selected === action
              ? action === "Accept"
                ? "bg-green-600 text-white border-green-600"
                : action === "Reject"
                ? "bg-red-600 text-white border-red-600"
                : "bg-yellow-500 text-white border-yellow-500"
              : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
          )}
        >
          {action}
        </button>
      ))}
    </div>
  );
}
