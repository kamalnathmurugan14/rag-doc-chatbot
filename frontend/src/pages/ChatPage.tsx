import { useCallback, useState } from "react";
import { api, type Debug, type Message, type Session, type Source } from "../api/client";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { IngestProgress } from "../components/IngestProgress";
import { ScopeSelector, scopeLabel, toScope } from "../components/ScopeSelector";
import { SessionList } from "../components/SessionList";
import { SourcePanel } from "../components/SourcePanel";
import { useAsync } from "../hooks/useAsync";
import { useChat } from "../hooks/useChat";
import { useOptions } from "../hooks/useOptions";

interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: { cited: Source[]; also_consulted: Source[] } | null;
  debug: Debug | null;
}

export function ChatPage() {
  const chat = useChat();
  const [options] = useOptions();
  const sessions = useAsync(() => api<{ sessions: Session[] }>("/sessions"), []);
  const [scope, setScope] = useState<string[]>([]);
  const [active, setActive] = useState<{ source: Source } | null>(null);
  const [debugMsg, setDebugMsg] = useState<Message | null>(null);

  const send = async (q: string) => {
    setActive(null);
    await chat.send(q, toScope(scope), options, chat.sessionId);
    sessions.reload();
  };
  const onCite = useCallback((m: Message, n: number) => {
    const s = [...(m.sources ?? [])].find((x) => x.n === n);
    if (s) {
      setDebugMsg(null);
      setActive({ source: s });
    }
  }, []);
  const open = async (id: number) => {
    const r = await api<{ messages: StoredMessage[] }>(`/sessions/${id}/messages?debug=true`);
    chat.load(
      id,
      r.messages.map((m) => ({
        id: `db${m.id}`,
        role: m.role,
        content: m.content,
        debug: m.debug ?? undefined,
        sources: m.citations ? [...m.citations.cited, ...m.citations.also_consulted] : undefined,
        citations: m.citations?.cited,
        alsoConsulted: m.citations?.also_consulted,
      })),
    );
    setActive(null);
    setDebugMsg(null);
  };
  const remove = async (id: number) => {
    await api(`/sessions/${id}`, { method: "DELETE" });
    if (id === chat.sessionId) chat.reset();
    sessions.reload();
  };

  return (
    <div className="three">
      <div className="pane left">
        <SessionList
          sessions={sessions.data?.sessions ?? []}
          activeId={chat.sessionId}
          onOpen={open}
          onNew={() => {
            chat.reset();
            setActive(null);
          }}
          onDelete={remove}
        />
        {sessions.error && (
          <p className="error" role="alert">
            {sessions.error}
          </p>
        )}
        <ScopeSelector selected={scope} onChange={setScope} />
        <h3>Index</h3>
        <IngestProgress compact />
      </div>
      <div className="pane center">
        <ChatWindow
          messages={chat.messages}
          busy={chat.busy}
          activeN={active?.source.n ?? null}
          scopeLabel={scopeLabel(scope)}
          onSend={send}
          onStop={chat.stop}
          onRegenerate={chat.regenerate}
          onCite={onCite}
          onDebug={(m) => {
            setActive(null);
            setDebugMsg(m);
          }}
        />
      </div>
      <div className="pane right">
        {active && <SourcePanel source={active.source} onClose={() => setActive(null)} />}
        {debugMsg && <DebugPanel m={debugMsg} onClose={() => setDebugMsg(null)} />}
        {!active && !debugMsg && (
          <p className="empty">
            Click a citation chip to read the source, or press “Debug” on an answer to see the retrieval.
          </p>
        )}
      </div>
    </div>
  );
}
