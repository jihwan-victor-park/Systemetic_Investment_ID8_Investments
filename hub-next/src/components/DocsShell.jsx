'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { getSidebarTree, getBreadcrumbs, containsPath, getPrevNext } from '@/data/sidebarConfig';
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
  const isActiveBranch = containsPath(item, pathname);

  // The accent rail should stop right after the item leading to the current
  // page, not run the full length of the list — split children into the
  // "on the way there" portion (rail) and everything after it (plain).
  const activeIdx = item.items.findIndex((child) => containsPath(child, pathname));
  const railItems = activeIdx >= 0 ? item.items.slice(0, activeIdx + 1) : item.items;
  const restItems = activeIdx >= 0 ? item.items.slice(activeIdx + 1) : [];

  return (
    <div className={styles.category}>
      <div className={styles.rail} data-active={isActiveBranch}>
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
        <div className={styles.categoryItemsWrapper} data-open={open}>
          <div className={styles.categoryItemsInner}>
            {railItems.map((child) => (
              <SidebarItem key={child.href || child.label} item={child} pathname={pathname} />
            ))}
          </div>
        </div>
      </div>
      {restItems.length > 0 && (
        <div className={styles.categoryItemsWrapper} data-open={open}>
          <div className={styles.categoryItemsInner}>
            {restItems.map((child) => (
              <SidebarItem key={child.href || child.label} item={child} pathname={pathname} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DocsShell({ companies = [], children }) {
  const pathname = usePathname();
  const tree = getSidebarTree(companies);
  const breadcrumbs = getBreadcrumbs(pathname, tree);
  const { prev, next } = getPrevNext(pathname, tree);
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

      {/* Docusaurus centers the content+TOC container within the space to the
          right of the fixed-width sidebar — it isn't packed flush against the
          sidebar, and it isn't centered on the full viewport either. */}
      <div className={styles.contentArea}>
        <div className={styles.contentInner}>
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
                      ) : b.href ? (
                        <Link href={b.href}>{b.label}</Link>
                      ) : (
                        <span>{b.label}</span>
                      )}
                    </span>
                  );
                })}
              </div>
            )}
            <div className="markdown" ref={contentRef}>
              {children}
            </div>

            {(prev || next) && (
              <div className={styles.pagination}>
                {prev ? (
                  <Link href={prev.href} className={styles.paginationLink} data-dir="prev">
                    <span className={styles.paginationLabel}>Previous</span>
                    <span className={styles.paginationTitle}>« {prev.label}</span>
                  </Link>
                ) : <span />}
                {next && (
                  <Link href={next.href} className={styles.paginationLink} data-dir="next">
                    <span className={styles.paginationLabel}>Next</span>
                    <span className={styles.paginationTitle}>{next.label} »</span>
                  </Link>
                )}
              </div>
            )}
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
      </div>
    </div>
  );
}
