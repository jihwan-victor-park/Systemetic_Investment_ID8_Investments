import "server-only";
import { Firestore } from "@google-cloud/firestore";

// On Cloud Run, credentials + project come from the service account via ADC.
// Locally, `gcloud auth application-default login` supplies them; GCP_PROJECT_ID
// pins the project.
const COLLECTION = process.env.FIRESTORE_COMPANIES_COLLECTION || "hub_companies";

let _db;
function db() {
  if (!_db) {
    _db = new Firestore({ projectId: process.env.GCP_PROJECT_ID || undefined });
  }
  return _db;
}

/** Coerce a Firestore Timestamp / ISO string / Date into an ISO date string. */
function isoDate(v) {
  if (!v) return "";
  if (typeof v === "string") return v;
  if (typeof v.toDate === "function") return v.toDate().toISOString();
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

/** All companies with a screen, newest activity first (for the research index). */
export async function listCompanies() {
  const snap = await db().collection(COLLECTION).orderBy("updated_at", "desc").get();
  return snap.docs.map((d) => {
    const data = d.data();
    return {
      slug: d.id,
      name: data.name || d.id,
      domain: data.domain || "",
      latest_screen_date: data.latest_screen_date || "",
      latest_round: data.latest_round || "",
      latest_fit_score: data.latest_fit_score ?? null,
      latest_gate: !!data.latest_gate,
      latest_tier_label: data.latest_tier_label || "",
      updated_at: isoDate(data.updated_at),
    };
  });
}

/** One company with its full dated screen history (newest first). */
export async function getCompany(slug) {
  const doc = await db().collection(COLLECTION).doc(slug).get();
  if (!doc.exists) return null;
  const data = doc.data();
  return {
    slug: doc.id,
    name: data.name || doc.id,
    domain: data.domain || "",
    round: data.round || "",
    hq: data.hq || "",
    lead_investors: data.lead_investors || "",
    screens: Array.isArray(data.screens) ? data.screens : [],
    has_docx: !!data.docx_base64,
    updated_at: isoDate(data.updated_at),
  };
}

/** The latest screen's .docx as a Buffer, or null. */
export async function getCompanyDocx(slug) {
  const doc = await db().collection(COLLECTION).doc(slug).get();
  if (!doc.exists) return null;
  const b64 = doc.data().docx_base64;
  if (!b64) return null;
  return Buffer.from(b64, "base64");
}
