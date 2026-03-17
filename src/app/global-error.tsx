'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <div style={{ padding: 32, textAlign: 'center' }}>
          <h2>Etwas ist schiefgelaufen.</h2>
          <button onClick={() => reset()} style={{ marginTop: 16 }}>
            Erneut versuchen
          </button>
        </div>
      </body>
    </html>
  );
}
