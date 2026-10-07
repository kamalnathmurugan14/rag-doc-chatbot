import type { Session } from "../api/client";

interface Props {
  sessions: Session[];
  activeId: number | null;
  onOpen: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
}

export function SessionList({ sessions, activeId, onOpen, onNew, onDelete }: Props) {
  return (
    <section aria-label="Chats">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Chats</h3>
        <button type="button" onClick={onNew}>
          ＋ New
        </button>
      </div>
      {sessions.length === 0 && <p className="muted">No chats yet.</p>}
      <ul className="plain">
        {sessions.map((s) => (
          <li key={s.id} className="row">
            <button
              type="button"
              className={`chip${s.id === activeId ? " active" : ""}`}
              style={{ flex: 1, textAlign: "left" }}
              onClick={() => onOpen(s.id)}
            >
              {s.title}
            </button>
            <button type="button" aria-label={`Delete chat ${s.title}`} onClick={() => onDelete(s.id)}>
              🗑
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
