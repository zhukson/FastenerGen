"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api";

interface FeedbackButtonsProps {
  designId: string;
}

type Action = "Accept" | "Needs Changes" | "Reject";

const ACTION_STYLES: Record<Action, { active: string; inactive: string; apiAction: string }> = {
  Accept: {
    active: "bg-green-600 text-white border-green-600",
    inactive: "bg-white text-gray-600 border-gray-300 hover:border-green-400 hover:text-green-600",
    apiAction: "accept",
  },
  "Needs Changes": {
    active: "bg-yellow-500 text-white border-yellow-500",
    inactive: "bg-white text-gray-600 border-gray-300 hover:border-yellow-400 hover:text-yellow-600",
    apiAction: "needs_changes",
  },
  Reject: {
    active: "bg-red-600 text-white border-red-600",
    inactive: "bg-white text-gray-600 border-gray-300 hover:border-red-400 hover:text-red-600",
    apiAction: "reject",
  },
};

export function FeedbackButtons({ designId }: FeedbackButtonsProps) {
  const [selected, setSelected] = useState<Action | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleClick = async (action: Action) => {
    if (submitting || submitted) return;
    setSelected(action);
    setSubmitting(true);
    try {
      await apiClient.submitFeedback(designId, ACTION_STYLES[action].apiAction);
      setSubmitted(true);
    } catch {
      // Still show selection even if API fails
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {submitted && (
        <span className="text-xs text-gray-400 mr-1">Feedback recorded</span>
      )}
      {(["Accept", "Needs Changes", "Reject"] as Action[]).map((action) => {
        const styles = ACTION_STYLES[action];
        const isActive = selected === action;
        return (
          <button
            key={action}
            onClick={() => void handleClick(action)}
            disabled={submitting || submitted}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              isActive ? styles.active : styles.inactive
            } ${(submitting || submitted) && !isActive ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {action}
          </button>
        );
      })}
    </div>
  );
}
