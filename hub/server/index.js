// Serves the built Docusaurus site (../build) behind a Google Workspace sign-in
// gate, EXCEPT the /investors page, which stays public.
//
// Why this can't be "serve /docs/** behind auth, allow /assets/** through":
// Docusaurus code-splits per-route content into individually-hashed chunks
// under /assets/js/, sitting alongside genuinely shared framework chunks in
// the SAME directory. A confidential research page's rendered text ships in
// one of those chunks (verified: the Warp screen's announcement text is
// byte-for-byte inside assets/js/1d9892b2.*.js). Allowing /assets/js/** would
// leak every gated page's content even with the HTML route itself gated.
//
// So the public allow-list is built from two authoritative, build-derived
// sources instead of a hand-maintained guess:
//   1. The actual <script>/<link> tags Docusaurus put in
//      build/investors/index.html -- the framework/runtime/CSS the page
//      needs on first paint.
//   2. .docusaurus/routesChunkNames.json -- Docusaurus's own route -> chunk
//      map, which reveals the chunk(s) React lazy-loads for that route after
//      hydration (the page's own component code, its plugin context, etc.),
//      which never appear as static tags in the HTML at all.
// Verified empirically (see hub/AUTH_SETUP.md) that neither source pulls in
// any other route's content chunk. Font files are allow-listed separately,
// in bulk, since they're binary glyph data that can't carry page content
// regardless of which route references them.
const fs = require('fs');
const path = require('path');
const express = require('express');
const cookieParser = require('cookie-parser');
const admin = require('firebase-admin');

admin.initializeApp();

const BUILD_DIR = path.join(__dirname, 'build');
const ALLOWED_DOMAIN = 'id8investments.com';
const SESSION_COOKIE = '__session';
const SESSION_MAX_AGE_MS = 5 * 24 * 60 * 60 * 1000; // 5 days
const PUBLIC_ROUTE = '/investors';

// The Firebase Web API key is not a secret (Firebase's own security model
// assumes it's public), but it still shouldn't sit in a committed file --
// keeping it as a Cloud Run env var means rotating it never touches git.
const FIREBASE_WEB_API_KEY = process.env.FIREBASE_WEB_API_KEY;
if (!FIREBASE_WEB_API_KEY) {
  throw new Error('Refusing to start: FIREBASE_WEB_API_KEY env var is not set.');
}
const LOGIN_HTML = fs.readFileSync(path.join(__dirname, 'login.html'), 'utf8')
  .replace('__FIREBASE_WEB_API_KEY__', FIREBASE_WEB_API_KEY);

function publicAssetPathsFromPage(htmlRelPath) {
  const html = fs.readFileSync(path.join(BUILD_DIR, htmlRelPath), 'utf8');
  const paths = new Set();
  const attrRe = /(?:src|href)="(\/[^"]+\.(?:js|css|png|svg|ico))"/g;
  let m;
  while ((m = attrRe.exec(html))) paths.add(m[1]);
  return paths;
}

function collectStrings(value, out = new Set()) {
  if (typeof value === 'string') out.add(value);
  else if (Array.isArray(value)) value.forEach((v) => collectStrings(v, out));
  else if (value && typeof value === 'object') Object.values(value).forEach((v) => collectStrings(v, out));
  return out;
}

