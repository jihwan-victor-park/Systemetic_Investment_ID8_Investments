// Replaces Docusaurus's `:::note` MDX admonition syntax with a plain JSX
// component. Styled from the ported `.theme-admonition*` rules in globals.css.
const HEADINGS = { note: 'Note', info: 'Info', tip: 'Tip', caution: 'Caution', danger: 'Danger' };

// Infima renders a small icon before every admonition label — this repo only
// ever uses `:::note`, so a single circle-i icon (Infima's note/info glyph)
// covers every real usage.
const ICONS = {
  note: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
      <line x1="12" y1="11" x2="12" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="12" cy="7.5" r="1.2" fill="currentColor" />
    </svg>
  ),
};

export default function Admonition({ type = 'note', children }) {
  return (
    <div className={`theme-admonition theme-admonition-${type}`}>
      <div className="theme-admonition-heading">
        {ICONS[type] || ICONS.note}
        <span>{HEADINGS[type] || type}</span>
      </div>
      <div>{children}</div>
    </div>
  );
}

export function Note({ children }) {
  return <Admonition type="note">{children}</Admonition>;
}
