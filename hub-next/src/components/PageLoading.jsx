import styles from './PageLoading.module.css';

// Next.js renders this automatically (via the sibling loading.jsx in each
// stage-table route) the instant a sidebar link is clicked, while the
// route's page.jsx (and its Firestore fetch) is still resolving -- so
// switching tabs feels instant and only the content area shows a spinner,
// instead of the whole navigation appearing to hang until data is ready.
export default function PageLoading() {
  return (
    <div className={styles.wrap}>
      <span className={styles.spinner} />
      <span>Loading…</span>
    </div>
  );
}
