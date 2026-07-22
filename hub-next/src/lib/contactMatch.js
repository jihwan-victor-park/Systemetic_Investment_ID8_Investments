// Best-effort pairing of a VC's team-member names against its team-member
// emails. Both come from the same Attio export as two independently-ordered
// multi-value fields -- position in one list has no relation to position in
// the other (verified against the real "ID8 Partner VCs" export: e.g.
// CoVenture's name list starts with "Meghan Hillery" but its email list
// starts with "ali@coventure.vc", matching a name 9th in the list) -- so
// pairing has to go by content, not index.
//
// Scoring per (name, email) candidate pair:
//  - any name token (>=3 chars) appearing in the email's local-part: +token length
//  - first-initial + another token forming the local-part exactly (e.g.
//    "Dillon Woodward" -> "dwoodward"): +10, the strongest single signal --
//    this is what disambiguates "Bill Woodward" from "Dillon Woodward" on
//    the same firm, since a bare substring match on "woodward" alone can't.
//  - local-part matching the firm's own dominant email domain: +8 -- breaks
//    ties toward a person's current work email over a stale/personal one
//    (e.g. "Doug Sills" -> dsills@anthemvp.com over dougsills90@gmail.com).
// Pairs are then assigned greedily, highest score first, each name and each
// email used at most once -- so a strong match elsewhere can't be blocked
// by a weaker pair claiming the same email first.
const MIN_SCORE = 6;

function emailDomain(email) {
  const at = email.lastIndexOf('@');
  return at === -1 ? '' : email.slice(at + 1).toLowerCase();
}

function localPart(email) {
  const at = email.lastIndexOf('@');
  return (at === -1 ? email : email.slice(0, at)).toLowerCase().replace(/[^a-z0-9]/g, '');
}

function nameTokens(name) {
  return name.toLowerCase().replace(/[^a-z\s]/g, ' ').split(/\s+/).filter((t) => t.length >= 2);
}

// The domain shared by the most addresses in this firm's own email list --
// a more reliable "real" domain than the VC's `website` field, which is
// often just the first of several aliases (see 1789 Capital: 1789capital.vc
// vs the .io addresses its team actually uses).
function primaryDomain(emails) {
  const counts = new Map();
  for (const email of emails) {
    const d = emailDomain(email);
    if (!d) continue;
    counts.set(d, (counts.get(d) || 0) + 1);
  }
  let best = '';
  let bestCount = 0;
  for (const [d, c] of counts) {
    if (c > bestCount) { best = d; bestCount = c; }
  }
  return best;
}

function scorePair(name, email, domain) {
  const tokens = nameTokens(name);
  const local = localPart(email);
  if (!tokens.length || !local) return 0;

  // Everything below has to come from the name itself -- the domain bonus
  // (added last, only on top of a nonzero base) exists purely to break ties
  // between candidates that already have a real reason to match. Without
  // that gate, a name sharing nothing with an email except the firm's own
  // domain (true of every address at a firm) would still limp over
  // MIN_SCORE on domain alone and grab a stranger's email.
  let base = 0;
  tokens.forEach((t, i) => {
    const weight = i === 0 ? 2 : 0; // first-name match is the strongest single-token signal
    if (local === t) {
      // Exact whole-local match, even for a 2-letter token like "MK" in
      // "MK McCormick" -- equality is a strong signal regardless of length,
      // unlike substring containment which is only meaningful once it's
      // long enough not to occur by chance.
      base += Math.max(t.length, 8) + weight;
    } else if (t.length >= 3 && local.includes(t)) {
      base += t.length + weight;
    } else if (local.length >= 3 && t.length > local.length && t.startsWith(local)) {
      // Nickname/short-form prefix, e.g. "Will" -> "William", "Max" ->
      // "Maximilian", "Jeff" -> "Jeffrey", "Pat" -> "Patrick".
      base += local.length + weight;
    }
  });
  if (tokens.length >= 2) {
    const initial = tokens[0][0];
    for (let i = 1; i < tokens.length; i++) {
      if (local === initial + tokens[i] || local === tokens[i] + initial) base += 10;
    }
    // All-initials form, e.g. "Chris Ward-Willis" -> "cww", "Investor
    // Relations" -> "ir" -- common for multi-word names/role aliases where
    // no single token or two-token pattern above would otherwise fire.
    const allInitials = tokens.map((t) => t[0]).join('');
    if (allInitials.length >= 2 && local === allInitials) base += 12;
  }
  if (base === 0) return 0;
  if (domain && emailDomain(email) === domain) base += 8;
  return base;
}

// contactStr / emailsStr are both comma-joined raw strings straight off the
// VC doc (`contact` and `contactEmails`). Returns one entry per name in
// `contactStr`, in its original order, `email: ''` when nothing clears
// MIN_SCORE -- a generic address (info@, ir@) shares no tokens with any
// name and is deliberately left unmatched rather than forced onto someone.
export function matchContacts(contactStr, emailsStr) {
  const names = (contactStr || '').split(',').map((s) => s.trim()).filter(Boolean);
  const emails = (emailsStr || '').split(',').map((s) => s.trim()).filter(Boolean);
  if (!names.length) return [];
  if (!emails.length) return names.map((name) => ({ name, email: '' }));

  const domain = primaryDomain(emails);
  const pairs = [];
  names.forEach((name, ni) => {
    emails.forEach((email, ei) => {
      const score = scorePair(name, email, domain);
      if (score > 0) pairs.push({ ni, ei, score });
    });
  });
  pairs.sort((a, b) => b.score - a.score);

  const assignedName = new Set();
  const assignedEmail = new Set();
  const emailByName = new Map();
  for (const p of pairs) {
    if (p.score < MIN_SCORE) break;
    if (assignedName.has(p.ni) || assignedEmail.has(p.ei)) continue;
    assignedName.add(p.ni);
    assignedEmail.add(p.ei);
    emailByName.set(p.ni, emails[p.ei]);
  }
  return names.map((name, i) => ({ name, email: emailByName.get(i) || '' }));
}
