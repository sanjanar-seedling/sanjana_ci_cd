import { Wrench } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';

export default function StatusBanner() {
  const { recoveryPlans } = usePipelineContext();

  if (recoveryPlans.size === 0) return null;

  // Show the most recent recovery plan
  const entries = Array.from(recoveryPlans.entries());
  const [stageId, plan] = entries[entries.length - 1];

  return (
    <div className="mx-5 mt-3 px-4 py-3 rounded-lg flex items-center gap-3 text-sm font-medium transition-all bg-amber-50 border border-amber-200 text-amber-800">
      <Wrench className="w-4 h-4 flex-shrink-0" />
      <span>
        Recovery for <span className="font-semibold font-mono">{stageId}</span>:{' '}
        <span className="font-semibold">{plan.strategy.replace(/_/g, ' ')}</span>
        {plan.reason && <span className="font-normal"> &mdash; {plan.reason}</span>}
      </span>
    </div>
  );
}
