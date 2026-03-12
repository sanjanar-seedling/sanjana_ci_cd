import { useState } from 'react';
import { Loader2, Rocket, Code2, Container, Tag } from 'lucide-react';
import { usePipeline } from '../hooks/usePipeline';
import { usePipelineContext } from '../context/PipelineContext';

const LANGUAGES = [
  { name: 'JavaScript', color: 'bg-yellow-100 text-yellow-800' },
  { name: 'TypeScript', color: 'bg-blue-100 text-blue-800' },
  { name: 'Python', color: 'bg-green-100 text-green-800' },
  { name: 'Java', color: 'bg-red-100 text-red-800' },
  { name: 'Go', color: 'bg-cyan-100 text-cyan-800' },
  { name: 'Rust', color: 'bg-orange-100 text-orange-800' },
];

interface CreatePipelineProps {
  prefill?: { repoUrl: string; goal: string; name: string; useDocker: boolean };
}

export default function CreatePipeline({ prefill }: CreatePipelineProps) {
  const [repoUrl, setRepoUrl] = useState(prefill?.repoUrl ?? '');
  const [goal, setGoal] = useState(prefill?.goal ?? '');
  const [name, setName] = useState(prefill?.name ?? '');
  const [useDocker, setUseDocker] = useState(prefill?.useDocker ?? false);
  const { loading, error, generate, setError } = usePipeline();
  const { setPipeline } = usePipelineContext();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !goal.trim()) return;
    setError(null);
    const spec = await generate(repoUrl.trim(), goal.trim(), useDocker, name.trim());
    if (spec) {
      setPipeline(spec);
    }
  };

  return (
    <div className="flex items-center justify-center h-full p-8">
      <div className="w-full max-w-lg">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <Rocket className="w-8 h-8 text-accent" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">
            {prefill ? 'Regenerate Pipeline' : 'Create Pipeline'}
          </h2>
          <p className="text-gray-500 mt-1">
            {prefill
              ? 'Re-analyze the repo and generate a fresh pipeline'
              : 'Analyze a repo and generate a CI/CD pipeline'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Pipeline Name
              <span className="text-gray-400 font-normal ml-1">(optional)</span>
            </label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Flask CI, Express Deploy"
                className="w-full pl-9 pr-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Repository URL
            </label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo"
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Deployment Goal
            </label>
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Deploy to AWS ECS staging"
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none transition-shadow"
              disabled={loading}
            />
          </div>

          <label className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <div className="relative">
              <input
                type="checkbox"
                checked={useDocker}
                onChange={(e) => setUseDocker(e.target.checked)}
                disabled={loading}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-300 rounded-full peer-checked:bg-accent transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <div className="flex items-center gap-2">
              <Container className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-700">Run in Docker containers</span>
            </div>
          </label>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !repoUrl.trim() || !goal.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-accent hover:bg-accent/90 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing repository...
              </>
            ) : prefill ? (
              'Regenerate Pipeline'
            ) : (
              'Generate Pipeline'
            )}
          </button>
        </form>

        {/* Supported Languages */}
        {!prefill && (
          <div className="mt-6 text-center">
            <div className="flex items-center justify-center gap-1.5 text-xs text-gray-400 mb-3">
              <Code2 className="w-3.5 h-3.5" />
              Supported Languages
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {LANGUAGES.map((lang) => (
                <span
                  key={lang.name}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium ${lang.color}`}
                >
                  {lang.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
