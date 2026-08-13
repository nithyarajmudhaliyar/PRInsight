/**
 * Loading screen shown while the backend is analyzing a Pull Request.
 *
 * Steps are passed in as a prop (from useAnalyze) instead of being
 * imported from mockData, keeping this component decoupled from data sources.
 */
export default function LoadingScreen({ completedSteps, currentStep, steps }) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-5 animate-fade-in" id="loading-screen">
      <div className="flex w-full max-w-md flex-col items-center gap-8">
        {/* Spinner */}
        <div className="relative h-20 w-20">
          <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-[var(--color-blue)] animate-spin-slow" />
          <div className="absolute inset-2.5 rounded-full border-[3px] border-transparent border-t-[var(--color-purple)] animate-spin-slow [animation-direction:reverse] [animation-duration:2s]" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-3 w-3 rounded-full bg-gradient-to-br from-[var(--color-blue)] to-[var(--color-purple)] animate-pulse-soft" />
          </div>
        </div>

        {/* Steps checklist */}
        <AnalysisProgress completedSteps={completedSteps} currentStep={currentStep} steps={steps} />
      </div>
    </div>
  );
}

export function AnalysisProgress({ completedSteps, currentStep, steps }) {
  return (
    <div className="flex w-full flex-col gap-2" id="analysis-progress">
      {steps.map((step) => {
        const isDone = completedSteps.includes(step.id);
        const isActive = step.id === currentStep && !isDone;

        return (
          <div
            key={step.id}
            className={`flex items-center gap-3 rounded-lg px-4 py-2.5 transition-all duration-300
              ${isDone ? 'opacity-50' : ''}
              ${isActive ? 'border border-[var(--color-border)] bg-[var(--color-bg-card)] animate-fade-in' : ''}
              ${!isDone && !isActive ? 'opacity-20' : ''}
            `}
          >
            {/* Icon */}
            <div className="flex h-5 w-5 shrink-0 items-center justify-center">
              {isDone ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-[var(--color-green)]">
                  <path d="M20 6L9 17L4 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : isActive ? (
                <div className="h-2.5 w-2.5 rounded-full bg-[var(--color-blue)] animate-pulse-soft" />
              ) : (
                <div className="h-2 w-2 rounded-full bg-[var(--color-text-muted)]" />
              )}
            </div>

            <span className={`text-sm font-medium ${isDone ? 'text-[var(--color-text-secondary)]' : isActive ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-muted)]'}`}>
              {step.text}
            </span>
          </div>
        );
      })}
    </div>
  );
}
