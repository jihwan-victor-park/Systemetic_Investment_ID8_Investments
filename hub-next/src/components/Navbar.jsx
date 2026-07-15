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

  // The left sidebar (DocsShell) is the one place all of these live now --
  // no more duplicate tab strip up here, just the way in.
  const links = [{ href: '/investors', label: 'Investor View' }];

  return (
    <header className={styles.navbar}>
      <div className={styles.inner}>
        <div className={styles.left}>
          <Link href="/" className={styles.brand}>
            <img src="/img/logo_charcoal.png" alt="ID8 Investments" className={styles.logo} />
            {!hideInternalNav && <span className={styles.brandLabel}>Hub</span>}
          </Link>
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
