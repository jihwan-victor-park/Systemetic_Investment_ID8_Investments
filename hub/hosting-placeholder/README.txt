This directory is intentionally near-empty.

Firebase Hosting requires a "public" directory to exist, but every real
request to this site is meant to be handled by the Cloud Run rewrite in
firebase.json (see server/index.js), not by static files here.

Do not add an index.html (or any file matching a real app route) to this
directory: Firebase Hosting serves an exact static-file match BEFORE it
evaluates rewrites, so a matching file here would silently bypass the
sign-in gate for that path.
