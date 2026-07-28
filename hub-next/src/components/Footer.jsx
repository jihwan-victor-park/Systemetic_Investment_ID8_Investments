import Link from 'next/link';
import styles from './Footer.module.css';

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.top}>
          <Link href="/" className={styles.brand}>
            <img src="/img/logo_white.png" alt="ID8 Investments" className={styles.logo} />
          </Link>
        </div>

        <div className={styles.contact}>
          <div className={styles.contactLabel}>Get in touch</div>
          <a href="mailto:hello@id8investments.com" className={styles.email}>
            HELLO@ID8INVESTMENTS.COM
          </a>
        </div>

        <div className={styles.bottom}>
          <span className={styles.copyright}>&copy; {new Date().getFullYear()} ID8 Investments. All rights reserved.</span>
          <a
            href="https://www.linkedin.com/company/id8investments/posts/?feedView=all"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.social}
            aria-label="LinkedIn"
          >
            <svg viewBox="0 0 24 24" width="19" height="19" fill="currentColor" aria-hidden="true">
              <path d="M19 0h-14c-2.76 0-5 2.24-5 5v14c0 2.76 2.24 5 5 5h14c2.76 0 5-2.24 5-5v-14c0-2.76-2.24-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.27c-1 0-1.8-.81-1.8-1.8s.8-1.8 1.8-1.8 1.8.81 1.8 1.8-.8 1.8-1.8 1.8zm13.5 12.27h-3v-5.6c0-1.34-.03-3.07-1.87-3.07-1.87 0-2.16 1.46-2.16 2.97v5.7h-3v-11h2.88v1.5h.04c.4-.76 1.38-1.56 2.84-1.56 3.04 0 3.6 2 3.6 4.59v6.47z" />
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}
