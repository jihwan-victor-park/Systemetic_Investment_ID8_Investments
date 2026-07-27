import { describe, expect, it } from 'vitest';
import { isInternal, ALLOWED_HD, EXPLICIT_INTERNAL_EMAILS } from './authInternal';

describe('isInternal', () => {
  it('grants access to any @id8investments.com email', () => {
    expect(isInternal('oscar@id8investments.com')).toBe(true);
    expect(isInternal('someone.new@id8investments.com')).toBe(true);
  });

  it('denies access to an unrelated domain', () => {
    expect(isInternal('investor@somefund.com')).toBe(false);
  });

  it('denies a domain that merely contains the allowed domain as a substring', () => {
    // e.g. "evil-id8investments.com" or "id8investments.com.evil.com" must not pass
    expect(isInternal('attacker@evil-id8investments.com')).toBe(false);
    expect(isInternal('attacker@id8investments.com.evil.com')).toBe(false);
  });

  it('grants access to the explicit safety-net allowlist regardless of domain', () => {
    for (const email of EXPLICIT_INTERNAL_EMAILS) {
      expect(isInternal(email)).toBe(true);
    }
  });

  it('is case-sensitive on the domain at this layer -- callers are expected to lowercase first', () => {
    // auth.js always calls isInternal on a pre-lowercased email (see its
    // signIn/jwt callbacks); this pins that contract so a future caller
    // doesn't assume case-insensitivity that isn't actually implemented here.
    // (An uppercase local part alone still passes, since only the domain
    // suffix is compared -- it's an uppercase domain that must fail here.)
    expect(isInternal(`someone@${ALLOWED_HD.toUpperCase()}`)).toBe(false);
  });
});
