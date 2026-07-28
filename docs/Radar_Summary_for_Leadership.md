# Radar — Being in the Room Three Months Early

*Internal summary · 28 July 2026 · Oscar Varas*

---

## The goal, stated precisely

We co-invest at Series B and later, alongside a Tier 1 firm leading the round with
new money. Two things follow from that, and they define the whole system:

> **1. We need contact with the company at least three months before it opens its
> next round.** Early enough to be in the conversation when the round forms; not so
> early that we're maintaining a relationship for years.
>
> **2. A perfectly-timed company we can't co-invest into is worth nothing to us.**
> If the next round won't be led by a new Tier 1, the deal fails our screen no
> matter how well we predicted the timing.

Radar exists to deliver both: it tells us **when** to make contact, and it filters
out companies that will never be co-investable in the first place.

---

## The problem today

Companies reach us one way: someone runs a PitchBook export by hand and drops it in
a folder, which triggers our automation. So we learn about a company **after** its
round has closed and after PitchBook has recorded it — typically weeks to months
late. And once it arrives, nothing revisits it. It sits in a list.

The result is that we meet companies when they are either not raising, or already
raising. Almost never three months out.

---

## The three dates the system works to

```
     signals appear        WE ACT           contact must exist       round opens
          │                  │                     │                     │
  ────────┼──────────────────┼─────────────────────┼─────────────────────┼─────▶
       T−6mo             T−4.5mo                T−3mo                  T−0
   prepare the route   request the intro       ← the goal          they go to market
   (internal only)
```

An important detail: **the alert has to fire earlier than the goal.** Securing an
introduction takes four to six weeks, so to have contact in place by three months
out, the system must flag the company at about four and a half months out. That gap
is the time it takes to work a route in — and getting it wrong is the difference
between hitting the target and arriving six weeks before a round, which is too
late to matter.

---

## How companies arrive, and which ones we keep

Radar is fed by our **two existing sourcing workflows, and only those**:

| | Pathway | What it delivers |
|---|---|---|
| 1 | **Top 10 VC workflow** — companies backed by firms we co-invest alongside | The round, what was raised, when it closed, and who is on the cap table |
| 2 | **Qualified deals workflow** — companies matching our investment filters | The same, for the broader qualified set |

Both already run and both already deliver everything the new logic needs — round
size, **closing date**, and the investor list. Our system currently records the
closing date and never reads it back; that single fix unlocks everything else.

**Then we screen, at the moment of arrival.** Four checks, all automatic:

1. **Geography** — North America or Europe.
2. **Next round in mandate** — Series B or later.
3. **A Tier 1 firm on the cap table.** This is the hard one. A company with no
   Tier 1 anywhere is very unlikely to attract a new Tier 1 lead next time, which
   means we couldn't co-invest even with perfect timing.
4. **Not structurally an insider round** — last round wasn't a bridge or a flat
   extension.

Companies that fail are recorded with the reason and **never monitored at all**.
This is why the system is cheap: we watch a few hundred companies that could
genuinely become deals, not a few thousand that couldn't.

**And a second filter we can change ourselves, without engineering.** Some companies
are only obviously wrong for us once you read what they actually do — a biotech, a
real-estate platform, a staffing business. That check exists today, but the list of
off-thesis terms is buried in the code, so adding one means a developer and a
deployment.

We move that list onto the Radar tab as something we edit directly:

- **Keywords or phrases** — anything matching in a company's description, category or
  vertical drops it off the list.
- **Whole categories** — exclude a sector outright, using the structured field.
- **Specific companies** — drop this one, whatever the rules say.

Three things make it safe to use:

1. **Preview before saving.** Type a word and see exactly how many companies it would
   drop and which ones, *before* committing. Typing "medical" and seeing it would
   also remove a company you like is what prevents a careless rule quietly shrinking
   the list.
2. **Nothing is deleted.** Excluded companies stop being monitored — that's the saving
   — but sit in a collapsed "Excluded" section, restorable with one click.
3. **"Keep anyway."** Pin a good company so no current or future rule can remove it.

Changes apply **immediately and retroactively**: add a term and every company already
on the list is re-checked on the spot. And each review re-checks the rules too, since
a company described vaguely as "data infrastructure" in August might read clearly as
clinical-trial software by November.

