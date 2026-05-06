"use client";

import { KeyboardEvent, useState } from "react";

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");

  function submit() {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex gap-3 items-end max-w-3xl mx-auto w-full">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about FastAPI… (Enter to send, Shift+Enter for new line)"
        aria-label="Ask a question"
        rows={2}
        disabled={disabled}
        className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:bg-gray-50 bg-white"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="px-5 py-3 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
      >
        Send
      </button>
    </div>
  );
}
