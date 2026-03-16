'use client';

interface FortschrittsCardProps {
  level: 'bronze' | 'silver' | 'gold' | 'platinum';
  points: number;
  nextLevelPoints: number;
  pointsNeeded: number;
  completedSteps: string[];
  pendingSteps: { text: string; points: number; action: string }[];
}

const TIER_CONFIG: Record<string, { label: string; className: string; emoji: string }> = {
  bronze: { label: 'Bronze', className: 'priceiq-tier-badge', emoji: '🥉' },
  silver: { label: 'Silber', className: 'priceiq-tier-badge priceiq-tier-badge--silver', emoji: '🥈' },
  gold: { label: 'Gold', className: 'priceiq-tier-badge priceiq-tier-badge--gold', emoji: '🥇' },
  platinum: { label: 'Platin', className: 'priceiq-tier-badge priceiq-tier-badge--platinum', emoji: '🏆' },
};

export function FortschrittsCard({
  level,
  points,
  nextLevelPoints,
  pointsNeeded,
  completedSteps,
  pendingSteps,
}: FortschrittsCardProps) {
  const tier = TIER_CONFIG[level] ?? TIER_CONFIG.bronze;
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
    subtext: undefined as string | undefined,
  }));

  const pendingTasks = (pendingSteps ?? []).map((step) => ({
    id: step.text,
    label: step.text,
    done: false,
    points: step.points,
    subtext: undefined as string | undefined,
  }));

  const allTasks = [...completedTasks, ...pendingTasks];

  return (
    <s-section>
      <s-stack direction="block" gap="4">
        {/* Header mit Tier-Badge */}
        <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <s-heading size="md">Dein Fortschritt</s-heading>
          <span className={tier.className}>
            {tier.emoji} {tier.label}
          </span>
        </s-stack>

        {/* Progress mit Milestone */}
        <s-stack direction="block" gap="2">
          <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <s-paragraph tone="subdued">
              {pointsNeeded} Punkte bis {nextLevelLabel}
            </s-paragraph>
            <span style={{ fontSize: 13, fontWeight: 600 }}>{points}/{nextLevelPoints}</span>
          </s-stack>
          <div className="priceiq-progress-track" style={{ position: 'relative' }}>
            <div
              className="priceiq-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
            <div
              className="priceiq-milestone-marker"
              style={{
                left: '50%',
                background: progressPercent >= 50 ? 'var(--v-success)' : 'var(--v-gray-200)',
              }}
            />
          </div>
        </s-stack>

        <s-divider />

        {/* Task List */}
        <s-stack direction="block" gap="0">
          {allTasks.map((task) => (
            <div key={task.id} className="priceiq-task-item">
              <div className={`priceiq-task-check ${task.done ? 'priceiq-task-check--done' : ''}`}>
                {task.done && <span style={{ fontSize: '11px', color: 'white' }}>✓</span>}
              </div>
              <s-stack direction="block" gap="0" style={{ flex: 1 }}>
                <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: task.done ? 400 : 500,
                      color: task.done ? 'var(--v-gray-400)' : 'var(--v-gray-950)',
                      textDecoration: task.done ? 'line-through' : 'none',
                    }}
                  >
                    {task.label}
                  </span>
                  {!task.done && (
                    <s-badge tone="info">+{task.points} Pkt.</s-badge>
                  )}
                </s-stack>
                {task.subtext && !task.done && (
                  <s-paragraph tone="subdued">{task.subtext}</s-paragraph>
                )}
              </s-stack>
            </div>
          ))}
        </s-stack>
      </s-stack>
    </s-section>
  );
}