Over time it curates itself: when several companies get removed by hand, the system
notices what their descriptions have in common and suggests it as a rule.

**And we keep two questions separate**, because they can point in opposite
directions:

| | The question | What answers it |
|---|---|---|
| **Access** | Can we get in front of them? | Who is on the cap table now, and who we know there |
| **Mandate fit** | Will a *new* Tier 1 lead the next round? | Whether the round goes to an outside firm or is simply done internally |

An existing Tier 1 investor is excellent for access and no guarantee of fit — if
the insiders just do the next round themselves, there's no new-money Tier 1 lead
and it isn't a deal for us. So we assess that separately, and we check ourselves
afterwards: the public filing that confirms a round also names the new board
member, which tells us who actually led.

---

## What we look at

Almost entirely free, public data. No new vendor is needed for the core system.

| What | Where it comes from | Cost |
|---|---|---|
| **Funding filings** — companies must file publicly when they raise | US securities regulator (within 15 days of closing); UK companies registry (within a month). Also names the new investor director, i.e. **who led** | **Free** |
| **Open roles** — every posting, its title, and when it appeared | The company's own job board. Most venture-backed companies use Greenhouse, Lever or Ashby, all of which publish their listings openly for exactly this purpose | **Free** |
| **Headcount** | Apollo, which we already license | Included |
| **Press and announcements** | News feeds; funding rumours; customer and product news; reports naming interested investors | **Free** |
| **The company's own website** | Pricing page, customer logos, security/trust page | **Free** |
| **Tier 1 activity** | Which firms are leading rounds, in what sectors, and who has just raised a fund | **Free** |

On the filings: this is how we learn a company we're watching has raised — **weeks
before the data vendor we pay for records it.** On the job boards: we read the
company's *own* published board, through the interface published for that purpose.

---

## What we measure

Everything is stored as **history, not a snapshot**, because the signal is in the
change. One look at a job board tells you nothing; twelve months of samples showing
a company go from 52 to 84 staff, with a Director of Finance role appearing in
month seven, tells you a great deal.

**1 · How much runway they have left.** We know what they raised and roughly what
they spend, so we can estimate when the money runs out. Companies start raising with
9–12 months of cash left. That gives us a predicted date for the round opening —
and therefore a **deadline for making contact**, three months before it.

**2 · What kind of people they're hiring.** The most valuable thing the system
measures, and a distinction a simple headcount tracker misses entirely:

> A company **preparing to raise** hires **narrow and senior** — a finance leader,
> a data hire, a sales executive. It is building the apparatus a fundraise
> requires: someone to produce the numbers and run the data room.
>
> A company that just **closed** a round hires **broad and junior** — engineers and
> salespeople across the board. It is spending the money.
>
> Both look like "hiring is up." They mean opposite things.

These signals also happen to be the only ones with enough lead time — six to nine
months — to let us hit a three-month contact deadline. By the time a press report
says a company is in talks, we should already know them.

**3 · Whether they're warming the market.** Customer announcements, product
launches, an enterprise pricing tier, a press page — companies make themselves
visible to investors before they need to ask.

