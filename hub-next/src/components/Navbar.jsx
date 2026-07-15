'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import SignOutButton from './SignOutButton';
import styles from './Navbar.module.css';

export default function Navbar() {
  const pathname = usePathname();
  const isInvestorView = pathname.startsWith('/investors');
  const isAuthPage = ['/signin', '/pending', '/denied'].includes(pathname);
  const hideInternalNav = isInvestorView || isAuthPage;
  const showSignOut = !isAuthPage;
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

  const isInDocs = pathname.startsWith('/docs');

  // The left sidebar (DocsShell) is the one place all of these live now --
  // no more duplicate tab strip up here, just the one way in ("Hub", which
  // actually links into /docs, unlike the logo which goes to the landing page).
  const links = [
    ...(!hideInternalNav ? [{ href: '/docs/overview', label: 'Hub' }] : []),
    { href: '/investors', label: 'Investor View' },
  ];

  return (
    <header className={styles.navbar}>
      <div className={styles.inner}>
        <div className={styles.left}>
          <Link href="/" className={styles.brand}>
            <img src="/img/logo_charcoal.png" alt="ID8 Investments" className={styles.logo} />
          </Link>
          {!hideInternalNav && (
            <Link href="/docs/overview" className={`${styles.hubLink} ${isInDocs ? styles.hubLinkActive : ''}`}>
              Hub
            </Link>
          )}
        </div>
        <div className={styles.right}>
          <Link href="/investors" className={`${styles.link} ${isInvestorView ? styles.linkActive : ''}`}>
            Investor View
          </Link>
          {showSignOut && <SignOutButton className={styles.signOut} />}
        </div>
        <button
          type="button"
          className={styles.hamburger}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span data-open={menuOpen} />
          <span data-open={menuOpen} />
          <span data-open={menuOpen} />
        </button>
      </div>
      {menuOpen && (
        <div className={styles.mobileMenu}>
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`${styles.mobileLink} ${pathname.startsWith(l.href) ? styles.linkActive : ''}`}
            >
              {l.label}
            </Link>
          ))}
          {showSignOut && <SignOutButton className={styles.mobileLink} />}
        </div>
      )}
    </header>
  );
}
