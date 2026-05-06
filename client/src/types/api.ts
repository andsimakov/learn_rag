export interface RetrievedChunk {
  content: string;
  source_url: string;
  heading: string | null;
  score: number;
}

export interface Message {
  id: string;
  question: string;
  answer: string;
  sources: RetrievedChunk[];
  status: "streaming" | "done" | "error";
  traceId: string;
}

export type SseEvent =
  | { type: "sources"; sources: RetrievedChunk[] }
  | { type: "token"; text: string }
  | { type: "done"; trace_id: string }
  | { type: "error"; message: string };
