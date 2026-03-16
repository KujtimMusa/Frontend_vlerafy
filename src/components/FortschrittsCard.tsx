'use client';

interface FortschrittsCardProps {
  level: 'bronze' | 'silver' | 'gold' | 'platinum';
  points: number;
  nextLevelPoints: number;
  pointsNeeded: number;
  completedSteps: string[];
  pendingSteps: { text: string; points: number; action: string }[];
}

function StarIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
      <path d="M5 0l1.5 3L10 4l-2.5 2.5L8 10 5 8 2 10l.5-3.5L0 4l3.5-1L5 0z" />
    </svg>
  );
}

const TIER_LABELS: Record<string, string> = {
  bronze: 'Bronze',
  silver: 'Silber',
  gold: 'Gold',
  platinum: 'Platin',
};

export function FortschrittsCard({
  level,
  points,
  nextLevelPoints,
  pointsNeeded,
  completedSteps,
  pendingSteps,
}: FortschrittsCardProps) {
  const tierLabel = TIER_LABELS[level] ?? 'Bronze';
  const nextLevelLabel =
    level === 'bronze'
      ? 'Silber'
      : level === 'silver'
        ? 'Gold'
        : level === 'gold'
          ? 'Platin'
          : 'Max';
  const progressPercent = nextLevelPoints > 0 ? Math.min((points / nextLevelPoints) * 100, 100) : 0;

  const completedTasks = (completedSteps ?? []).map((step) => ({
    id: step,
    label: String(step).replace(/^✅\s*/, ''),
    done: true,
    points: 0,
    sub: undefined as string | undefined,
  }));

  const pendingTasks = (pendingSteps ?? []).map((step) => ({
    id: step.text,
    label: step.text,
    done: false,
    points: step.points,
    sub: undefined as string | undefined,
  }));

  const allTasks = [...completedTasks, ...pendingTasks];

  return (
    <>
      <div className="piq-card-head">
        <div className="piq-prog-head">
          <div className="piq-card-ttl">Fortschritt</div>
          <span className="piq-tier">
            <StarIcon />
            {tierLabel}
          </span>
        </div>
        <div className="piq-prog-pts">{points} / {nextLevelPoints} Pkt.</div>
      </div>

      <div className="piq-prog-section">
        <div className="piq-prog-track">
          <div className="piq-prog-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="piq-prog-hint">
          {pointsNeeded} Punkte bis {nextLevelLabel}
        </div>
      </div>

      <div className="piq-card-body">
        {allTasks.map((task) => (
          <div key={task.id} className="piq-task">
            <div className={`piq-task-circle${task.done ? ' piq-task-circle--done' : ''}`}>
              {task.done && <div className="piq-task-check" />}
            </div>
            <div className={`piq-task-label${task.done ? ' piq-task-label--done' : ''}`}>
              {task.label}
              {task.sub != null && <span className="piq-task-label-dim"> {task.sub}</span>}
            </div>
            {!task.done && task.points > 0 && (
              <span className="piq-task-pts">+{task.points}</span>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
