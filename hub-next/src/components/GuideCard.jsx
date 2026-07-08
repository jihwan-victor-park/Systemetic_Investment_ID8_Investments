import styles from './GuideCard.module.css';

// A designed artifact card: cover thumbnail + the formatted, downloadable edition.
export default function GuideCard({ title, meta, cover, docx, pdf }) {
  return (
    <div className={styles.card}>
      <div className={styles.coverWrap}>
        <a href={pdf || docx} target="_blank" rel="noopener noreferrer">
          <img className={styles.cover} src={cover} alt={`${title} cover`} />
        </a>
      </div>
      <div className={styles.body}>
        <div className={styles.kicker}>Operating guide</div>
        <div className={styles.title}>{title}</div>
        <div className={styles.meta}>{meta}</div>
        <div className={styles.actions}>
          {pdf && <a className={styles.link} href={pdf} target="_blank" rel="noopener noreferrer">View PDF →</a>}
          <a className={pdf ? styles.linkMuted : styles.link} href={docx} download>Download Word →</a>
        </div>
      </div>
    </div>
  );
}
