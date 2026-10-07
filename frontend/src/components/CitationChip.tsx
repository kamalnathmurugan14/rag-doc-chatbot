export function CitationChip({
  n,
  active,
  onClick,
  title,
}: {
  n: number;
  active?: boolean;
  onClick: (n: number) => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      className={`cite${active ? " active" : ""}`}
      onClick={() => onClick(n)}
      title={title}
      aria-label={`Open source ${n}`}
    >
      {n}
    </button>
  );
}
