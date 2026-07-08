// Normalizes two things the Docusaurus source did separately: the
// `<span className="status-pill status-live">Live</span>` HTML-in-markdown
// hack on the Overview table, and the homepage systems grid's own
// `.cardStatus[data-status]` dot — both rendered the same "uppercase label +
// colored square dot" idea with duplicated CSS. One component, one rule set.
const DOT_VAR = {
  Live: 'var(--id8-fresh-dot)',
  Beta: 'var(--id8-aging-dot)',
  Deprecated: 'var(--id8-stale-dot)',
};

export default function StatusPill({ status }) {
  return (
    <span className="status-pill">
      <span
        style={{
          display: 'inline-block',
          width: 8,
          height: 8,
          borderRadius: 2,
          marginRight: 6,
          background: DOT_VAR[status] || 'var(--id8-grey)',
        }}
      />
      {status}
    </span>
  );
}
