'use client';

interface FortschrittsCardProps {
  level: 'bronze' | 'silver' | 'gold' | 'platinum';
  points: number;
  nextLevelPoints: number;
  pointsNeeded: number;
  completedSteps: string[];
  pendingSteps: { text: string; points: number; action: string }[];
  onPriceAction?: () => void;
  onProductsAction?: () => void;
  onSettingsAction?: () => void;
}

const TIER_LABELS: Record<string, string> = {
  bronze: 'Bronze', silver: 'Silber', gold: 'Gold', platinum: 'Platin',
};
const NEXT_LABELS: Record<string, string> = {
  bronze: 'Silber', silver: 'Gold', gold: 'Platin', platinum: 'Max',
};

function StarIcon() {
  return (
    <svg width="8" height="8" viewBox="0 0 10 10" fill="currentColor">
      <polygon points="5,0.5 6.5,3.8 9.8,4.3 7.4,6.6 8,9.9 5,8.2 2,9.9 2.6,6.6 0.2,4.3 3.5,3.8" />
    </svg>
  );
}

function PriceIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <path d="M7 1v3M7 10v3M1 7h3M10 7h3M2.8 2.8l2.1 2.1M9.1 9.1l2.1 2.1M2.8 11.2l2.1-2.1M9.1 4.9l2.1-2.1" />
    </svg>
  );
}

function SyncIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 7A5 5 0 0 1 2 7M2 7A5 5 0 0 1 12 7M9.5 4.5l2.5 2.5-2.5 2.5M4.5 9.5L2 7l2.5-2.5" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <circle cx="7" cy="7" r="2" />
      <path d="M7 1v2M7 11v2M1 7h2M11 7h2M2.8 2.8l1.4 1.4M9.8 9.8l1.4 1.4M2.8 11.2l1.4-1.4M9.8 4.2l1.4-1.4" />
    </svg>
  );
}

export function FortschrittsCard({
  level,
  points,
  nextLevelPoints,
  pointsNeeded,
  completedSteps,
  pendingSteps,
  onPriceAction,
  onProductsAction,
  onSettingsAction,
}: FortschrittsCardProps) {
  const tierLabel      = TIER_LABELS[level] ?? 'Bronze';
  const nextLevelLabel = NEXT_LABELS[level] ?? 'Silber';
  const progressPercent = nextLevelPoints > 0
    ? Math.min((points / nextLevelPoints) * 100, 100)
    : 0;

  return (
    <div className="piq-card piq-progress-card">

      {/* ── Card Header ── */}
      <div className="piq-card-head">
        <div className="piq-prog-head">
          <div className="piq-card-ttl">Fortschritt</div>
          <div className="piq-tier">
            <StarIcon />
            {tierLabel}
          </div>
        </div>
        <div className="piq-prog-pts">{points} / {nextLevelPoints}</div>
      </div>

      {/* ── Progress Bar ── */}
      <div className="piq-prog-section">
        <div className="piq-prog-track">
          <div className="piq-prog-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="piq-prog-hint">{pointsNeeded} Punkte bis {nextLevelLabel}</div>
      </div>

      {/* ── Task List ── */}
      <div className="piq-card-body">
        {(completedSteps ?? []).map((step, i) => (
          <div key={`done-${i}`} className="piq-task">
            <div className="piq-task-circle piq-task-circle--done">
              <div className="piq-task-check" />
            </div>
            <span className="piq-task-label piq-task-label--done">
              {String(step).replace(/^✅\s*/, '')}
            </span>
          </div>
        ))}

        {(pendingSteps ?? []).map((step, i) => (
          <div key={`pending-${i}`} className="piq-task">
            <div className="piq-task-circle" />
            <span className="piq-task-label">{step.text}</span>
            {step.points > 0 && (
              <span className="piq-task-pts">+{step.points}</span>
            )}
          </div>
        ))}
      </div>

      {/* ── Schnellaktionen ── */}
      <div className="piq-qa-wrap">
        <div className="piq-qa-lbl">Schnellaktionen</div>
        <div className="piq-qa-grid">
          <button className="piq-qa-btn" onClick={onPriceAction} type="button">
            <PriceIcon /> Preise
          </button>
          <button className="piq-qa-btn" onClick={onProductsAction} type="button">
            <SyncIcon /> Produkte
          </button>
          <button className="piq-qa-btn" onClick={onSettingsAction} type="button">
            <SettingsIcon /> Einstellungen
          </button>
        </div>
      </div>

    </div>
  );
}
