import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Performance Monitoring – 10 % der Transaktionen tracken
  tracesSampleRate: 0.1,

  // Session Replay – 1 % normaler, 100 % Fehler-Sessions
  replaysSessionSampleRate: 0.01,
  replaysOnErrorSampleRate: 1.0,

  // Nur in Production aktiv
  enabled: process.env.NODE_ENV === "production",

  integrations: [
    Sentry.replayIntegration(),
  ],
});
