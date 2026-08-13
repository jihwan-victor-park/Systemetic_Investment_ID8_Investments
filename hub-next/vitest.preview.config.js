import { defineConfig } from 'vitest/config';
import path from 'node:path';

// Config for the standalone dashboard preview generator only (see
// scripts/preview-dashboard.jsx for why it exists). Kept separate from
// vitest.config.js so `npm test` never picks up a generator that writes files as
// if it were a unit test -- that config's `include` is deliberately narrow to
// src/**/*.test.js.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['scripts/preview-*.jsx'],
    // Without this, vitest's default (css: false) makes every `styles.foo` read
    // undefined, so the rendered HTML carries NO class names and the preview is
    // an unstyled bullet list -- which looks like a broken stylesheet rather
    // than a broken config. 'non-scoped' emits each class as its own plain
    // name, exactly matching the raw .module.css selectors the preview inlines.
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
