"use client";

import { useState } from "react";
import type { RetrievedChunk } from "@/types/api";

interface Props {
  sources: RetrievedChunk[];
}

export function SourcesList({ sources }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-gray-400 hover:text-gray-600 transition-colors text-xs"
      >
        <svg
          aria-hidden="true"
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        {sources.length} source{sources.length !== 1 ? "s" : ""}
      </button>

      {open && (
        <div className="mt-2 space-y-2 max-w-xl">
          {sources.map((s) => (
            <div
              key={s.source_url}
              className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2"
            >
              <a
                href={s.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline font-medium text-xs block mb-1 truncate"
              >
                {s.heading ?? s.source_url}
              </a>
              <p className="text-gray-600 text-xs line-clamp-2 leading-relaxed">
                {s.content}
              </p>
              <span className="text-gray-400 text-xs mt-1 block">
                score {s.score.toFixed(3)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
