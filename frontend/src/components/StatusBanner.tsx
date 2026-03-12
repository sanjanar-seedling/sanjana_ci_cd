import { useEffect } from 'react';
import { AlertTriangle, Wrench } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';

export default function StatusBanner() {
  const { replannerInfo, setReplannerInfo } = usePipelineContext();

  useEffect(() => {
    if (!replannerInfo) return;
    const timer = setTimeout(() => setReplannerInfo(null), 10000);
    return () => clearTimeout(timer);
  }, [replannerInfo, setReplannerInfo]);

  if (!replannerInfo) return null;

  const hasStrategy = !!replannerInfo.strategy;

  return (
    <div
      className={`mx-5 mt-3 px-4 py-3 rounded-lg flex items-center gap-3 text-sm font-medium transition-all ${
        hasStrategy
          ? 'bg-amber-50 border border-amber-200 text-amber-800'
          : 'bg-orange-50 border border-orange-200 text-orange-800'
      }`}
    >
      {hasStrategy ? (
        <>
          <Wrench className="w-4 h-4 flex-shrink-0" />
          <span>
            Recovery: <span className="font-semibold">{replannerInfo.strategy}</span>
            {replannerInfo.reason && <span className="font-normal"> &mdash; {replannerInfo.reason}</span>}
          </span>
        </>
      ) : (
        <>
          <AlertTriangle className="w-4 h-4 flex-shrink-0 animate-pulse" />
          <span>
            Replanner active: Analyzing failure in{' '}
            <span className="font-semibold font-mono">{replannerInfo.stageId}</span>...
          </span>
        </>
      )}
    </div>
  );
}
