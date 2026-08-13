# Attio <-> Hub deal sync -- 2026-08-13

- Attio companies (deals grouped by company): **318**
- Hub companies (Firestore `companies`, round docs folded in): **314**
- Matched on both sides: **307** (302 by key, 4 by domain, 1 by name)
- **In Attio, missing from the hub: 8**
- **In the hub, missing from Attio: 1** (after setting aside 5 duplicate hub docs and 2 test fixtures)
- Placement disagreements among matched deals: **43** (agreed: 126)
- Matched but filed by hand in Attio (Passed/Invested -- rule not applied): 34
- **Missing their Attio deal history in the hub (pipeline/passed/invested tags): 30**
- Matched but the rule places them nowhere: 104 (17 above B with no Tier 1 (33), 87 below/unknown series)

Those five buckets partition the 307 matched companies (43 + 126 + 34 + 17 + 87 = 307), so no matched deal is missing from the report.

Placement rule applied: **Tier 1 (33) investor + above Series B -> Qualified**; **Top 10 investor + Series B or below -> Radar**. Series-B mode: `dual`.

## In Attio, missing from the hub

8 companies. All of them get created by `--apply-hub`: a deal that exists in Attio belongs in the hub regardless of whether the series rule can place it. `Created as` is the rule's placement when it has one, else Attio's own stage, else `new` (hub-next's triage bucket, which surfaces in the Admin page's Needs Triage table rather than blending into a real tab).

| Company | Domain | Series | Attio stage | Created as | Rule says | Top 10 / Tier 1 (33) |
|---|---|---|---|---|---|---|
| Impulse Space | impulsespace.com | Series D | Pipeline | qualified + pipeline | Qualified | Founders Fund, Lux Capital |
| Physical Intelligence | pi.website | Series B | Qualified | qualified + radar | Qualified | Index Ventures, ICONIQ Capital, Thrive Capital |
| Cathedral |  |  | Radar | radar | nothing -- series unknown -- cannot place from the rule | Sequoia Capital |
| OneBrief | onebrief.com |  | Pipeline | pipeline | nothing -- series unknown -- cannot place from the rule |  |
| Raindrop | raindrop.ai |  | Pipeline | pipeline | nothing -- series unknown -- cannot place from the rule |  |
| Replit | replit.com |  | Invested | invested | nothing -- series unknown -- cannot place from the rule |  |
| Together AI | together.ai |  | Invested | invested | nothing -- series unknown -- cannot place from the rule |  |
| Wonderful AI | wonderful.ai |  | Pipeline | pipeline | nothing -- series unknown -- cannot place from the rule |  |

## Colliding company keys

4 keys hold more than one domain. `fit_note.company_id` keys a company on `domain.split(".")[0]` -- only the first label -- which modern TLDs make collide. Each side is re-keyed here on its full domain so the two stop sharing one hub doc, but **company_id itself is unchanged**, so anything else importing these companies will collide again.

| Key | Domains | Names | Verdict |
|---|---|---|---|
| `onyx` | onyx.app + onyx.security | Onyx | same company, duplicate Attio records -- merge in Attio |
| `pi` | pi.security + pi.website | Physical Intelligence / Pi Security | **two different companies** |
| `simile` | simile.ai + simile.com | Simile | same company, duplicate Attio records -- merge in Attio |
| `warp` | warp.co + warp.dev | Warp / Warp (Business/Productivity Software) | same company, duplicate Attio records -- merge in Attio |

3 Attio records were set aside as duplicates of a company the hub already has, rather than created as new hub docs.

## Duplicate hub docs

5 companies hold 5 extra doc(s) between them -- one keyed by domain, its twin keyed by the name slug. `fit_note.company_id` prefers the domain and falls back to the name, and an Attio Deal carries no domain of its own, so a screening run that could not resolve it wrote a second doc. **`Stranded` is data sitting on the twin that the real company doc does not have** -- most importantly `latestScreen`, which is why these companies show no fit score in the hub despite having been screened. 4 of them would otherwise have reported as "missing from Attio", which they are not.

