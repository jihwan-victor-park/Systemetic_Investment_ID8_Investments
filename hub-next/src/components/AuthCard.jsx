import styles from './AuthCard.module.css';

export default function AuthCard({ headline, children }) {
  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <img src="/img/logo_charcoal.png" alt="ID8 Investments" className={styles.logo} />
        <div className={styles.kicker}>Applied AI</div>
        <h1 className={styles.headline}>{headline}</h1>
        {children}
      </div>
    </main>
  );
}
