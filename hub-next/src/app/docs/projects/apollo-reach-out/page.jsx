import { H2, H3 } from '@/components/Prose';
import { Note } from '@/components/Admonition';
import GuideCard from '@/components/GuideCard';

export const metadata = { title: 'Apollo Reach Out', description: 'Building clean family office and RIA lists, enriching them, and launching sequences.' };

export default function ApolloReachOutPage() {
  return (
    <>
      <h1>Apollo Reach Out</h1>
      <p>
        Apollo Reach Out turns Apollo&apos;s contact database into a short, clean list of real family office and
        RIA decision-makers. It enriches each one and loads them into a managed outbound sequence.
      </p>

      <GuideCard
        title="Apollo Reach Out"
        meta="The formatted edition. Filters, enrichment, and sequence setup."
        cover="/img/cover_apollo.png"
        docx="/guides/ID8_Apollo_Reach_Out_Guide.docx"
      />

      <p>
        The hard part is filtering. A broad search for financial services in Los Angeles returns about 61,889
        people. That is every banker, broker, and fintech employee in the city. This guide is the recipe that
        gets you down to 50 to 300 real prospects.
      </p>

      <H2>When to use it</H2>
      <ul>
        <li>You are preparing an outbound push for a city or an event, like the LA trip.</li>
        <li>You need a fresh list of prospects to feed the LP screener.</li>
        <li>You want to load qualified contacts into a sequence without touching anyone already in a live campaign.</li>
      </ul>

      <H2>What you get</H2>
      <table>
        <thead><tr><th>Stage</th><th>Output</th></tr></thead>
        <tbody>
          <tr><td>Filtered search</td><td>50 to 300 clean FO and RIA decision-makers in the target city</td></tr>
          <tr><td>Enrichment</td><td>Research and a 0 to 100 LP fit score per firm</td></tr>
          <tr><td>Sequence load</td><td>Contacts mirrored into Apollo and enrolled in the managed sequence</td></tr>
        </tbody>
      </table>

      <Note>
        Quality beats quantity here. A hundred precise contacts outperform five thousand broad ones. If loosening
        a filter grows the list, the list usually got worse.
      </Note>

      <H2>Building the target list</H2>
      <p>Set the filters in this order. Each layer removes a category of bad results. The employee count filter does most of the work on its own.</p>

      <H3>Step 1. Company keywords to include</H3>
      <p>Set the keyword type to ANY so a contact matches on any single term. Use only the terms real family offices use about themselves.</p>
      <ul>
        <li>family office</li>
        <li>single family office</li>
        <li>multi-family office</li>
        <li>private family office</li>
        <li>family wealth</li>
        <li>private wealth</li>
      </ul>

      <Note>
        Skip the broad terms wealth management, investment management, and financial services. They pull in
        large platforms like Mercer, Edward Jones, and Raymond James.
      </Note>

      <H3>Step 2. Company keywords to exclude</H3>
      <p>Exclusions do more work than inclusions. Paste these into the exclude box.</p>
      <table>
        <thead><tr><th>Category</th><th>Exclude terms</th></tr></thead>
        <tbody>
          <tr><td>Banks and wirehouses</td><td>bank, banking, brokerage, broker dealer, Raymond James, Edward Jones, Morgan Stanley, Wells Fargo, Merrill Lynch, UBS, Charles Schwab, Ameriprise, LPL Financial</td></tr>
          <tr><td>Large platforms</td><td>Fidelity, Vanguard, BlackRock, asset management, fund administration</td></tr>
          <tr><td>Insurance</td><td>insurance, Northwestern Mutual</td></tr>
          <tr><td>Wrong asset class</td><td>hedge fund, private equity, venture capital, real estate</td></tr>
          <tr><td>Wrong kind of finance</td><td>accounting, tax, payroll</td></tr>
          <tr><td>Tech in finance</td><td>fintech, software, technology</td></tr>
        </tbody>
      </table>

      <H3>Step 3. Employee count</H3>
      <p>Real family offices have 2 to 30 employees. Platforms have hundreds or thousands. Under Company Headcount, select 1 to 10 and 11 to 50.</p>

      <Note>This one filter removes about 90 percent of the wrong results. If you do nothing else, do this.</Note>

      <H3>Step 4. Job titles</H3>
      <p>Partner, Managing Partner, Principal, Chief Investment Officer, Head of Investments, Director of Investments, Managing Director, Investment Director, Portfolio Manager.</p>

      <H3>Step 5. Seniority</H3>
      <p>Owner or Partner, C-Suite, VP, Director.</p>

      <H3>Step 6. Location</H3>
      <p>Keep the geography tight to the campaign. For the current effort this is Los Angeles.</p>

      <H3>RIA sub-search</H3>
      <p>RIAs that serve high-net-worth clients are small firms. Run them as a separate search.</p>
      <table>
        <thead><tr><th>Filter</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td>Keywords</td><td>registered investment advisor OR RIA</td></tr>
          <tr><td>Headcount</td><td>1 to 50</td></tr>
          <tr><td>Titles</td><td>Partner, CIO, Managing Director, Principal</td></tr>
        </tbody>
      </table>
      <p>Any RIA with 500 or more employees is a retail platform, not what you want.</p>

      <H3>What good looks like</H3>
      <p>After all layers you should land between 50 and 300 results. You want unfamiliar names like Westlake Capital or Meridian Family Office. If you recognize the firm, it is too big.</p>

      <H2>Enrich and launch</H2>
      <H3>Enrich with Perplexity</H3>
      <p>Research each firm before you reach out. The enrichment step scores each firm against the ID8 Growth Opportunities Fund I rubric.</p>
      <table>
        <thead><tr><th>Script</th><th>Role</th></tr></thead>
        <tbody>
          <tr><td><code>perplexity_lp_screener.py</code></td><td>Per-firm web research and structured notes</td></tr>
          <tr><td><code>lp_screener_hybrid.py</code></td><td>Applies the 0 to 100 rubric and tiers firms</td></tr>
        </tbody>
      </table>
      <p>These also back the <code>lp-prospect-screener</code> skill. Hand it a CSV of contacts and it returns a scored, tiered CSV.</p>

      <Note>Screen before you load the sequence. Enroll only Tier 1 and Tier 2 firms.</Note>

      <H3>Load the sequence</H3>
      <p>
        The sync mirrors your Attio People into Apollo and parks them in a dormant holding sequence. Any later
        Apollo search then flags those people as already sequenced, so you never double-touch a contact. It
        lives in <code>pipeline/attio_apollo_sync.py</code> and runs from <code>/sync-apollo</code>.
      </p>
      <pre><code>{`curl -X POST https://<your-app>/sync-apollo
curl https://<your-app>/sync-apollo/status`}</code></pre>
      <table>
        <thead><tr><th>Env var</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td><code>APOLLO_API_KEY</code></td><td>Must be a master key. add_contact_ids returns 403 otherwise</td></tr>
          <tr><td><code>APOLLO_HOLDING_SEQUENCE_ID</code></td><td>A dormant sequence with no active email steps</td></tr>
          <tr><td><code>APOLLO_MAILBOX_ID</code></td><td>Optional mailbox for the sequence</td></tr>
        </tbody>
      </table>

      <H3>API gotchas</H3>
      <p>These fail silently with no error, so they are easy to miss.</p>
      <ul>
        <li><code>add_contact_ids</code> needs a master API key.</li>
        <li>Sequence flags are snake_case: <code>sequence_active_in_other_campaigns</code> and <code>sequence_finished_in_other_campaigns</code>. CamelCase is ignored. Keep both false so live contacts stay put.</li>
        <li>The mailbox param is <code>send_email_from_email_account_id</code>, and <code>emailer_campaign_id</code> must echo the sequence id.</li>
        <li>Upsert with <code>POST /contacts</code> and <code>run_dedupe=true</code>. The lookup fallback is <code>POST /contacts/search</code>.</li>
        <li>Re-running is safe. Apollo dedupes and a contact can only sit in a sequence once.</li>
      </ul>

      <H2>Technical structure</H2>
      <p>
        Code lives in <code>pipeline/attio_apollo_sync.py</code> (the sync, exposed at <code>/sync-apollo</code>),{' '}
        <code>lp-screener/</code> (<code>perplexity_lp_screener.py</code> and <code>lp_screener_hybrid.py</code> for
        enrichment and scoring), and the <code>lp-prospect-screener</code> skill.
      </p>
    </>
  );
}
