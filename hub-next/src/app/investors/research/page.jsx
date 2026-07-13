import styles from '../page.module.css';

export const metadata = { title: 'Research', description: "ID8's research view for approved investors" };

// Gated to the 'investor' role by middleware (src/auth.config.js). Placeholder
// for now -- deal summaries, company list, and sourcing narrative land here
// once that content model is built; this just proves the access gate works
// end to end for an approved external account.
export default function InvestorResearch() {
  return (
    <main className={styles.page}>
      <div className={styles.kicker}>ID8 Investments&nbsp;&nbsp;|&nbsp;&nbsp;Applied AI</div>
      <h1 className={styles.headline}>You&apos;re in.</h1>
      <p className={styles.lede}>
        Thanks for your patience — this is where ID8&apos;s deal summaries, company list, and
        sourcing narrative will live for approved investors. That view is still being built;
        for now, this page just confirms your account has research access.
      </p>
    </main>
  );
}
