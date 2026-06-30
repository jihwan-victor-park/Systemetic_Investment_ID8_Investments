import QualityFunnel from "@/components/QualityFunnel";
import ConnectGraph from "@/components/ConnectGraph";
import RubricCards from "@/components/RubricCards";
import styles from "./page.module.css";

export const metadata = { title: "For Investors" };

export default function Investors() {
  return (
    <main className={styles.page}>
      <div className={styles.kicker}>ID8 Investments&nbsp;&nbsp;|&nbsp;&nbsp;Applied AI</div>
      <h1 className={styles.headline}>Sourcing,<br /><em>run by AI.</em></h1>
      <p className={styles.lede}>
        Good returns start with good sourcing, and good sourcing is a system, not luck. AI agents work
        every stage of how we find and pick deals: scanning the market, scoring on one rubric, researching
        the strongest, and surfacing the few that earn conviction.
      </p>

      <section className={styles.section}>
        <div className={styles.eyebrow}>01 The funnel</div>
        <h2 className={styles.subhead}>Every deal meets the same bar.</h2>
        <p className={styles.body}>
          The whole market flows in. AI scores each deal against one rubric, the strongest advance to deep,
          evidence-based diligence, and only the few that earn conviction make it through. The standard is
          identical every time, so quality is the process, not a hunch.
        </p>
        <div className={styles.visual}><QualityFunnel /></div>
      </section>

      <section className={styles.section}>
        <div className={styles.eyebrow}>02 The network</div>
        <h2 className={styles.subhead}>We connect the dots others miss.</h2>
        <p className={styles.body}>
          Behind every deal is a web of people, rounds, and signals. Our AI maps those connections
          continuously and lights up the ones that matter most, turning a scattered field into a clear
          view of where the strongest opportunities and warmest paths actually are.
        </p>
        <div className={styles.visual}><ConnectGraph /></div>
      </section>

      <section className={styles.section}>
        <div className={styles.eyebrow}>03 The standard</div>
        <h2 className={styles.subhead}>Five dimensions, one bar.</h2>
        <p className={styles.body}>
          Every deal is measured the same way, across the same five dimensions, every time.
          It's how conviction gets built on evidence, not instinct.
        </p>
        <div className={styles.cardsWrap}><RubricCards /></div>
      </section>

      <div className={styles.closing}>
        <p className={styles.closingText}>
          This is infrastructure we built and own. It compounds with every deal we see, so our sourcing
          and our judgment get sharper over time.
        </p>
      </div>
    </main>
  );
}
