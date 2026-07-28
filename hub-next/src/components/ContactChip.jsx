'use client';

import { useState } from 'react';
import InlineTextField from './InlineTextField';
import styles from './ContactChip.module.css';

// Replaces the old avatar-circle + "Contact · Tracked by X" chip. `contacts`
// is the already-computed [{ name, email }] list (best-effort matched
// against the firm's raw Attio email export -- see lib/contactMatch.js);
// `attioUrl` links straight to the firm's own Attio company record.
// `contact`/`canEdit` are still the raw editable field + permission, kept
// behind a small "Edit names" toggle -- most of these firms are exactly as
// re-imported from Attio, but a few (e.g. 1789 Capital, trimmed to its 3
// actual working contacts) carry manual curation that has to stay editable.
export default function ContactChip({ endpoint, id, trackedBy, contact, contacts, attioUrl, canEdit }) {
  const [editing, setEditing] = useState(false);

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>Contacts</span>
        {attioUrl && (
          <a className={styles.attioLink} href={attioUrl} target="_blank" rel="noopener noreferrer">Attio ↗</a>
        )}
      </div>

      {contacts.length > 0 ? (
        <p className={styles.names}>
          {contacts.map((c, i) => (
            <span key={i}>
              {c.email ? <a href={`mailto:${c.email}`}>{c.name}</a> : c.name}
              {i < contacts.length - 1 ? ', ' : ''}
            </span>
          ))}
        </p>
      ) : (
        <p className={styles.empty}>No contact recorded</p>
      )}

      <p className={styles.tracked}>
        Tracked by <InlineTextField endpoint={endpoint} id={id} field="trackedBy" value={trackedBy} canEdit={canEdit} placeholder="partner" />
      </p>

      {canEdit && (
        editing ? (
          <div className={styles.editRow}>
            <InlineTextField endpoint={endpoint} id={id} field="contact" value={contact} canEdit={canEdit} placeholder="Add a contact" />
            <button type="button" className={styles.doneBtn} onClick={() => setEditing(false)}>Done</button>
          </div>
        ) : (
          <button type="button" className={styles.editBtn} onClick={() => setEditing(true)}>Edit names</button>
        )
      )}
    </div>
  );
}
