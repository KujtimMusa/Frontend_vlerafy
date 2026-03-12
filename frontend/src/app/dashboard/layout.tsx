import Link from 'next/link';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <s-nav-menu>
        <Link href="/dashboard" rel="home">
          Dashboard
        </Link>
        <Link href="/dashboard/products">Produkte</Link>
        <Link href="/dashboard/analytics">Analysen</Link>
      </s-nav-menu>
      {children}
    </>
  );
}
