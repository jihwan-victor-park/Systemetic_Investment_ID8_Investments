import AuthCard from '@/components/AuthCard';
import SignOutButton from '@/components/SignOutButton';
import cardStyles from '@/components/AuthCard.module.css';

export const metadata = { title: 'Access pending' };

export default function Pending() {
  return (
    <AuthCard headline={<>Request<br /><em>received.</em></>}>
      <p className={cardStyles.lede}>
        Thanks for signing in. Your access request has been sent to ID8 Investments for review —
        we&apos;ll follow up once it&apos;s approved.
      </p>
      <p className={cardStyles.detail}>
        Already approved? Sign out and back in to pick up the new access.
      </p>
      <SignOutButton className={cardStyles.ghostButton} />
    </AuthCard>
  );
}
