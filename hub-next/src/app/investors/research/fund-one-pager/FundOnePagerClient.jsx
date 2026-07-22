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

    // Draws the tech-supercycle chart's wave outlines in left-to-right,
    // like a pen (or a rollercoaster car) tracing the line -- each hump
    // a bit faster than the last, and the AI line snapping in fastest of
    // all, echoing the slide's own point that each wave arrives quicker
    // than the one before it. Purely a stroke-dashoffset/opacity reveal:
    // the underlying path data never changes, so it always lands on the
    // exact static chart. Tied directly to scroll position (not a timer)
    // so it moves at the pace of the user's own scroll -- scrub down to
    // draw more, scrub back up to undraw -- until it's fully drawn once,
    // at which point it latches and won't undraw again even if scrolled
    // back past. Skipped entirely under reduced motion, which leaves the
    // chart in its normal, already-fully-drawn state.
    const chartWrap = shadow.querySelector('.chart-wrap');
    let cleanupChartScroll;
    if (chartWrap && !reduceMotion) {
      const waveLines = Array.from(chartWrap.querySelectorAll('.wave-line'));
      const waveFills = Array.from(chartWrap.querySelectorAll('.wave-fill'));
      const aiLine = chartWrap.querySelector('.ai-line');
      const aiArrow = chartWrap.querySelector('.ai-arrow');
      const allLines = aiLine ? [...waveLines, aiLine] : waveLines;

      if (allLines.length) {
        const lengths = allLines.map((path) => path.getTotalLength());
        allLines.forEach((path, i) => {
          path.style.strokeDasharray = String(lengths[i]);
        });

        // Each path's "peak" -- the arc-length fraction where it stops
        // climbing and starts descending (1 for the AI line, which never
        // comes back down). Used below to pace the climb and the drop
        // differently instead of a single uniform ease.
        const SAMPLES = 40;
        const peakFractions = allLines.map((path, i) => {
          const len = lengths[i];
          if (!len) return 1;
          let minY = Infinity;
          let peakF = 1;
          for (let s = 0; s <= SAMPLES; s++) {
            const f = s / SAMPLES;
            const y = path.getPointAtLength(f * len).y;
            if (y < minY) {
              minY = y;
              peakF = f;
            }
          }
          return peakF;
        });

        // Relative weights -- same shape as a timer would have used (each
        // era a bit quicker than the last), now expressed as fractions of
        // the overall scroll-driven timeline instead of milliseconds.
        const segWeights = [170, 144, 122, 104, 88, 74, 60].slice(0, allLines.length);
        const overlapWeight = 18;
        const starts = [];
        let cursor = 0;
        segWeights.forEach((w) => {
          starts.push(cursor);
          cursor += w - overlapWeight;
        });
        const totalWeight = cursor + overlapWeight;
        const segStartFracs = starts.map((s) => s / totalWeight);
        const segDurFracs = segWeights.map((w) => w / totalWeight);

        // Climb slow with a launch feel (accelerating into the crest), then
        // drop fast (quick rush, easing off at the bottom) -- a rollercoaster
        // pace rather than one uniform speed across the whole hump. The AI
        // line has no drop (its peak is at the very end), so it spends its
        // entire segment on the climb: a slow build that launches right as
        // the arrowhead lands.
        const CLIMB_SHARE = 0.68;
        const easeInCubic = (x) => x * x * x;
        const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3);
        function archFraction(segT, peakF) {
          if (peakF >= 1) return easeInCubic(segT);
          if (segT <= CLIMB_SHARE) {
            return peakF * easeInCubic(segT / CLIMB_SHARE);
          }
          const local = (segT - CLIMB_SHARE) / (1 - CLIMB_SHARE);
          return peakF + (1 - peakF) * easeOutCubic(local);
        }

        function render(progress) {
          allLines.forEach((path, i) => {
            const segT = Math.min(1, Math.max(0, (progress - segStartFracs[i]) / segDurFracs[i]));
            const eased = archFraction(segT, peakFractions[i]);
            path.style.strokeDashoffset = String(lengths[i] * (1 - eased));
            const fill = i < waveFills.length ? waveFills[i] : aiArrow;
            if (fill) fill.style.opacity = String(eased);
          });
        }
        render(0);

        // The scroll distance the chart takes to go from "just entering
        // the bottom of the viewport" to "mostly scrolled up past a third
        // of it" -- roughly half a screen's worth of scrolling -- maps to
        // progress 0 -> 1, so it moves at the reader's own pace rather
        // than snapping open on a fixed timer.
        let everCompleted = false;
        let ticking = false;
        function computeAndRender() {
          ticking = false;
          if (everCompleted) return;
          const rect = chartWrap.getBoundingClientRect();
          const vh = window.innerHeight || document.documentElement.clientHeight;
          const startY = vh * 0.85;
          const endY = vh * 0.3;
          const progress = Math.min(1, Math.max(0, (startY - rect.top) / (startY - endY)));
          if (progress >= 1) {
            everCompleted = true;
            render(1);
            window.removeEventListener('scroll', onScroll);
            window.removeEventListener('resize', onScroll);
            return;
          }
          render(progress);
        }
        function onScroll() {
          if (ticking) return;
          ticking = true;
          requestAnimationFrame(computeAndRender);
        }

        computeAndRender();
        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', onScroll);
        cleanupChartScroll = () => {
          window.removeEventListener('scroll', onScroll);
          window.removeEventListener('resize', onScroll);
        };
      }
    }

    return () => {
      revealObserver.disconnect();
      countObserver.disconnect();
      if (cleanupChartScroll) cleanupChartScroll();
    };
  }, []);

  return <div ref={hostRef} />;
}
