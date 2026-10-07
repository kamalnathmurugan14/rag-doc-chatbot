import { useCallback, useRef, useState } from "react";
import { API_URL, type ChatOptions, type Message, type Scope } from "../api/client";
import { streamPost } from "../api/sse";

let seq = 0;
const uid = () => `m${++seq}`;

/** Chat state + SSE streaming. `stop()` aborts the request, which cancels generation on the server. */
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const ctrl = useRef<AbortController | null>(null);
  const lastQuestion = useRef<{ q: string; scope: Scope; options: ChatOptions } | null>(null);

  const patchLast = (fn: (m: Message) => Message) =>
    setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)));

  const send = useCallback(
    async (question: string, scope: Scope, options: ChatOptions, sid: number | null) => {
      lastQuestion.current = { q: question, scope, options };
      const c = new AbortController();
      ctrl.current = c;
      setBusy(true);
      setMessages((ms) => [
        ...ms,
        { id: uid(), role: "user", content: question },
        { id: uid(), role: "assistant", content: "", streaming: true },
      ]);
      try {
        await streamPost(
          "/chat",
          { session_id: sid, question, scope, options },
          (e) => {
            if (e.event === "rewritten_query")
              patchLast((m) => ({ ...m, rewritten: e.data.rewritten ? e.data.query : null }));
            else if (e.event === "sources") patchLast((m) => ({ ...m, sources: e.data.sources }));
            else if (e.event === "token") patchLast((m) => ({ ...m, content: m.content + e.data.text }));
            else if (e.event === "done") {
              setSessionId(e.data.session_id);
              patchLast((m) => ({
                ...m,
                streaming: false,
                citations: e.data.citations,
                alsoConsulted: e.data.also_consulted,
                debug: e.data.debug,
              }));
            } else if (e.event === "error")
              patchLast((m) => ({ ...m, streaming: false, error: e.data.message }));
          },
          c.signal,
        );
      } catch (err) {
        patchLast((m) => ({ ...m, error: (err as Error).message }));
      } finally {
        patchLast((m) => ({ ...m, streaming: false }));
        setBusy(false);
      }
    },
    [],
  );

  const stop = useCallback(() => ctrl.current?.abort(), []);
  const regenerate = useCallback(() => {
    const l = lastQuestion.current;
    if (l && !busy) {
      setMessages((ms) => ms.slice(0, -2)); // drop the old question + answer from the screen
      void send(l.q, l.scope, l.options, sessionId);
    }
  }, [busy, send, sessionId]);
  const load = useCallback((sid: number | null, ms: Message[]) => {
    setSessionId(sid);
    setMessages(ms);
  }, []);
  const reset = useCallback(() => load(null, []), [load]);
  return { messages, sessionId, busy, send, stop, regenerate, load, reset, apiUrl: API_URL };
}
