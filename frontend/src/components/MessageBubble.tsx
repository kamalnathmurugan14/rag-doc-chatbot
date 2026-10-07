import ReactMarkdown from "react-markdown";
import type { Message } from "../api/client";
import { CitationChip } from "./CitationChip";

/** Turn [1] or [2][3] into markdown links we can render as clickable chips. */
export const linkCitations = (text: string) => text.replace(/\[(\d+)\]/g, (_, n) => `[${n}](#cite-${n})`);

interface Props {
  m: Message;
  activeN?: number | null;
  onCite: (m: Message, n: number) => void;
  onDebug?: (m: Message) => void;
}

export function MessageBubble({ m, activeN, onCite, onDebug }: Props) {
  if (m.role === "user") return <div className="bubble user">{m.content}</div>;
  const known = new Set((m.sources ?? []).map((s) => s.n));
  return (
    <div className="bubble assistant" aria-live={m.streaming ? "polite" : undefined}>
      {m.rewritten && <div className="muted">🔎 searched for: “{m.rewritten}”</div>}
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            const n = href?.startsWith("#cite-") ? Number(href.slice(6)) : NaN;
            if (Number.isNaN(n))
              return (
                <a href={href} target="_blank" rel="noreferrer noopener">
                  {children}
                </a>
              );
            return known.has(n) ? (
              <CitationChip
                n={n}
                active={activeN === n}
                onClick={(x) => onCite(m, x)}
                title={m.sources?.find((s) => s.n === n)?.rel_path}
              />
            ) : (
              <span>[{n}]</span>
            );
          },
        }}
      >
        {linkCitations(m.content)}
      </ReactMarkdown>
      {m.streaming && (
        <span className="cursor" aria-hidden>
          ▌
        </span>
      )}
      {m.error && (
        <p className="error" role="alert">
          {m.error}
        </p>
      )}
      {!m.streaming && m.alsoConsulted && m.alsoConsulted.length > 0 && (
        <details className="muted">
          <summary>Also consulted ({m.alsoConsulted.length})</summary>
          {m.alsoConsulted.map((s) => (
            <div key={s.n}>
              <CitationChip n={s.n} onClick={(x) => onCite(m, x)} /> {s.rel_path} · p.{s.page}
            </div>
          ))}
        </details>
      )}
      {!m.streaming && m.content && (
        <div className="row actions">
          <button type="button" onClick={() => navigator.clipboard?.writeText(m.content)}>
            Copy
          </button>
          {m.debug && onDebug && (
            <button type="button" onClick={() => onDebug(m)}>
              Debug
            </button>
          )}
        </div>
      )}
    </div>
  );
}
