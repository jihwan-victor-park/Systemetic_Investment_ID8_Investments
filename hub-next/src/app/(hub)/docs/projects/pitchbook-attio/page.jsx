import { H2, H3 } from '@/components/Prose';
import { Note } from '@/components/Admonition';
import GuideCard from '@/components/GuideCard';

export const metadata = { title: 'PitchBook → Attio Pipeline', description: 'Syncing PitchBook deal, company, and investor data into Attio.' };

export default function PitchbookAttioPage() {
  return (
    <>
      <h1>PitchBook → Attio Pipeline</h1>
      <p>
        This pipeline reads PitchBook exports of deals, companies, and investors and writes them into ID8&apos;s
        Attio CRM. It creates and updates Deal and Company records, stages deals, and links each deal to the VC
        firms that invested so the investor graph in Attio stays accurate.
      </p>

      <GuideCard
        title="PitchBook → Attio Pipeline"
        meta="The formatted edition. Investor linking, write formats, and backfill."
        cover="/img/cover_pitchbook.png"
        docx="/guides/ID8_PitchBook_Attio_Pipeline_Guide.docx"
      />

      <table>
        <tbody>
          <tr><td>Input</td><td>A PitchBook CSV of deals and companies, ideally with the Investors Websites column</td></tr>
          <tr><td>Output</td><td>Attio Deals and Companies, staged, with lead, new, and all-investor links</td></tr>
          <tr><td>Code</td><td><code>pipeline/</code> (app.py, attio_apollo_sync.py, attio_import/)</td></tr>
        </tbody>
      </table>

      <Note>
        The most important column in your export is Investors Websites. Without it, only VCs that already exist
        in Attio by name get linked. Everything else is skipped.
      </Note>

      <H2>How it works</H2>
      <ol>
        <li>Export deals and companies from PitchBook, including the Investors Websites column.</li>
        <li>Run the processing endpoint. Records are matched or created in Attio.</li>
        <li>Deal stage is applied per the staging rules below.</li>
        <li>Investor references are resolved and written as record links.</li>
      </ol>

      <H3>Write values are not read values</H3>
      <p>
        Attio&apos;s write format for a value differs from its read format. Writing the read shape fails silently.
        The field just does not get set, with no error. This is the most common reason a field looks like it did
        not update.
      </p>
      <table>
        <thead><tr><th>Type</th><th>Write format</th></tr></thead>
        <tbody>
          <tr><td>select, single</td><td>plain string of the option title, like <code>&quot;slug&quot;: &quot;Yes&quot;</code>. Not <code>[{'{'}&quot;option&quot;:&quot;Yes&quot;{'}'}]</code></td></tr>
          <tr><td>multi-select</td><td>array of title strings, like <code>&quot;slug&quot;: [&quot;A&quot;, &quot;B&quot;]</code></td></tr>
          <tr><td>text</td><td><code>[{'{'}&quot;value&quot;: &quot;...&quot;{'}'}]</code></td></tr>
          <tr><td>number</td><td><code>[{'{'}&quot;value&quot;: 123{'}'}]</code></td></tr>
          <tr><td>currency</td><td><code>[{'{'}&quot;currency_value&quot;: 123{'}'}]</code>. Money in millions, so multiply by 1,000,000</td></tr>
          <tr><td>date</td><td><code>[{'{'}&quot;value&quot;: &quot;YYYY-MM-DD&quot;{'}'}]</code></td></tr>
          <tr><td>status</td><td><code>[{'{'}&quot;status&quot;: &quot;Watchlist&quot;{'}'}]</code></td></tr>
          <tr><td>record reference</td><td><code>[{'{'}&quot;target_object&quot;: &quot;companies&quot;, &quot;target_record_id&quot;: &quot;...&quot;{'}'}]</code></td></tr>
        </tbody>
      </table>

      <Note>
        A single-select must be a plain string. The <code>[{'{'}&quot;option&quot;: &quot;Yes&quot;{'}'}]</code> shape is
        the read format and is ignored on write. This is why <code>top_10_vc</code> used to not get set. An unknown
        option errors, so <code>ensure_select_option</code> creates it first.
      </Note>

      <H2>hub-next stage changes push back to Attio</H2>
      <p>
        Moving a company between stages via the dropdown on a pipeline table row (<code>updateCompanyStage</code> in{' '}
        <code>hub-next/src/lib/companies.js</code>) mirrors that change onto the matching Attio Deal record through{' '}
        <code>pipeline/app.py</code>&apos;s <code>/update-deal-stage</code> endpoint, using the same <code>status</code>{' '}
        write shape as everywhere else on this page (<code>[{'{'}&quot;status&quot;: &quot;Qualified&quot;{'}'}]</code>).
        This is the direction that used to not exist at all — Attio → hub-next sync (<code>push_company_from_attio</code>)
        has existed for a while, but a stage edit made by hand in hub-next previously stayed siloed in Firestore and
        silently drifted from whatever Attio still showed.
      </p>
      <Note>
        Best-effort and non-blocking by design: the Firestore write is hub-next&apos;s own source of truth regardless
        of whether the Attio mirror succeeds, and a company with no <code>origin.attioRecordId</code> (created
        directly in the hub, never synced from Attio) has nothing to push back to — skipped, not an error. A failed
        push logs server-side (<code>console.error</code>) rather than surfacing to the user, since the stage change
        itself already succeeded in hub-next.
      </Note>

      <H2>Investor linking</H2>
      <p>The Deals object links VC firms to Company records through reference attributes. The link slugs, held in INVESTOR_REF_MAP, are below.</p>
      <table>
        <thead><tr><th>Category</th><th>Reference slug</th></tr></thead>
        <tbody>
          <tr><td>Lead investors</td><td><code>lead_investors_8</code></td></tr>
          <tr><td>New investors</td><td><code>new_investors_5</code></td></tr>
          <tr><td>All investors, including follow-ons</td><td><code>investors_5</code></td></tr>
        </tbody>
      </table>

      <Note>
        These are different from the text slugs in FIELD_MAP, which are <code>lead_investors</code>,{' '}
        <code>new_investors_7</code>, and <code>investors</code>. Those drive email and display. The slugs above
        create the actual links.
      </Note>

      <H3>Domain versus record ID</H3>
      <p>These are two different mechanisms depending on whether you use the CSV importer or the API.</p>
      <p>
        The CSV importer links by domain. Put the company domain in the cell and match on Domains. Record-ID
        matching does not work reliably in the importer. Separate multi-value cells with a comma and a space, not
        a semicolon.
      </p>
      <p>
        The API links by <code>target_record_id</code>. There is no link-by-domain in the API.{' '}
        <code>resolve_investor_links</code> matches by domain first, then by name, then sends the resolved id. Do
        not change it to emit a domain or the call breaks.
      </p>

      <H3>Create if website</H3>
      <p>
        <code>resolve_investor_links</code> matches by domain first, then name. If an investor is unmatched and
        the export gave its domain, it creates the company and caches the new id so repeats reuse it. Unmatched
        with no domain gets skipped, since you cannot create a company without a domain.
      </p>

      <H2>Backfill, staging, and fixes</H2>
      <H3>Bulk backfill, use CSV not the API</H3>
      <p>
        <code>get_company_index</code> with refresh pages every Company. On a large workspace that alone passes
        the 30 second gunicorn timeout, so <code>/process</code>, <code>/backfill-investors</code>, and{' '}
        <code>/update-investors</code> all return 500.
      </p>
      <p>For a one-off backfill, do not fight the timeout. Build a CSV locally and import it to Deals in the Attio UI.</p>
      <ol>
        <li>One row per deal, with domain columns per category, multi-value separated by a comma and a space. pandas quotes the cells for you.</li>
        <li>Reuse <code>parse_investor_websites</code> for the name-to-domain map and <code>parse_investors</code> per category.</li>
        <li>Import to Deals: match deals by Name, map domain columns to <code>lead_investors_8</code>, <code>new_investors_5</code>, and <code>investors_5</code>, match target Companies on Domains, and create missing ones.</li>
      </ol>

      <Note>Duplicate deal names across Series make name-matching ambiguous. Handle those by Series or by hand.</Note>

      <H3>Staging rules</H3>
      <p>
        <code>/process-top10</code> puts only new deals on Radar. Existing deals keep their current stage, so do
        not auto-promote a Qualified deal. To bulk-promote existing Qualified deals to Radar, use{' '}
        <code>/fix-radar-stages</code>. It moves Qualified deals that have <code>new_investors_7</code>.
      </p>

      <H2>Technical structure</H2>
      <p>
        Code lives in <code>pipeline/</code> (<code>app.py</code>, <code>attio_apollo_sync.py</code>,{' '}
        <code>attio_import/</code>). The endpoints above run from <code>pipeline/app.py</code>.
      </p>
    </>
  );
}