| Company | Real doc | Duplicate doc | Stranded on the duplicate | Screen on duplicate |
|---|---|---|---|---|
| Distyl AI | distyl (qualified) | distyl-ai | latestScreen | 3.6 gate=True |
| Firestorm | launchfirestorm (passed) | firestorm | - | - |
| Nexthop AI | nexthop (qualified) | nexthop-ai | latestScreen | 3.5 gate=True |
| Rogo (Business/Productivity Software) | rogo (watchlist) | rogo-business-productivity-software | latestScreen | 3.6 gate=True |
| SambaNova Systems | sambanova (qualified) | sambanova-systems | latestScreen | 3.5 gate=True |

## Test fixtures (not real deals)

2 hub companies on `.example` domains, left over from the screen-deals Firestore test backfill. Excluded from the hub-only list below -- Attio is right not to have them.

Brightline Health (`example-brightline-health`), Cascade Analytics (`example-cascade-analytics`)

## In the hub, missing from Attio

1 companies, after excluding the duplicate docs and test fixtures above.

| Company | Domain | Series | Hub stage | Hub tags | Origin | Should be in Attio |
|---|---|---|---|---|---|---|
| lassie | lassie.ai |  |  |  |  | -- |

## Placement disagreements

Matched on both sides, but at least one side isn't where the rule says it should be. `Hub needs` lists the tabs the company is missing from (hub membership is additive: stage + tags).

| Company | Series | Attio | Hub | Should be | Hub fix | Attio fix | Why |
|---|---|---|---|---|---|---|---|
| Actively AI | Series B | Target | new | Qualified + radar | stage -> qualified; +tag radar | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| AdvanCell | Series D | Radar | None | Qualified | stage -> qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Advanced Manufacturing Company of America | Series B | Pipeline | qualified +radar | Qualified + radar | - | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Anthropic | Series H | Qualified | None | Qualified | stage -> qualified | - | above Series B with a Tier 1 (33) investor |
| Braintrust (Software Development Applications) | Series B | Watchlist | None +watchlist,radar | Qualified + radar | stage -> qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Castelion | Series C | Pipeline | pipeline | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Chai Discovery | Series C | Radar | qualified | Qualified | - | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Console | Series A | Pipeline | pipeline | Radar | +tag radar | stage -> Radar | below Series B with a Top 10 investor |
| E2B | Early Stage VC | Watchlist | watchlist | Radar | +tag radar | stage -> Radar | below Series B with a Top 10 investor |
| ElevenLabs | Series D | Pipeline | pipeline | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Float.tech | Series A | Pipeline | pipeline +radar | Radar | - | stage -> Radar | below Series B with a Top 10 investor |
| Forus (Healthcare Technology Systems) | Series B | Watchlist | watchlist +radar | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Glow | Series B | Qualified | radar | Qualified + radar | +tag qualified | - | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Hadrian | Series D | Qualified | pipeline | Qualified | +tag qualified | - | above Series B with a Tier 1 (33) investor |
| Harvey | Series F | Target | new | Qualified | stage -> qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Helsing | Series E | Qualified | None | Qualified | stage -> qualified | - | above Series B with a Tier 1 (33) investor |
| Higgsfield | Series B | Pipeline | pipeline | Qualified + radar | +tag qualified, radar | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Higharc | Series C | Qualified | None | Qualified | stage -> qualified | - | above Series B with a Tier 1 (33) investor |
| ICON | Series D | Pipeline | pipeline | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Loop (Chicago) | Series C | Watchlist | watchlist | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Lovable | Series C | Pipeline | qualified | Qualified | - | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Mach Industries | Series C | Pipeline | qualified | Qualified | - | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Mind Robotics | Early Stage VC | Watchlist | watchlist | Radar | +tag radar | stage -> Radar | below Series B with a Top 10 investor |
| Mintlify | Series B | Target | new | Qualified + radar | stage -> qualified; +tag radar | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Monaco (Business/Productivity Software) | Series B | Watchlist | watchlist +radar | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Norm Ai | Series C | Qualified | None | Qualified | stage -> qualified | - | above Series B with a Tier 1 (33) investor |
| Ollama | Series B | Watchlist | radar +pipeline | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Omni Analytics | Later Stage VC | Watchlist | watchlist | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Onyx | Series B | Radar | pipeline +radar | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Pallet | Series C | Target | new | Qualified | stage -> qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Parallel | Series B | Watchlist | watchlist +radar | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Pi Security | Series B | Pipeline | qualified | Qualified + radar | +tag radar | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Profound | Series D | Pipeline | qualified | Qualified | - | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Revel (Business/Productivity Software) | Series B | Pipeline | pipeline +radar | Qualified + radar | +tag qualified | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Ricursive Intelligence | Series A | Watchlist | watchlist +radar | Radar | - | stage -> Radar | below Series B with a Top 10 investor |
| Rogo (Business/Productivity Software) | Series D | Watchlist | watchlist | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Sandstone (Business/Productivity Software) | Series A | Watchlist | watchlist +radar | Radar | - | stage -> Radar | below Series B with a Top 10 investor |
| Simile | Series B | Radar | pipeline | Qualified + radar | +tag qualified, radar | stage -> Qualified | Series B with a Top 10 investor (in mandate at B+, and just raised) |
| Snorkel | Series E | Pipeline | pipeline | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Supabase | Series F | Pipeline | pipeline | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Synthetix | Series C | Watchlist | watchlist | Qualified | +tag qualified | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Temporal | Series E | Pipeline | qualified | Qualified | - | stage -> Qualified | above Series B with a Tier 1 (33) investor |
| Trajectory | Series A | Pipeline | pipeline | Radar | +tag radar | stage -> Radar | below Series B with a Top 10 investor |

