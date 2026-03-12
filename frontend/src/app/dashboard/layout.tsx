import Link from 'next/link';
import { InlineStack, Box } from '@shopify/polaris';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Box padding="400">
      <InlineStack gap="400" blockAlign="center">
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/dashboard/products">Produkte</Link>
        <Link href="/dashboard/analytics">Analysen</Link>
      </InlineStack>
      <Box paddingBlockStart="400">{children}</Box>
    </Box>
  );
}
