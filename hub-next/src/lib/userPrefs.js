import 'server-only';
import { db } from './firestore';

const COLLECTION = 'userPrefs';

// One doc per signed-in user, keyed by lowercased email -- how that person
// has chosen to reorder/rename their own top-level Hub tabs (Notion-style
// customization, per Oscar's ask). Entirely optional and per-user: someone
// who's never customized anything just gets the default order/labels from
// sidebarConfig.js (see applyUserPrefs there). Open to any signed-in user,
// not internal-only -- an investor's own tab layout is theirs to arrange
// too, it doesn't touch anyone else's data or the underlying deal records.
export async function getUserPrefs(email) {
  if (!email) return { tabOrder: [], labels: {} };
  const doc = await db().collection(COLLECTION).doc(email.toLowerCase()).get();
  if (!doc.exists) return { tabOrder: [], labels: {} };
  const d = doc.data();
  return { tabOrder: d.tabOrder || [], labels: d.labels || {} };
}

export async function updateUserPrefs(email, patch) {
  if (!email) throw new Error('missing-email');
  const ref = db().collection(COLLECTION).doc(email.toLowerCase());
  await ref.set(patch, { merge: true });
  return { email: email.toLowerCase() };
}
