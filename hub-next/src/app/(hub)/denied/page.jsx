import AuthCard from '@/components/AuthCard';
import SignOutButton from '@/components/SignOutButton';
import cardStyles from '@/components/AuthCard.module.css';

export const metadata = { title: 'Access not granted' };

export default function Denied() {
  return (
    <AuthCard headline={<>Access not<br /><em>granted.</em></>}>
      <p className={cardStyles.lede}>
        This account hasn&apos;t been approved to access ID8&apos;s research hub. If you believe
        this is a mistake, reach out to <a href="mailto:hello@id8investments.com">hello@id8investments.com</a>.
      </p>
      <SignOutButton className={cardStyles.ghostButton} />
    </AuthCard>
  );
}