// routesChunkNames.json keys the route with a trailing content hash
// ("/investors-327") that can change on rebuild, so match by prefix rather
// than hardcoding the full key.
function publicLazyChunkPaths(routePrefix) {
  const manifestPath = path.join(__dirname, 'routesChunkNames.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const routeKey = Object.keys(manifest).find((k) => k === routePrefix || k.startsWith(`${routePrefix}-`));
  if (!routeKey) {
    throw new Error(`Refusing to start: no routesChunkNames.json entry for route "${routePrefix}".`);
  }
  const chunkIds = collectStrings(manifest[routeKey]);
  const jsDir = path.join(BUILD_DIR, 'assets', 'js');
  const allFiles = fs.readdirSync(jsDir);
  const paths = new Set();
  for (const id of chunkIds) {
    for (const f of allFiles) {
      if (f.startsWith(`${id}.`) && f.endsWith('.js')) paths.add(`/assets/js/${f}`);
    }
  }
  return paths;
}

const PUBLIC_ASSET_PATHS = new Set([
  ...publicAssetPathsFromPage(`${PUBLIC_ROUTE.slice(1)}/index.html`),
  ...publicLazyChunkPaths(PUBLIC_ROUTE),
]);

// Defensive: if a future edit to investors.js ever pulls in a direct link to
// a generated document, refuse to boot rather than silently serve it.
for (const p of PUBLIC_ASSET_PATHS) {
  if (p.startsWith('/assets/files/')) {
    throw new Error(
      `Refusing to start: investors page references ${p}, which looks like a ` +
      `generated document, not a shared UI asset. Check what changed in investors.js.`
    );
  }
}

console.log(`Public asset allow-list (derived from ${PUBLIC_ROUTE} + routesChunkNames.json):`, [...PUBLIC_ASSET_PATHS]);

const PUBLIC_ROUTE_PATTERNS = [
  /^\/investors\/?$/,
  /^\/login\/?$/,
  /^\/fonts\/[^/]+$/,        // static/fonts/*.ttf -- glyph data, never page content
  /^\/assets\/fonts\/[^/]+$/, // Infima/theme fonts referenced from the shared CSS
];

function isPublicPath(urlPath) {
  if (PUBLIC_ASSET_PATHS.has(urlPath)) return true;
  return PUBLIC_ROUTE_PATTERNS.some((re) => re.test(urlPath));
}

function isEmailAllowed(decoded) {
  const email = decoded.email || '';
  const domain = email.split('@')[1] || '';
  return decoded.email_verified === true && domain.toLowerCase() === ALLOWED_DOMAIN;
}

// Only ever redirect to a same-origin relative path -- an unvalidated
// `redirect` param would otherwise be an open redirect.
function safeRedirectTarget(target) {
  if (typeof target === 'string' && /^\/(?!\/)/.test(target) && !target.includes('://')) {
    return target;
  }
  return '/';
}

const app = express();
app.disable('x-powered-by');
app.use(express.json());
app.use(cookieParser());

app.get('/login', (req, res) => {
  res.type('html').send(LOGIN_HTML);
});

app.post('/sessionLogin', async (req, res) => {
  const { idToken } = req.body || {};
  if (!idToken) return res.status(400).json({ error: 'missing-id-token' });
  try {
    const decoded = await admin.auth().verifyIdToken(idToken);
    if (!isEmailAllowed(decoded)) {
      return res.status(403).json({ error: 'not-id8-account' });
    }
    const sessionCookie = await admin.auth().createSessionCookie(idToken, {
      expiresIn: SESSION_MAX_AGE_MS,
    });
    res.cookie(SESSION_COOKIE, sessionCookie, {
      maxAge: SESSION_MAX_AGE_MS,
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      path: '/',
    });
    res.json({ ok: true });
  } catch (err) {
    console.error('sessionLogin failed:', err.message);
    res.status(401).json({ error: 'invalid-token' });
  }
});

app.get('/logout', (req, res) => {
  res.clearCookie(SESSION_COOKIE, { path: '/' });
  res.redirect('/login');
});

// Everything below this line is gated by default.
app.use(async (req, res, next) => {
  if (isPublicPath(req.path)) return next();

  const cookie = req.cookies[SESSION_COOKIE];
  if (!cookie) {
    return res.redirect(`/login?redirect=${encodeURIComponent(safeRedirectTarget(req.originalUrl))}`);
  }
  try {
    const decoded = await admin.auth().verifySessionCookie(cookie, true /* checkRevoked */);
    if (!isEmailAllowed(decoded)) {
      res.clearCookie(SESSION_COOKIE, { path: '/' });
      return res.redirect('/login?error=not-id8-account');
    }
    req.user = decoded;
    return next();
  } catch (err) {
    res.clearCookie(SESSION_COOKIE, { path: '/' });
    return res.redirect(`/login?redirect=${encodeURIComponent(safeRedirectTarget(req.originalUrl))}`);
  }
});

app.use(express.static(BUILD_DIR, { extensions: ['html'] }));

app.use((req, res) => {
  res.status(404).sendFile(path.join(BUILD_DIR, '404.html'));
});

const port = process.env.PORT || 8080;
app.listen(port, () => console.log(`hub server listening on ${port}`));
