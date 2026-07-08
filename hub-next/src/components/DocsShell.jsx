'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { getSidebarTree, getBreadcrumbs, containsPath } from '@/data/sidebarConfig';
import styles from './DocsShell.module.css';

function SidebarItem({ item, pathname }) {
  const [open, setOpen] = useState(() => !item.collapsed || containsPath(item, pathname));

  useEffect(() => {
    if (containsPath(item, pathname)) setOpen(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (item.type === 'doc') {
    const active = pathname === item.href;
    return (
      <Link href={item.href} className={`menu__link ${active ? 'menu__link--active' : ''}`}>
        {item.label}
      </Link>
    );
  }

  // category — every category is collapsible with a chevron; `collapsed`
  // only controls the initial open state (Projects/Research start open,
  // Companies starts closed), matching how Docusaurus actually renders them.
  const chevron = (
    <span className={styles.chevron} data-open={open} aria-hidden="true">›</span>
  );
  return (
    <div className={styles.category}>
      {item.href ? (
        <div className={styles.categoryRow}>
          <Link href={item.href} className={styles.categoryLink}>{item.label}</Link>
          <button
            type="button"
            className={styles.chevronBtn}
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Collapse' : 'Expand'}
          >
            {chevron}
          </button>
        </div>
      ) : (
        <button type="button" className={styles.categoryRow} onClick={() => setOpen((v) => !v)}>
          <span className={styles.categoryLabelText}>{item.label}</span>
          {chevron}
        </button>
      )}
      {open && (
        <div className={styles.categoryItems}>
          {item.items.map((child) => (
            <SidebarItem key={child.href || child.label} item={child} pathname={pathname} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocsShell({ companies = [], children }) {
  const pathname = usePathname();
  const tree = getSidebarTree(companies);
  const breadcrumbs = getBreadcrumbs(pathname, tree);
  const contentRef = useRef(null);
  const [toc, setToc] = useState([]);
  const [activeId, setActiveId] = useState(null);

  useEffect(() => {
    const container = contentRef.current;
    if (!container) return undefined;
    const headings = Array.from(container.querySelectorAll('h2[id], h3[id]'));
    setToc(headings.map((h) => ({ id: h.id, text: h.textContent, level: h.tagName === 'H3' ? 3 : 2 })));
    if (!headings.length) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) setActiveId(visible[0].target.id);
      },
      { rootMargin: '0px 0px -70% 0px', threshold: 1.0 },
    );
    headings.forEach((h) => observer.observe(h));
    return () => observer.disconnect();
  }, [pathname]);

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <nav>
          {tree.map((item) => (
            <SidebarItem key={item.href || item.label} item={item} pathname={pathname} />
          ))}
        </nav>
      </aside>

      <main className={styles.main}>
        {breadcrumbs.length > 0 && (
          <div className={styles.breadcrumbs}>
            <Link href="/" className={styles.homeLink} aria-label="Home">⌂</Link>
            {breadcrumbs.map((b, i) => {
              const isLast = i === breadcrumbs.length - 1;
              return (
                <span key={b.href || b.label}>
                  <span className={styles.crumbSep}>›</span>
                  {isLast ? (
                    <span className={styles.crumbCurrent}>{b.label}</span>
                  ) : (
                    <Link href={b.href}>{b.label}</Link>
                  )}
                </span>
              );
            })}
          </div>
        )}
        <div className="markdown" ref={contentRef}>
          {children}
        </div>
      </main>

      {toc.length > 0 && (
        <aside className={styles.toc}>
          <div className={styles.tocTitle}>On this page</div>
          <ul className={`table-of-contents ${styles.tocList}`}>
            {toc.map((t) => (
              <li key={t.id} style={{ marginLeft: t.level === 3 ? '0.8rem' : 0 }}>
                <a
                  href={`#${t.id}`}
                  className={`table-of-contents__link ${activeId === t.id ? 'table-of-contents__link--active' : ''}`}
                >
                  {t.text}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
