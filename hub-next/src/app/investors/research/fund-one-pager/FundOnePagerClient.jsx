'use client';

import { useEffect, useRef } from 'react';
import { PAGE_CSS, BODY_HTML } from './content.js';

// Renders the ported one-pager inside a Shadow DOM so its (fairly aggressive,
// document-level) CSS reset -- *{...}, :host{...} standing in for the
// original body{...} -- can never leak into or be leaked into by the rest of
// the hub's styles. The markup itself is untouched from the original export
// except for one thing: the saved HTML had every .reveal element's scroll-
// triggered 'in' class already baked in (an artifact of "Save As" capturing
// the DOM mid-scroll), which silently neutered the reveal-on-scroll effect
// the page was actually designed with. content.js strips that back out, and
// the IntersectionObserver below re-attaches the exact same behavior the
// original inline <script> had (scripts inside innerHTML never execute, so
// it has to be reattached here instead of just carried over as markup).
//
// On top of that, this adds a count-up animation for the numeric stat/deal
// callouts ($50MM, 4–6x, 14.3x, etc.) and a few CSS-only hover treatments
// (already appended into content.js's PAGE_CSS) -- kept subtle and only
// active once a stat scrolls into view, so the page still reads as a
// professional LP one-pager rather than a demo of animation effects.
export default function FundOnePagerClient() {
  const hostRef = useRef(null);

  useEffect(() => {
    const hostEl = hostRef.current;
    if (!hostEl) return;
    const shadow = hostEl.shadowRoot || hostEl.attachShadow({ mode: 'open' });
    shadow.innerHTML = `<style>${PAGE_CSS}</style>${BODY_HTML}`;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 },
    );
    shadow.querySelectorAll('.reveal').forEach((el) => revealObserver.observe(el));

    // Counts up to whatever number is already in the element's text -- e.g.
    // "$50MM" -> animates "$0MM" to "$50MM", "4–6x" -> "4–0x" to "4–6x"
    // (only the trailing number in a range moves). Elements with no digit at
    // all ("Post Series A") are left untouched. Always lands on the exact
    // original string, never a rounding artifact of the animation itself.
    function animateCountUp(el) {
      const text = el.textContent;
      const match = text.match(/(\d[\d,]*\.?\d*)(?!.*\d)/);
      if (!match) return;
      const numStr = match[1];
      const target = parseFloat(numStr.replace(/,/g, ''));
      if (!Number.isFinite(target)) return;
      const decimals = numStr.includes('.') ? numStr.split('.')[1].length : 0;
      const prefix = text.slice(0, match.index);
      const suffix = text.slice(match.index + numStr.length);
      if (reduceMotion) return; // leave the real text as-is, no motion
      const duration = 1100;
      const start = performance.now();
      function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = prefix + (target * eased).toFixed(decimals) + suffix;
        if (t < 1) requestAnimationFrame(frame);
        else el.textContent = prefix + numStr + suffix;
      }
      requestAnimationFrame(frame);
    }

    const countObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCountUp(entry.target);
            countObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 },
    );
    shadow.querySelectorAll('.stat .v, .statcard .big').forEach((el) => countObserver.observe(el));

    return () => {
      revealObserver.disconnect();
      countObserver.disconnect();
    };
  }, []);

  return <div ref={hostRef} />;
}
