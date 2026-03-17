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
const TIER_COLORS: Record<string, string> = {
  bronze: '#cd7f32', silver: '#94a3b8', gold: '#f59e0b', platinum: '#6366f1',
};

function TierStar({ level }: { level: string }) {
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill={TIER_COLORS[level] ?? '#cd7f32'}>
      <polygon points="5.5,0.5 7,3.8 10.5,4.3 8,6.8 8.6,10.3 5.5,8.6 2.4,10.3 3,6.8 0.5,4.3 4,3.8" />
    </svg>
  );
}

function PriceActionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 1.5v15M12.5 5.5c0-1.1-.9-2-2-2H7.5a2 2 0 0 0 0 4h3a2 2 0 0 1 0 4H6" />
    </svg>
  );
}

function ProductActionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#d97706" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h3l2 9h7l1.5-6H6.5" />
      <circle cx="9" cy="15.5" r="1" />
      <circle cx="14" cy="15.5" r="1" />
    </svg>
  );
}

function SettingsActionIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#6b7280" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="9" r="3" />
      <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.5 3.5l1.4 1.4M13.1 13.1l1.4 1.4M3.5 14.5l1.4-1.4M13.1 4.9l1.4-1.4" />
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

  const actions = [
    { label: 'Preise', sub: 'Empfehlungen', icon: <PriceActionIcon />, color: 'green', onClick: onPriceAction },
    { label: 'Produkte', sub: 'Synchronisieren', icon: <ProductActionIcon />, color: 'amber', onClick: onProductsAction },
    { label: 'Einstellungen', sub: 'Konfiguration', icon: <SettingsActionIcon />, color: 'gray', onClick: onSettingsAction },
  ] as const;

  return (
    <div className="piq-card piq-progress-card">

      {/* ── Header ── */}
      <div className="piq-card-head">
        <div className="piq-prog-head">
          <div className="piq-card-ttl">Fortschritt</div>
          <div className="piq-tier">
            <TierStar level={level} />
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

      {/* ── Schnellaktionen — Icon Cards ── */}
      <div className="piq-qa-wrap">
        <div className="piq-qa-lbl">Schnellaktionen</div>
        <div className="piq-qa-grid">
          {actions.map((action) => (
            <div
              key={action.label}
              className="piq-qa-card"
              onClick={action.onClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && action.onClick?.()}
              aria-label={action.label}
            >
              <div className={`piq-qa-icon piq-qa-icon--${action.color}`}>
                {action.icon}
              </div>
              <div className="piq-qa-ttl">{action.label}</div>
              <div className="piq-qa-sub">{action.sub}</div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