## Series disagreements (not auto-corrected)

13 companies where the hub and Attio hold a different Series. **Not written by --apply-hub.** `round` is hand-editable in the hub (RoundInput/updateCompanyRound) and the disagreements run in both directions -- some hub values are ahead of Attio, some behind -- so overwriting wholesale would destroy real research as often as it fixed staleness. Pass `--overwrite-series` to take Attio's value for all of them.

| Company | Hub says | Attio says | Attio stage |
|---|---|---|---|
| Chai Discovery | Series D | Series C | Radar |
| ClickHouse | Series C | Series D | Qualified |
| Fireworks AI | Series C | Series D | Qualified |
| Hadrian | Series B | Series D | Qualified |
| Iceye | Series E | Series F | Qualified |
| Lovable | Series B | Series C | Pipeline |
| MicroOne | Series B | Pre-B SAFE | Pipeline |
| Onyx | Series A | Series B | Radar |
| Profound | Series C | Series D | Pipeline |
| Ramp | Series E3 | Series F | Qualified |
| Simile | Series A | Series B | Radar |
| Temporal | Series D | Series E | Pipeline |
| Whatnot | Series F | Series G | Qualified |

## Missing or stale Series / Deal Date / Deal Size

25 companies where Attio has the round's close date (or size) and the hub doesn't. The hub renders these as its Deal Date column and the `closed <date>` line on the company page, so a company missing them shows a bare em-dash and sinks to the bottom of any date sort -- present, but effectively invisible. Filled only when missing, never overwritten.

| Company | Attio stage | Series to write | Deal Date to write | Deal Size to write |
|---|---|---|---|---|
| Advanced Manufacturing Company of America | Pipeline | - | 2026-08-12 (was stale) | - |
| Antora Energy | Qualified | - | 2026-07-30 | 550000000 |
| Base Power | Qualified | Series D | 2026-08-03 | 1000000000 |
| Braintrust (Software Development Applications) | Watchlist | Series B | 2026-02-17 | 80000000 |
| ClickHouse | Qualified | - | 2026-01-16 (was stale) | 400000000 (was stale) |
| Console | Pipeline | - | 2026-08-03 | 22999996 |
| Convex | Qualified | Series B | 2026-08-04 | 57000000 |
| DataBahn | Radar | - | 2026-07-30 | 40000000 |
| Hadrian | Qualified | - | 2026-08-06 (was stale) | 1370000000 |
| Iceye | Qualified | - | 2026-06-09 (was stale) | 1163110000 (was stale) |
| Inforcer | Qualified | - | 2026-07-30 | 48940000 |
| Jump | Qualified | - | 2026-02-23 (was stale) | 80000000 |
| K2 Space | Qualified | - | 2026-07-30 | 500000000 |
| Lovable | Pipeline | - | 2026-07-06 (was stale) | - |
| Lumilens | Qualified | Series C | 2026-08-06 | 700000000 |
| Mach Industries | Pipeline | - | 2026-08-12 (was stale) | - |
| Mariana Minerals | Qualified | Series B | 2026-08-03 | 310000000 |
| MicroOne | Pipeline | - | 2026-06-11 (was stale) | - |
| Ollama | Watchlist | - | 2026-07-14 (was stale) | - |
| Onyx | Radar | - | 2026-07-29 | 113000000 |
| Ramp | Qualified | - | 2026-06-04 (was stale) | 750000000 (was stale) |
| Simile | Radar | - | 2026-07-30 | 200000000 |
| Valar Atomics | Qualified | Series B | 2026-08-03 | 1200000000 |
| Whatnot | Qualified | - | 2026-08-07 (was stale) | 545000000 (was stale) |
| WindBorne Systems | Qualified | Series B | 2026-08-05 | 37000000 |

