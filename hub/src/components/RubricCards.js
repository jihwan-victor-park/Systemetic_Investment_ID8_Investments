import React, { useState } from 'react';
import styles from './RubricCards.module.css';

const ITEMS = [
  {
    label: 'Round Dynamics',
    blurb: 'Who is leading, and whether the structure shows real conviction.',
    detail: 'We look at who actually wrote the lead check, how the round came together, and '
      + 'whether the people closest to the company are backing it with real capital. An inside '
      + 'round or a passive syndicate scores very differently than a new, top-tier lead writing '
      + 'a real check.',
    icon: (
      <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
        <circle cx="7" cy="11" r="3.2" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="17" cy="5" r="1.8" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="17" cy="17" r="1.8" stroke="currentColor" strokeWidth="1.4" />
        <line x1="9.6" y1="9.4" x2="15.3" y2="6" stroke="currentColor" strokeWidth="1.2" />
        <line x1="9.6" y1="12.6" x2="15.3" y2="16" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    ),
  },
  {
    label: 'AI Depth',
    blurb: 'How central artificial intelligence actually is to the product, not the pitch.',
    detail: 'Plenty of pitches say "AI-powered." We look at whether the model is actually core '
      + 'to the product and the moat, or just a feature bolted onto a familiar business. The '
      + 'difference shows up in the architecture, not the deck.',
    icon: (
      <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
        <rect x="6" y="6" width="10" height="10" stroke="currentColor" strokeWidth="1.4" transform="rotate(45 11 11)" />
        <circle cx="11" cy="11" r="1.3" fill="currentColor" />
      </svg>
    ),
  },
  {
    label: 'Fundamentals',
    blurb: 'Revenue, growth, retention, and burn, read against what the stage demands.',
    detail: 'Revenue, growth rate, retention, and burn, benchmarked against what is actually '
      + 'normal for the stage, not against the founder’s own story. A growth chart only '
      + 'matters if the unit economics behind it hold up.',
    icon: (
      <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
        <line x1="5" y1="17" x2="5" y2="13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="11" y1="17" x2="11" y2="9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="17" y1="17" x2="17" y2="5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    label: 'Return Potential',
    blurb: 'What multiple is realistically in play, and how much downside sits underneath it.',
    detail: 'We size the realistic outcome range for this check: the multiple if it works, and '
      + 'the odds and severity of it not working. A good story is not enough if the math caps '
      + 'the upside or exposes too much downside.',
    icon: (
      <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
        <polyline points="4,16 9,10 13,13 18,5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points="13,5 18,5 18,10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: 'Terms',
    blurb: 'Whether the structure and rights are fair, not just favorable to the round.',
    detail: 'Carry, fees, structure, and rights, read the way a fiduciary should read them. A '
      + 'great company can still be a bad investment if the terms quietly work against the '
      + 'people writing the check.',
    icon: (
      <svg viewBox="0 0 22 22" fill="none" aria-hidden="true">
        <rect x="5" y="3.5" width="12" height="15" stroke="currentColor" strokeWidth="1.3" />
        <line x1="7.5" y1="8" x2="14.5" y2="8" stroke="currentColor" strokeWidth="1.1" />
        <line x1="7.5" y1="11" x2="14.5" y2="11" stroke="currentColor" strokeWidth="1.1" />
        <line x1="7.5" y1="14" x2="12" y2="14" stroke="currentColor" strokeWidth="1.1" />
      </svg>
    ),
  },
];

export default function RubricCards() {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div className={styles.grid} role="tablist" aria-label="ID8 deal-scoring rubric">
        {ITEMS.map((item, i) => (
          <button
            key={item.label}
            type="button"
            role="tab"
            aria-selected={active === i}
            className={`${styles.card} ${active === i ? styles.active : ''}`}
            onClick={() => setActive(i)}
          >
            <span className={styles.num}>{String(i + 1).padStart(2, '0')}</span>
            <span className={styles.icon}>{item.icon}</span>
            <span className={styles.label}>{item.label}</span>
            <span className={styles.blurb}>{item.blurb}</span>
          </button>
        ))}
      </div>
      <div className={styles.detailPanel}>
        <span className={styles.detailNum}>{String(active + 1).padStart(2, '0')}</span>
        <p key={active} className={styles.detailText}>{ITEMS[active].detail}</p>
      </div>
    </div>
  );
}
