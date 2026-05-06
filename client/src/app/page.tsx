"use client";

import { useState } from "react";
import { ChatInput } from "@/components/ChatInput";
import { MessageList } from "@/components/MessageList";
import { streamQuery } from "@/lib/api";
import type { Message } from "@/types/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  async function handleSubmit(question: string) {
    const id = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id, question, answer: "", sources: [], status: "streaming", traceId: "" },
    ]);
    setIsStreaming(true);

    try {
      for await (const event of streamQuery(question)) {
        if (event.type === "sources") {
          setMessages((prev) =>
            prev.map((m) => (m.id === id ? { ...m, sources: event.sources } : m)),
          );
        } else if (event.type === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id ? { ...m, answer: m.answer + event.text } : m,
            ),
          );
        } else if (event.type === "done") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id ? { ...m, status: "done", traceId: event.trace_id } : m,
            ),
          );
        } else if (event.type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id ? { ...m, status: "error", answer: event.message } : m,
            ),
          );
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? { ...m, status: "error", answer: "Failed to connect to the server." }
            : m,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-4 shrink-0">
        <h1 className="text-lg font-semibold text-gray-900">FastAPI Docs Q&A</h1>
        <p className="text-xs text-gray-400 mt-0.5">
          RAG-powered assistant · FastAPI documentation
        </p>
      </header>

      <main className="flex-1 min-h-0">
        <MessageList messages={messages} />
      </main>

      <footer className="bg-white border-t border-gray-200 px-4 py-4 shrink-0">
        <ChatInput onSubmit={handleSubmit} disabled={isStreaming} />
      </footer>
    </div>
  );
}