## Missing deal history (pipeline / passed / invested)

30 companies whose Attio stage implies a hub bucket the hub isn't carrying. This is separate from the placement rule above: the rule says where a deal *belongs* (qualified/radar), this says what actually *happened* to it. Both are additive in the hub, so a deal can be Qualified by the rule and Passed in fact. `passed` always brings `pipeline` with it -- passing on a deal means it was evaluated, so it belongs in Pipeline's history too.

| Company | Attio stage(s) | Hub now | Missing tags |
|---|---|---|---|
| AdvanCell | Radar | None | radar |
| Advanced Manufacturing Company of America | Pipeline, Qualified | qualified +radar | pipeline |
| Anthropic | Passed, Qualified | None | passed, pipeline, qualified |
| Castelion | Pipeline, Qualified | pipeline | qualified |
| Chai Discovery | Qualified, Radar | qualified | radar |
| Cloaked | Invested | passed +pipeline | invested |
| Commure | Invested | passed +pipeline | invested |
| DataBahn | Radar | qualified | radar |
| Databento | Qualified | None | qualified |
| Glow | Qualified | radar | qualified |
| Hadrian | Pipeline, Qualified | pipeline | qualified |
| Helsing | Qualified | None | qualified |
| Higharc | Qualified | None | qualified |
| Jump | Passed, Qualified | new | passed, pipeline, qualified |
| Kalshi | Pipeline, Qualified | qualified | pipeline |
| Legora | Passed, Qualified | qualified | passed, pipeline |
| Lovable | Pipeline, Qualified | qualified | pipeline |
| Mach Industries | Pipeline, Qualified | qualified | pipeline |
| Norm Ai | Qualified | None | qualified |
| Ollama | Radar, Watchlist | radar +pipeline | watchlist |
| Ollin | Qualified | None | qualified |
| Pi Security | Pipeline | qualified | pipeline |
| Pocket | Radar | None | radar |
| Profound | Pipeline, Qualified | qualified | pipeline |
| Rogo (Business/Productivity Software) | Qualified, Watchlist | watchlist | qualified |
| Sable AI | Radar | qualified | radar |
| Simile | Radar | pipeline | radar |
| Temporal | Pipeline, Qualified | qualified | pipeline |
| Warp | Qualified | None | qualified |
| nous research | Pipeline | None | pipeline |

## Above Series B, no Tier 1 (33) investor

17 matched companies clear the B+ mandate but have no Tier 1 (33) firm on the cap table, so the Qualified clause of the rule does not fire. The live intake path files these as Qualified anyway (`determine_placement` never checks Tier 1) -- this is the population affected by that difference.

