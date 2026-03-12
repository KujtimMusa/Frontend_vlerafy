'use client';

import { AppProvider } from '@shopify/polaris';
import '@shopify/polaris/build/esm/styles.css';
import de from '@shopify/polaris/locales/de.json';

export default function PolarisProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppProvider i18n={de}>{children}</AppProvider>;
}
