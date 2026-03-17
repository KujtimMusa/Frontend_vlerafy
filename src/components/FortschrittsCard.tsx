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

function TierIcon({ level }: { level: string }) {
  const colors: Record<string, string> = {
    bronze: '#cd7f32', silver: '#94a3b8', gold: '#f59e0b', platinum: '#6366f1',
  };
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill={colors[level] ?? '#cd7f32'}>
      <polygon points="5,0.5 6.5,3.5 9.8,4 7.4,6.3 8.1,9.8 5,8.1 1.9,9.8 2.6,6.3 0.2,4 3.5,3.5" />
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

      {/* ── Header ── */}
      <div className="piq-card-head">
        <div className="piq-prog-head">
          <div className="piq-card-ttl">Fortschritt</div>
          <div className="piq-tier">
            <TierIcon level={level} />
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
          <s-button variant="secondary" size="slim" onClick={onPriceAction}>
            Preise
          </s-button>
          <s-button variant="secondary" size="slim" onClick={onProductsAction}>
            Produkte
          </s-button>
          <s-button variant="secondary" size="slim" onClick={onSettingsAction}>
            Einstellungen
          </s-button>
        </div>
      </div>

    </div>
  );
}
