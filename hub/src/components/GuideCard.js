import React from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './GuideCard.module.css';

// A designed artifact card: cover thumbnail + the formatted, downloadable edition.
export default function GuideCard({ title, meta, cover, docx, pdf }) {
  const coverUrl = useBaseUrl(cover);
  const docxUrl = useBaseUrl(docx);
  const pdfUrl = pdf ? useBaseUrl(pdf) : null;
  return (
    <div className={styles.card}>
      <div className={styles.coverWrap}>
        <a href={pdfUrl || docxUrl} target="_blank" rel="noopener noreferrer">
          <img className={styles.cover} src={coverUrl} alt={`${title} cover`} />
        </a>
      </div>
      <div className={styles.body}>
        <div className={styles.kicker}>Operating guide</div>
        <div className={styles.title}>{title}</div>
        <div className={styles.meta}>{meta}</div>
        <div className={styles.actions}>
          {pdfUrl && <a className={styles.link} href={pdfUrl} target="_blank" rel="noopener noreferrer">View PDF →</a>}
          <a className={pdfUrl ? styles.linkMuted : styles.link} href={docxUrl} download>Download Word →</a>
        </div>
      </div>
    </div>
  );
}