| Company | Series | Attio | Hub | Investors on file |
|---|---|---|---|---|
| Akido | Series C | Target | new | none matched |
| Aspora | Series C | Pipeline | pipeline | none matched |
| Clay | Series D | Pipeline | pipeline | none matched |
| CodeRabbit | Series C | Pipeline | pipeline | none matched |
| Cornelius Networks | Series C | Pipeline | pipeline | none matched |
| FalconX | Series E | Pipeline | pipeline | none matched |
| Firestorm | NEA | Watchlist | watchlist | none matched |
| Frore | Series D | Pipeline | pipeline | none matched |
| Grafana | Series C | Target | new | none matched |
| Harbinger | Series D | Pipeline | pipeline | none matched |
| Inspiren | Series C | Pipeline | pipeline | none matched |
| Laurel | Series D | Target | new | none matched |
| MagicSchool | Series C | Target | new | none matched |
| Numa | Series C | Pipeline | pipeline | none matched |
| OXIO | Series C | Pipeline | pipeline | none matched |
| Path Robotics | Series E | Watchlist | watchlist | none matched |
| Retool | Series E | Watchlist | watchlist | none matched |

## Matched, but the rule places them nowhere

87 companies below Series B without a Top 10 backer, or with no usable series on file. They stay wherever they are today -- listed so the numbers above reconcile and so a wrong/blank Series is visible as the cause.

- Series B with a Tier 1 (33) but no Top 10 investor: **41**
- Series B with no Tier 1 (33) or Top 10 investor: **25**
- below Series B with no Top 10 investor: **11**
- series unknown -- cannot place from the rule: **10**

| Company | Series | Attio | Hub | Why |
|---|---|---|---|---|
| Aalyria | Series B | Watchlist | watchlist | Series B with a Tier 1 (33) but no Top 10 investor |
| Aikido Security | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Arch | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Attentive (Business/Productivity Software) | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Avoca | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| BNTO | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Blackbox | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Capital R3alm | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Celero | Series B | Qualified | qualified | Series B with no Tier 1 (33) or Top 10 investor |
| Cerby | Series B | Qualified | qualified | Series B with no Tier 1 (33) or Top 10 investor |
| Chemify | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| ClimAct Systems | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Convex | Series B | Qualified | qualified +radar | Series B with a Tier 1 (33) but no Top 10 investor |
| Corgi | Series B | Watchlist | watchlist | Series B with a Tier 1 (33) but no Top 10 investor |
| Courier Health | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| CuspAI | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| DataBahn | Series B | Radar | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Databento | Series B | Qualified | None | Series B with a Tier 1 (33) but no Top 10 investor |
| DeepInfra | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Depthfirst | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Doss | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Eridu | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Firecrawl | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Function Health | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Fundamental Research Labs | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| GenLogs | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| General Intuition | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| General Matter | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Generalist | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Gimlet Labs | Series B | Pipeline | pipeline | Series B with a Tier 1 (33) but no Top 10 investor |
| Glimpse | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| GreenLite Technologies | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Harmonic Security | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Heron Power | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Humanly | Series B | Target | new | Series B with no Tier 1 (33) or Top 10 investor |
| Jump | Series B | Qualified | new | Series B with a Tier 1 (33) but no Top 10 investor |
| Liberate Innovations | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Lighter (Financial Software) | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Lila Sciences | Series B | Pipeline | pipeline | Series B with a Tier 1 (33) but no Top 10 investor |
| Lyzr.ai | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Magnus Medical | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Monumental (Hardware) | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Namespace | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Ollin | Series B | Qualified | None | Series B with a Tier 1 (33) but no Top 10 investor |
| Omnea | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Orbem | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Osmo Labs | Series B | Qualified | qualified | Series B with no Tier 1 (33) or Top 10 investor |
| Panthalassa | Series B SAFE | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Prime Attorneys | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Prime Intellect | Series B | Target | new | Series B with no Tier 1 (33) or Top 10 investor |
| Pulley | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Quaise Energy | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Qualified Health | Series B | Pipeline | pipeline | Series B with a Tier 1 (33) but no Top 10 investor |
| RoboFlow | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Slide | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Spade Data | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Sunbeam | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Supio | Series B | Target | new | Series B with no Tier 1 (33) or Top 10 investor |
| Taxfyle | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Tempero Bio | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Triomics | Series B | Qualified | qualified | Series B with a Tier 1 (33) but no Top 10 investor |
| Upcodes | Series B | Pipeline | pipeline | Series B with no Tier 1 (33) or Top 10 investor |
| Warp | Series B | Qualified | None | Series B with a Tier 1 (33) but no Top 10 investor |
| WindBorne Systems | Series B | Qualified | qualified +radar | Series B with a Tier 1 (33) but no Top 10 investor |
| Xbow | Series B | Target | new | Series B with no Tier 1 (33) or Top 10 investor |
| nous research | Series B | Pipeline | None | Series B with no Tier 1 (33) or Top 10 investor |
| Copperlane | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Cosmic Labs | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Dili | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| MicroOne | Pre-B SAFE | Pipeline | pipeline | below Series B with no Top 10 investor |
| ModRetro | Early Stage VC | Watchlist | watchlist | below Series B with no Top 10 investor |
| Newcore | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Noah Labs | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Project Prometheus | Early Stage VC | Watchlist | watchlist | below Series B with no Top 10 investor |
| Silicondata | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Tenkara Labs | Series A | Pipeline | pipeline | below Series B with no Top 10 investor |
| Walden Robotics | Seed | Pipeline | pipeline | below Series B with no Top 10 investor |
| Consensus.app | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Draftwise | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Fyxer AI | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Instinct | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Nucleus Genomics | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Pocket | (blank) | Radar | None | series unknown -- cannot place from the rule |
| Sable AI | (blank) | Radar | qualified | series unknown -- cannot place from the rule |
| Tavily | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |
| Vapi | (blank) | Qualified | qualified | series unknown -- cannot place from the rule |
| Wealth.com | (blank) | Pipeline | pipeline | series unknown -- cannot place from the rule |

