import React from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import SignalField from '@site/src/components/SignalField';
import styles from './index.module.css';

const SYSTEMS = [
  { num: '01', title: 'PitchBook → Attio Pipeline', to: '/docs/projects/pitchbook-attio',
    desc: 'Syncs deal, company, and investor data into Attio, with reliable investor linking.', status: 'Live' },
  { num: '02', title: 'Apollo Reach Out', to: '/docs/projects/apollo-reach-out',
    desc: 'Builds clean family office and RIA lists, enriches them, then loads outbound sequences.', status: 'Live' },
  { num: '03', title: 'Deal Intelligence', to: '/docs/projects/intelligence',
    desc: 'AI agents score every qualified deal against our rubric and deep-research the best.', status: 'Live' },
];

export default function Home() {
  return (
    <Layout title="AI Intelligence" description="ID8 Investments AI and automation hub">
      <main className={styles.page}>
        <div className={styles.kicker}>ID8 Investments  |  Applied AI</div>
        <h1 className={styles.headline}>Ambitious ideas,<br /><em>made legible.</em></h1>
        <p className={styles.lede}>
          The AI and automation systems ID8 runs across sourcing, diligence, and outreach.
          Each one lives here with what it does, how to use it, how it works, and where the code is.
        </p>
        <div className={styles.field}><SignalField seed="home-systems" /></div>
        <hr className={styles.rule} />
        <div className={styles.sectionLabel}>Systems</div>
        <div className={styles.grid}>
          {SYSTEMS.map(p => (
            <Link key={p.num} className={styles.card} to={p.to}>
              <div className={styles.cardNum}>{p.num}</div>
              <div className={styles.cardTitle}>{p.title}</div>
              <div className={styles.cardDesc}>{p.desc}</div>
              <div className={styles.cardStatus}>{p.status}</div>
            </Link>
          ))}
        </div>
      </main>
    </Layout>
  );
}
