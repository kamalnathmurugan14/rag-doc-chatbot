import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Debug, Message, Source } from "../api/client";
import { ChatWindow } from "./ChatWindow";
import { DebugPanel } from "./DebugPanel";
import { FileExplorer } from "./FileExplorer";
import { MessageBubble, linkCitations } from "./MessageBubble";
import { SessionList } from "./SessionList";
import { toScope } from "./ScopeSelector";

afterEach(() => vi.restoreAllMocks());

const src = (n: number): Source => ({
  n,
  chunk_id: `1:${n}`,
  rel_path: `docs/f${n}.txt`,
  page: 1,
  similarity: 0.8,
  rerank: null,
  snippet: "s",
});
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

describe("citations", () => {
  it("linkCitations rewrites [n] into links", () => {
    expect(linkCitations("A [1] and [2][3].")).toBe("A [1](#cite-1) and [2](#cite-2)[3](#cite-3).");
  });
  it("renders known citations as chips, unknown ones as plain text, and opens the source", async () => {
    const onCite = vi.fn();
    const m: Message = {
      id: "a",
      role: "assistant",
      content: "Leave is 24 days [1] and more [7].",
      sources: [src(1), src(2)],
    };
    render(<MessageBubble m={m} onCite={onCite} />);
    await userEvent.click(screen.getByRole("button", { name: "Open source 1" }));
    expect(onCite).toHaveBeenCalledWith(m, 1);
    expect(screen.queryByRole("button", { name: "Open source 7" })).toBeNull();
    expect(screen.getByText("[7]")).toBeInTheDocument();
  });
  it("shows the rewritten query, streaming cursor and 'also consulted'", () => {
    const m: Message = {
      id: "a",
      role: "assistant",
      content: "hi",
      rewritten: "standalone q",
      streaming: true,
      alsoConsulted: [src(2)],
    };
    render(<MessageBubble m={m} onCite={() => {}} />);
    expect(screen.getByText(/standalone q/)).toBeInTheDocument();
    expect(screen.queryByText(/Also consulted/)).toBeNull(); // hidden while streaming
  });
  it("user bubbles are plain", () => {
    render(<MessageBubble m={{ id: "u", role: "user", content: "question?" }} onCite={() => {}} />);
    expect(screen.getByText("question?")).toBeInTheDocument();
  });
});

describe("ChatWindow", () => {
  const base = {
    activeN: null,
    onRegenerate: () => {},
    onCite: () => {},
    onDebug: () => {},
    scopeLabel: "all indexed documents",
  };
  it("sends on submit and shows the empty state", async () => {
    const onSend = vi.fn();
    render(<ChatWindow {...base} messages={[]} busy={false} onSend={onSend} onStop={() => {}} />);
    expect(screen.getByText(/Ask a question/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Your question"), "hello{enter}");
    expect(onSend).toHaveBeenCalledWith("hello");
  });
  it("shows Stop while busy", async () => {
    const onStop = vi.fn();
    render(<ChatWindow {...base} messages={[]} busy onSend={() => {}} onStop={onStop} />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalled();
    expect(screen.getByLabelText("Your question")).toBeDisabled();
  });
});

describe("DebugPanel / SessionList / scope", () => {
  const debug: Debug = {
    query: "q",
    rewritten_query: "standalone",
    fetched: 6,
    below_min_similarity: 2,
    stages: ["similarity", "mmr"],
    rerank: "off",
    embedder: "x",
    timings_ms: { embed_ms: 1.5 },
    options: { top_k: 3, mmr: true, rerank: false, min_similarity: 0.25 },
    sources: [src(1)],
    prompt: "THE PROMPT",
    dropped_for_budget: ["1:9"],
    usage: { tokens_in: 10, tokens_out: 5 },
    history_turns: 1,
  };
  it("shows retrieval details and the dropped chunks warning", () => {
    render(<DebugPanel m={{ id: "a", role: "assistant", content: "", debug }} onClose={() => {}} />);
    expect(screen.getByText("standalone")).toBeInTheDocument();
    expect(screen.getByText(/similarity → mmr/)).toBeInTheDocument();
    expect(screen.getByText(/Dropped to fit/)).toBeInTheDocument();
    expect(screen.getByText("0.800")).toBeInTheDocument();
  });
  it("lists sessions, opens and deletes", async () => {
    const onOpen = vi.fn(),
      onDelete = vi.fn();
    render(
      <SessionList
        sessions={[{ id: 4, title: "Leave policy", created_at: "" }]}
        activeId={null}
        onOpen={onOpen}
        onNew={() => {}}
        onDelete={onDelete}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Leave policy" }));
    await userEvent.click(screen.getByRole("button", { name: /Delete chat/ }));
    expect(onOpen).toHaveBeenCalledWith(4);
    expect(onDelete).toHaveBeenCalledWith(4);
  });
  it("toScope splits files and folders", () => {
    expect(toScope(["a.txt", "hr/", "x/y.md"])).toEqual({ files: ["a.txt", "x/y.md"], folders: ["hr"] });
  });
});

describe("FileExplorer scope checkboxes", () => {
  const tree = {
    path: "",
    entries: [
      { name: "hr", type: "dir", size: 0, modified: "2026-01-01T00:00:00+00:00", path: "hr" },
      { name: "a.txt", type: "file", size: 10, modified: "2026-01-01T00:00:00+00:00", path: "a.txt" },
    ],
  };
  it("selects folders with a trailing slash and files by path", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json(tree));
    const onSel = vi.fn();
    render(<FileExplorer selectable selected={[]} onSelectionChange={onSel} />);
    await userEvent.click(await screen.findByLabelText("Select hr"));
    expect(onSel).toHaveBeenCalledWith(["hr/"]);
    await userEvent.click(screen.getByLabelText("Select a.txt"));
    expect(onSel).toHaveBeenLastCalledWith(["a.txt"]);
  });
});