## Series B with a Top 10 investor

58 companies sit in the one band the rule reads two ways. Under `dual` (the default, and what the shipped intake code does) they are Qualified in Attio and additionally tagged `radar` in the hub. Under `radar` they would be Radar only. Rerun with `--series-b-mode radar` to see that version.

| Company | Series | Attio | Hub | Top 10 |
|---|---|---|---|---|
| Actively AI | Series B | Target | new | Bain Capital Ventures |
| Advanced Manufacturing Company of America | Series B | Pipeline | qualified +radar | Lightspeed Venture Partners |
| Allegro Labs | Series B | Qualified | qualified +radar | Index Ventures |
| AltaClaro | Series B | Qualified | qualified +radar | Bessemer Venture Partners |
| Archy | Series B | Qualified | qualified +radar | Bessemer Venture Partners |
| Astrocade | Series B | Qualified | qualified +radar | Sequoia Capital |
| Auterion | Series B | Qualified | qualified +radar | Bessemer Venture Partners |
| Basis (Financial Software) | Series B | Qualified | qualified +radar | Accel |
| Bezi | Series B | Passed | passed +passed,pipeline | Bessemer Venture Partners |
| Black Forest Labs | Series B | Qualified | qualified +radar | Bain Capital Ventures |
| Braintrust (Software Development Applications) | Series B | Watchlist | None +watchlist,radar | ICONIQ Capital |
| Bunkerhill Health | Series B1 | Qualified | qualified +radar | Sequoia Capital |
| Campfire (Financial Software) | Series B | Qualified | qualified +radar | Accel |
| Cowboy Space | Series B | Qualified | qualified +radar | Index Ventures |
| Distyl AI | Series B | Qualified | qualified +radar | Lightspeed Venture Partners |
| EXUGlobal | Series B | Qualified | qualified +radar | Sequoia Capital |
| Emergent (Software Development Applications) | Series B | Qualified | qualified +radar | Lightspeed Venture Partners |
| Evervault | Series B | Qualified | qualified +radar | Sequoia Capital, Index Ventures |
| Forus (Healthcare Technology Systems) | Series B | Watchlist | watchlist +radar | Accel, Thrive Capital, Bain Capital Ventures |
| Foxglove | Series B | Qualified | qualified +radar | Bessemer Venture Partners |
| Fractile | Series B | Qualified | qualified +radar | Accel |
| Gamma Tech. | Series B | Qualified | qualified +radar | Accel |
| Glow | Series B | Qualified | radar +radar | Sequoia Capital, Index Ventures, Greenoaks Capital Partners |
| Higgsfield | Series B | Pipeline | pipeline | Accel |
| House Rx | Series B | Qualified | qualified +radar | Bessemer Venture Partners |
| Juicebox | Series B | Qualified | qualified +radar | Sequoia Capital |
| LangChain | Series B | Qualified | qualified +radar | Sequoia Capital, Benchmark |
| Lead Bank | Series B | Qualified | qualified +radar | ICONIQ Capital |
| Linx Security | Series B | Qualified | qualified +radar | Index Ventures |
| Listen Labs | Series B | Qualified | qualified +radar | Sequoia Capital |
| Mariana Minerals | Series B | Qualified | qualified +radar | Greenoaks Capital Partners |
| Mintlify | Series B | Target | new | Bain Capital Ventures |
| Monaco (Business/Productivity Software) | Series B | Watchlist | watchlist +radar | Benchmark, Greenoaks Capital Partners |
| Naboo | Series B | Qualified | qualified +radar | Lightspeed Venture Partners |
| Nexthop AI | Series B | Qualified | qualified +radar | Lightspeed Venture Partners |
| Nominal | Series B | Qualified | qualified +radar | Sequoia Capital, Lightspeed Venture Partners |
| Ollama | Series B | Watchlist | radar +pipeline | Benchmark |
| Onyx | Series B | Radar | pipeline +radar | Bessemer Venture Partners |
| Pace | Series B | Qualified | qualified +radar | Sequoia Capital, Thrive Capital |
| Parallel | Series B | Watchlist | watchlist +radar | Sequoia Capital, Index Ventures |
| PermitFlow | Series B | Passed | passed +passed,pipeline | Accel |
| Pi Security | Series B | Pipeline | qualified | Index Ventures, ICONIQ Capital, Thrive Capital |
| PointFive | Series B | Qualified | qualified +radar | Index Ventures, Accel |
| Reducto | Series B | Qualified | qualified +radar | Benchmark |
| Reflection AI | Series B | Invested | invested | Sequoia Capital, Lightspeed Venture Partners |
| Revel (Business/Productivity Software) | Series B | Pipeline | pipeline +radar | Index Ventures, Thrive Capital |
| Serval | Series B | Qualified | qualified +radar | Sequoia Capital |
| Sesame AI | Series B | Qualified | qualified +radar | Sequoia Capital |
| Simile | Series B | Radar | pipeline | Index Ventures, Bain Capital Ventures, Greenoaks Capital Partners |
| Sunday (Hardware) | Series B | Qualified | qualified +radar | Benchmark, Bain Capital Ventures |
| Sunflower Labs | Series B | Qualified | qualified +radar | Sequoia Capital |
| TRIANA Biomedicines | Series B | Qualified | qualified +radar | Lightspeed Venture Partners, Bessemer Venture Partners |
| Twenty (Network Management Software) | Series B | Qualified | qualified +radar | Accel |
| Upwind Security | Series B | Passed | passed +passed,pipeline | Sequoia Capital, Bessemer Venture Partners |
| Valar Atomics | Series B | Qualified | qualified +radar | Sequoia Capital |
| Weaviate | Series B | Qualified | qualified +radar | Index Ventures |
| WithCoverage | Series B | Qualified | qualified +radar | Sequoia Capital |
| tem (Business/Productivity Software) | Series B | Qualified | qualified +radar | Lightspeed Venture Partners |

## Filed by hand in Attio (Passed / Invested)

34 matched companies carry a stage the series rule must not override. Listed so nothing is invisible; no action proposed.

Airwallex (Passed), Assort Health (Passed), Bedrock Robotics (Passed), Bezi (Passed), ChipAgents (Passed), Cloaked (Invested), Commure (Invested), Coretsu (Logical Intelligence) (Passed), Crusoe Energy (Passed), Decart.ai (Passed), Erebor (Passed), Eudia (Passed), Firestorm (Passed), Hayden AI (Passed), Klir (Passed), Letter AI (Passed), Maybern (Passed), Northwood (Passed), Parloa (Passed), Pepper (Passed), Periodic Labs (Passed), PermitFlow (Passed), Polymarket (Invested), Radiant (Passed), Reflection AI (Invested), Saronic (Invested), Skild AI (Passed), Sprouts.ai (Passed), Stacklet (Passed), Standard Bots (Passed), Stepful (Passed), Upwind Security (Passed), Varda Space (Passed), Vatn (Passed)
