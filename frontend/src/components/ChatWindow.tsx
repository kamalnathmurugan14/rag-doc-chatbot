import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Message } from "../api/client";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
  busy: boolean;
  activeN: number | null;
  onSend: (q: string) => void;
  onStop: () => void;
  onRegenerate: () => void;
  onCite: (m: Message, n: number) => void;
  onDebug: (m: Message) => void;
  scopeLabel: string;
}

export function ChatWindow({
  messages,
  busy,
  activeN,
  onSend,
  onStop,
  onRegenerate,
  onCite,
  onDebug,
  scopeLabel,
}: Props) {
  const [q, setQ] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim() && !busy) {
      onSend(q.trim());
      setQ("");
    }
  };
  return (
    <section className="chat" aria-label="Chat">
      <div className="messages">
        {messages.length === 0 && (
          <p className="empty">
            Ask a question about your documents.
            <br />
            <span className="muted">Scope: {scopeLabel}</span>
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} m={m} activeN={activeN} onCite={onCite} onDebug={onDebug} />
        ))}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="question">
          Your question
        </label>
        <input
          id="question"
          type="text"
          placeholder="Ask about your documents…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          disabled={busy}
          autoComplete="off"
        />
        {busy ? (
          <button type="button" onClick={onStop}>
            ■ Stop
          </button>
        ) : (
          <button className="primary" type="submit" disabled={!q.trim()}>
            Send
          </button>
        )}
        <button type="button" onClick={onRegenerate} disabled={busy || messages.length < 2}>
          ↻ Regenerate
        </button>
      </form>
    </section>
  );
}
