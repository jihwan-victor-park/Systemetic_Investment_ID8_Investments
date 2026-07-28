import Link from 'next/link';
import styles from './Footer.module.css';

// Internal-tool footer -- deliberately minimal. No "Get in touch"/email/
// LinkedIn (that's marketing-site content, not relevant inside the app
// itself, per Oscar's explicit call 2026-07-28) -- just the mark and a
// copyright line, small.
export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand}>
          <img src="/img/logo_white.png" alt="ID8 Investments" className={styles.logo} />
        </Link>
        <span className={styles.copyright}>&copy; {new Date().getFullYear()} ID8 Investments</span>
      </div>
    </footer>
  );
}
