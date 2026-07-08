// Replaces Docusaurus's `:::note` MDX admonition syntax with a plain JSX
// component. Styled from the ported `.theme-admonition*` rules in globals.css.
const HEADINGS = { note: 'Note', info: 'Info', tip: 'Tip', caution: 'Caution', danger: 'Danger' };

export default function Admonition({ type = 'note', children }) {
  return (
    <div className={`theme-admonition theme-admonition-${type}`}>
      <div className="theme-admonition-heading">{HEADINGS[type] || type}</div>
      <div>{children}</div>
    </div>
  );
}

export function Note({ children }) {
  return <Admonition type="note">{children}</Admonition>;
}
