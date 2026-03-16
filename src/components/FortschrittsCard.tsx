'use client';

interface FortschrittsCardProps {
  level: 'bronze' | 'silver' | 'gold' | 'platinum';
  points: number;
  nextLevelPoints: number;
  pointsNeeded: number;
  completedSteps: string[];
  pendingSteps: { text: string; points: number; action: string }[];
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
    <s-stack direction="block" gap="4">
      <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <s-heading size="md">Fortschritt</s-heading>
        <s-badge tone="warning" size="small">
          {tierLabel}
        </s-badge>
      </s-stack>

      <s-stack direction="block" gap="2">
        <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <s-paragraph tone="subdued">
            {pointsNeeded} Punkte bis {nextLevelLabel}
          </s-paragraph>
          <s-paragraph>
            <strong>{points}</strong> / {nextLevelPoints}
          </s-paragraph>
        </s-stack>
        <div className="piq-prog-track">
          <div className="piq-prog-fill" style={{ width: `${progressPercent}%` }} />
        </div>
      </s-stack>

      <s-divider />

      <s-stack direction="block" gap="0">
        {allTasks.map((task) => (
          <div key={task.id} className="piq-task">
            <div className={`piq-task-circle${task.done ? ' piq-task-circle--done' : ''}`}>
              {task.done && <div className="piq-task-check" />}
            </div>
            <s-stack direction="block" gap="0" style={{ flex: 1, minWidth: 0 }}>
              <s-paragraph
                tone={task.done ? 'subdued' : undefined}
                style={
                  task.done
                    ? { textDecoration: 'line-through', margin: 0 }
                    : { margin: 0 }
                }
              >
                {task.label}
                {task.sub != null && (
                  <span style={{ color: 'var(--p-color-text-subdued)', fontSize: '0.9em' }}>
                    {' '}{task.sub}
                  </span>
                )}
              </s-paragraph>
            </s-stack>
            {!task.done && task.points > 0 && (
              <s-badge tone="info" size="small">+{task.points}</s-badge>
            )}
          </div>
        ))}
      </s-stack>
    </s-stack>
  );
}