**Output per company:** the probability they open a raise within six months (which
is what triggers action), the probability within three months (which tells us
whether we're behind), a predicted date window, a contact-by deadline, and the
specific evidence behind all of it.

---

## How often we check, and why it varies

We expect around **100 companies** on the list (9 today, growing weekly). Two
separate rhythms:

**A free background record.** Every week we take a snapshot of each company's job
board; every month, headcount; every day, the funding filings. No analysis — it just
builds up history. This costs nothing and it matters because a senior finance role
often stays open only six to eight weeks. If we only looked when we did a full
review, we'd miss the single most valuable signal in the system.

**A review, on a schedule that varies by company.** The first review is at **four
months** after their round closed — before that it's all deployment noise, nothing
diagnostic. The second at **six months**, which gives us a direction rather than
just a reading. After that the interval is calculated:

| Time until we think they'll raise | We review every |
|---|---|
| More than a year | 4 months |
| 8–12 months | 3 months |
| 5–8 months | 8 weeks |
| **3–5 months** | **6 weeks** — the decisive stretch |
| Under 3 months | 4 weeks |

Then adjusted for the company: **capital-intensive businesses** (hardware, defence,
companies training their own AI models) burn faster and get reviewed ~30% more
often. **Capital-light, near-breakeven businesses** can go two and a half years and
get reviewed less. A big round relative to burn stretches the interval; a bridge
shortens it. Strong momentum shortens it; two quiet reviews in a row lengthen it.
And once a finance role appears anywhere, the interval never stretches past six
weeks.

**Target: about five reviews per company per year.** That's three ordinary reviews
for a company showing nothing urgent, plus **two fixed dates every company gets
regardless of its own schedule — early September and mid-January** (see below) —
which gives 3 + 2 = 5 as the resting rate for a quiet company. A company actively
approaching its raise reviews more often than that, which is intended: that's where
the attention should concentrate. **Each review costs no more than 15 cents** —
capped, and most of the cost in the system is concentrated in the much rarer full
research pass, not in routine reviews.

Importantly, **a real signal doesn't wait for the next scheduled review.** When the
weekly job-board snapshot catches a finance role, the review is pulled forward. In
the example below that mechanism is what bought us three extra weeks — and three
weeks was the difference between making contact three months out and six weeks out.

---

## Being realistic about the calendar

Fundraises don't launch evenly through the year, and a model that ignores this
produces confident predictions for months in which nothing ever happens.

**Nobody launches a process in August, or between mid-December and the first week of
January.** Partners are away, partner meetings thin out, decisions stall.

**Processes launch in two windows:** mid-January to early June, and early September
to mid-November.

Three rules follow, and the asymmetry between the first two is deliberate:

1. **Their dates move later.** If the maths says a company's window opens on
   12 August, they'll actually start in early September. If it says 22 December,
   they'll start mid-January.
2. **Our deadlines move earlier.** If our contact deadline lands in late August or
   over the holidays, we bring it forward — mid-July, or early December. We can't
   afford to be chasing an introduction when nobody's answering email. Their dates
   slip later; ours slip earlier, never the other way round.
3. **The exception that catches people out:** a company whose money actually runs
   out in September *cannot* wait for September to start raising. It has to run the
   process in May or June, or take a bridge. So cash pressure landing in a dead zone
   pulls the process **earlier**, not later — the opposite of rule 1. The naive read
   of a quiet summer is exactly wrong in that case.

We also do two **all-company reviews on fixed dates: around 5 September and around
12 January.** Those are the highest-information days of the year — companies that
decided over the break to raise start posting finance roles right then. One review
on 5 September is worth several in August.

---

## A worked example

**Northwind Systems** arrives in August 2026 through the Top 10 VC workflow: AI data
infrastructure, Boston, **Series B of $32M closed February 2026**, led by a firm we
co-invest alongside.

**Screen:** Boston ✓ · next round is Series C ✓ · Tier 1 on the cap table ✓ · no
bridge ✓ → **monitored.**

**Runway maths:** 52 staff at closing, 71 now, roughly $1.7M a month going out,
about $23M of the $32M left. The money runs out around August 2027, so the round
likely opens around **February 2027**.

> **Contact deadline: November 2026. Alert must fire by mid-October.**

| | What we see | Chance of raising within 6 months |
|---|---|---|
| **Aug** | 71 staff. 9 open roles, all engineers and salespeople — post-round spending | 18% |
| **Sep** | 76 staff. A **Director of Finance** role appears | 32% → *prepare the route* |
| **Oct** | 81 staff. A **VP Sales** role appears — total openings flat but the senior share climbing. Two enterprise customers announced | **41% → contact window opens, 8 Oct** |
| **Nov** | Finance role **filled**. Enterprise pricing tier appears on their site | 52% → **contact made 6 Nov** |
| **Dec** | A **Head of Corporate Development** role appears. Runway under 8 months | 61% → already known |
| **Feb 2027** | **They file a $65M round, led by a Tier 1 that wasn't previously on the cap table** | closed |

**What we actually did.**

In **September**, the first preparation signal told us to get the route ready — no
contact yet, just confirming internally that the Series B lead is a firm we
co-invest alongside and that we already have a partner-level contact for them. Two
minutes of work.

In **October**, the evidence crossed our threshold with two independent signal
types behind it. That triggered the one piece of paid AI research in the whole
sequence: a single pass that checked the evidence sceptically (was the finance hire
just a replacement? was the headcount jump an acquisition?), judged that a **new**
Tier 1 was likely to lead — multiple Tier 1s active in the sector, check size in
range, the existing lead late in its fund cycle — and named our route in. Intro
requested that week.

**Contact was made on 6 November. The round opened in early February — three
months later. Goal met.**

And the round was **led by a new Tier 1**, which is what made it something we could
actually co-invest into. The public filing confirmed both calls automatically.

**Total AI cost for this company over seven months: well under $1.05** — six
routine reviews at well under 15 cents each, plus the one real research pass,
itself capped at 40 cents. Everything else was free public data and arithmetic.
This company ran busier than most, since it spent the whole stretch approaching
its window; a company still a year or two out costs a fraction of that.

### Why the six-month horizon matters

An earlier version of this design triggered on the three-month probability. That
would have fired in November or December and produced contact in December at best —
**six weeks before the round, not three months.** Acting on the six-month horizon
instead is the entire difference between hitting the goal and missing it.

### The cases the system is designed to refuse

**Halden Compute** — strong company, growing fast, but the cap table is a regional
fund and angels with no Tier 1, and the last round was a flat extension. Fails the
screen at arrival and is never monitored. Perfect timing wouldn't help: without a
new Tier 1 leading, there's no co-investment for us.

**Southgate Robotics** — 22 months past its Series A and overdue, so a naive
"overdue means due" model would put it top of the list. But headcount has fallen
from 64 to 57, the Head of Finance left in September, and three roles closed with
none opened. That is a company in difficulty, not one preparing to raise. The
system suppresses it and never presents it to a partner.

Being right about those two is what makes the rest of the list worth reading.

---

## How we'll know if it works

One number, and it computes itself:

> **Of the rounds that closed among the companies we were watching, in what
> fraction did we have contact at least three months beforehand?**

Because public filings tell us exactly when each round closed, every case is scored
automatically with no manual tracking. At 100 companies on 18–24 month cycles we
should see **roughly 50–65 real rounds a year** — enough to report the hit rate from
the start, and enough to begin correcting the weightings after about 18 months.

Misses are labelled by cause — the signal arrived too late, no route existed, the
introduction never landed, or the company never crossed the threshold — because each
of those implies a different fix.

We also score how often we were right that a **new Tier 1** would lead, using the
board member named on the filing.

The system therefore starts as an informed estimate and becomes a measured one.
That accumulated history is proprietary — our own watch list, our own network, our
own outcomes — and it can't be bought.

One consequence worth acting on now: **expired job postings can't be recovered
later.** Every month we delay collecting is a month of history we can never get
back, which is why sampling starts before the model is finished.

---

## Being honest about the numbers

Roughly 5–8% of venture-backed companies raise in any given 90-day window. A good
model lifts that substantially among its top picks, and still **most flagged
companies won't raise inside the predicted window.**

That's acceptable because of how contact is framed: an introduction through an
investor we know, centred on the company and its work — never on a raise. If they
turn out not to be raising, we have simply met a good company early, which is a
thing we wanted anyway. **We never open with "we hear you're raising."**

Nothing is sent automatically. The system decides who is worth an hour of someone's
attention this week; a person still decides what to say.

---

## Cost and effort

| | |
|---|---|
| **New annual spend** | **~$120–150**, at 100 companies |
| Why so low | Filings and job-board data are free and public; the screen removes most companies before any monitoring runs; the roughly 500 routine reviews a year are capped at 15 cents each (~$75 at most); the full research pass only fires when something genuinely happens — roughly 60–90 times a year across the whole list — and is itself capped at 40 cents, not the open-ended cost we first floated |
| Scaling | Cost tracks *escalations and review count*, not company count directly, and every AI call carries its own hard cap. Going from 100 to 300 companies roughly triples the free work and adds well under $200 total |
| Tools reused | PitchBook, Apollo, Perplexity, our own hub and CRM. **No new vendor needed** for the core |
| Real cost | Engineering time, phased over roughly a quarter |
| First milestone | Detect a round on a watched company **before PitchBook records it**, and measure by how many days |

Full technical plan: `RADAR_PLAN.md`. The reasoning behind each signal:
`RADAR_SIGNAL_ENGINE.md`.
