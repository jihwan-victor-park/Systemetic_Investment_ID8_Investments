import InlineTextField from './InlineTextField';
import styles from './ContactChip.module.css';

function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '—';
  return parts.slice(0, 3).map((w) => w[0]).join('').toUpperCase();
}

// Gmail-style contact card: an avatar (initials of the actual person) next
// to a small "Contact · Tracked by X" label and the contact's name --
// rather than two bare inline fields side by side. Both trackedBy and
// contact stay independently editable (embedded InlineTextFields), this is
// just the display shell around them.
export default function ContactChip({ endpoint, id, trackedBy, contact, canEdit }) {
  return (
    <div className={styles.chip}>
      <div className={styles.avatar}>{initials(contact)}</div>
      <div className={styles.meta}>
        <div className={styles.label}>
          Contact · Tracked by <InlineTextField endpoint={endpoint} id={id} field="trackedBy" value={trackedBy} canEdit={canEdit} placeholder="partner" />
        </div>
        <div className={styles.name}>
          <InlineTextField endpoint={endpoint} id={id} field="contact" value={contact} canEdit={canEdit} placeholder="Add a contact" />
        </div>
      </div>
    </div>
  );
}
