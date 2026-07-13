'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import SignOutButton from './SignOutButton';
import styles from './Navbar.module.css';

const INTERNAL_LINKS = [
  { href: '/docs/overview', label: 'AI Capabilities' },
  { href: '/docs/projects/pitchbook-attio', label: 'Systems' },
  { href: '/docs/research', label: 'Research' },
  { href: '/docs/admin', label: 'Admin' },
];

export default function Navbar() {
  const pathname = usePathname();
  const isInvestorView = pathname === '/investors';
  const showSignOut = !['/signin', '/pending', '/denied'].includes(pathname);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

  const links = [
    ...(!isInvestorView ? INTERNAL_LINKS : []),
    { href: '/investors', label: 'Investor View' },
  ];

  return (
    <header className={styles.navbar}>
      <div className={styles.inner}>
        <div className={styles.left}>
          <Link href="/" className={styles.brand}>
            <img src="/img/logo_charcoal.png" alt="ID8 Investments" className={styles.logo} />
          </Link>
          {!isInvestorView &&
            INTERNAL_LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`${styles.link} ${pathname.startsWith(l.href) ? styles.linkActive : ''}`}
              >
                {l.label}
              </Link>
            ))}
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
