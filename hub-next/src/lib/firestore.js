import 'server-only';
import { Firestore } from '@google-cloud/firestore';

let _db;

export function db() {
  if (!_db) {
    _db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });
  }
  return _db;
}

export function isoDate(v) {
  if (!v) return null;
  if (typeof v === 'string') return v;
  if (v instanceof Date) return v.toISOString();
  if (typeof v.toDate === 'function') return v.toDate().toISOString();
  return String(v);
}
