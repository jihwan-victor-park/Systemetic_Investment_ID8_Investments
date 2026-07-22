import ResearchChat from '@/components/ResearchChat';

export const metadata = {
  title: 'Research Chat',
  description: 'Trigger Deal Intelligence Stage 1 or Stage 2 research on any company from chat.',
};

export default function ResearchChatPage() {
  return (
    <>
      <h1>Research Chat</h1>
      <p>
        This runs the same <a href="/docs/projects/intelligence">Deal Intelligence</a> research
        pipeline as the automated screen, on demand, for any company — not just deals already in
        Attio. It does exactly two things, deliberately nothing else: kick off Stage 1 (fit check
        against the rubric), or Stage 2 (deep research memo).
      </p>
      <p>
        <strong>Stage 1</strong> is the smart path today — just describe what to look into in plain
        language ("look into Ramp's Series D, led by Founders Fund") and it parses out the company
        and whatever context you gave it. Results are published to the hub and appear in{' '}
        <a href="/docs/qualified-deals">Qualified Deals</a> like any other screen.
      </p>
      <p>
        <strong>Stage 2</strong> still needs the company name typed directly (plus optional details)
        — the same free-text parsing is coming for it later. Stage 2 memos show only in this chat;
        there is no hub page for memos yet. Both stages run at max research depth, so expect several
        minutes per company.
      </p>
      <ResearchChat />
    </>
  );
}
