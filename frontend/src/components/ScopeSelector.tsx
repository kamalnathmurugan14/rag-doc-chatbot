import type { Scope } from "../api/client";
import { FileExplorer } from "./FileExplorer";

export const toScope = (sel: string[]): Scope => ({
  files: sel.filter((p) => !p.endsWith("/")),
  folders: sel.filter((p) => p.endsWith("/")).map((p) => p.slice(0, -1)),
});
export const scopeLabel = (sel: string[]) =>
  sel.length === 0 ? "all indexed documents" : `${sel.length} selected file(s)/folder(s)`;

export function ScopeSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (s: string[]) => void;
}) {
  return (
    <section aria-label="Scope">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Scope</h3>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])}>
            Clear
          </button>
        )}
      </div>
      <p className="muted">{scopeLabel(selected)}</p>
      <FileExplorer selectable selected={selected} onSelectionChange={onChange} />
    </section>
  );
}
