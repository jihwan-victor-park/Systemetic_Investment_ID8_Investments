import Link from 'next/link';
import { H2 } from '@/components/Prose';
import { Note } from '@/components/Admonition';

export const metadata = { title: 'Deal Intelligence', description: 'Two-stage AI research and scoring over every qualified deal.' };

export default function IntelligencePage() {
  return (
    <>
      <h1>Deal Intelligence</h1>
      <p>
        The intelligence layer scores and researches every qualified deal, so judgment is built on evidence
        instead of gut. It runs in two stages and writes results back to Attio and this hub. The deep memo is
        only produced for the deals worth it.
      </p>

      <H2>How it works</H2>
      <table>
        <thead><tr><th>Stage</th><th>Runs on</th><th>Output</th><th>Model</th></tr></thead>
        <tbody>
          <tr>
            <td>1. Preliminary fit</td>
            <td>Every qualified deal</td>
            <td>A 1 to 4 fit score, a gate flag, and a short rationale — written to Attio, a per-company page on the hub, and the deal-intake email</td>
            <td>Cheap and fast (Perplexity)</td>
          </tr>
          <tr>
            <td>2. Deep research</td>
            <td>Only deals that clear the gate</td>
            <td>Five research angles and a synthesized memo with a final score, on Attio and the hub</td>
            <td>Strongest</td>
          </tr>
        </tbody>
      </table>
      <p>
        Stage 1 is cheap, so it runs across the whole qualified pipeline. Stage 2 is heavier, so it only fires
        for the deals that pass the threshold. That keeps cost down and attention on the deals that matter.
      </p>

      <H2>Stage 1, preliminary fit</H2>
      <p>
        Each qualified deal gets a light Perplexity research pass and a score against the ID8 rubric — five
        equally weighted dimensions, each scored 1 to 4: lead / round dynamics, AI score, fundamentals, return
        potential, and terms. Two hard gates run first: the round must be Series B or later, and the company
        must be headquartered in North America or Europe. Output is a weighted fit score (1 to 4), a short
        rationale that names alignment or misalignment with the fund&apos;s new-money Tier 1 thesis, and a gate
        flag — written onto the deal in Attio, published as a per-company page under Research, and rendered
        into the deal-intake email so the team can scan ratings without leaving their inbox.
      </p>

      <H2>Stage 2, deep research</H2>
      <p>
        Deals over the threshold get the full treatment: parallel research on the company, market, traction,
        round dynamics, and risks, then a synthesized memo with a final score. The memo reads like the Gimlet
        and Lila drafts in Research. It is written to Attio and surfaced here.
      </p>

      <H2>Why it is proprietary</H2>
      <p>
        It runs on ID8&apos;s own deal flow and rubric. Every deal that moves through the pipeline makes the
        next pass sharper. That is the edge: not a data feed anyone can buy, but a scoring and research engine
        tuned to how ID8 actually invests.
      </p>
      <p>
        Each company gets one page under <strong><Link href="/docs/research">Research → Companies</Link></strong>,
        keyed by a stable id and its website, holding a dated screen history — so when a company comes back at a
        later round, the new screen is appended to the same page rather than scattered across one-off entries.
        Live screens: <Link href="/docs/research/companies/assorthealth">Assort Health</Link>,{' '}
        <Link href="/docs/research/companies/ollin">Ollin</Link>,{' '}
        <Link href="/docs/research/companies/warp">Warp</Link>.
      </p>

      <Note>
        The rubric and the agent prompts live in <code>deal_intelligence/prompts/</code>. The external name for
        this capability is still being decided.
      </Note>

      <H2>Status</H2>
      <p>
        Live. Stage 1 runs on every new deal from the intake pipeline — scoring against the rubric, publishing
        a per-company screen under Research, and rendering the rating into the deal-intake email. Stage 2 deep
        research fires for deals that clear the gate. Remaining: the Attio write-back fields, so scores also
        land on the deal record.
      </p>
    </>
  );
}
