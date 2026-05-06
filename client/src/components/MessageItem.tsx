import ReactMarkdown from "react-markdown";
import { SourcesList } from "./SourcesList";
import type { Message } from "@/types/api";

interface Props {
  message: Message;
}

export function MessageItem({ message }: Props) {
  const displayText =
    message.status === "streaming"
      ? message.answer + "▋"
      : message.answer;

  return (
    <div className="space-y-2">
      {/* Question */}
      <div className="flex justify-end">
        <div className="max-w-xl bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed">
          {message.question}
        </div>
      </div>

      {/* Answer */}
      <div className="flex justify-start">
        <div className="max-w-xl bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-gray-100 text-sm text-gray-800 leading-relaxed">
          {message.status === "streaming" && !message.answer ? (
            <span className="inline-flex gap-1 items-center h-5">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" />
            </span>
          ) : (
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0">{children}</p>
                ),
                code: ({ children }) => (
                  <code className="bg-gray-100 rounded px-1 py-0.5 text-xs font-mono">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="bg-gray-100 rounded p-3 text-xs font-mono overflow-x-auto my-2">
                    {children}
                  </pre>
                ),
              }}
            >
              {displayText}
            </ReactMarkdown>
          )}
        </div>
      </div>

      {/* Sources */}
      {message.sources.length > 0 && (
        <div className="pl-1">
          <SourcesList sources={message.sources} />
        </div>
      )}
    </div>
  );
}
