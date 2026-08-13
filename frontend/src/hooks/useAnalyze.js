import { useState, useCallback, useRef, useEffect } from 'react';
import { analyzePR } from '../services/api';

/**
 * Loading steps displayed during analysis.
 * Previously imported from mockData — now defined here since these
 * are purely UI-layer concerns, not mock data.
 */
const loadingSteps = [
  { id: 'parse', text: 'Parsing Pull Request URL' },
  { id: 'fetch-pr', text: 'Fetching Pull Request' },
  { id: 'fetch-open', text: 'Loading Active Pull Requests' },
  { id: 'compare', text: 'Comparing Changed Files' },
  { id: 'detect', text: 'Detecting Conflicts' },
];

/**
 * Custom hook encapsulating the full analyze flow:
 * parsing → loading steps → results.
 *
 * The loading animation runs in parallel with the real API call.
 * Steps animate at timed intervals. If the API responds before all
 * steps complete, the remaining steps are fast-forwarded. If the API
 * takes longer than the animation, the last step stays active
 * (its spinner keeps spinning) until the response arrives.
 */
export function useAnalyze() {
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const cancelRef = useRef(false);

  // Animate through loading steps at timed intervals
  const runSteps = useCallback(async () => {
    const stepDelay = [400, 700, 800, 900, 600]; // ms per step
    for (let i = 0; i < loadingSteps.length; i++) {
      if (cancelRef.current) return;
      setCurrentStep(loadingSteps[i].id);
      await new Promise((r) => setTimeout(r, stepDelay[i] || 600));
      if (cancelRef.current) return;
      setCompletedSteps((prev) => [...prev, loadingSteps[i].id]);
    }
  }, []);

  const analyze = useCallback(async (parsed) => {
    cancelRef.current = false;
    setStatus('loading');
    setResult(null);
    setError(null);
    setCompletedSteps([]);
    setCurrentStep(loadingSteps[0].id);

    try {
      // Run loading steps UI and API call in parallel.
      // The loading animation plays while the real backend request
      // is in flight. No artificial setTimeout for the API — the
      // loading screen stays visible naturally until the response arrives.
      const [apiResult] = await Promise.all([
        analyzePR(parsed),
        runSteps(),
      ]);

      if (cancelRef.current) return;

      // Fast-forward: mark all steps as completed when API responds
      setCompletedSteps(loadingSteps.map((s) => s.id));

      setResult(apiResult);
      setStatus('success');
    } catch (err) {
      if (cancelRef.current) return;
      setError(err.message || 'Analysis failed. Please try again.');
      setStatus('error');
    }
  }, [runSteps]);

  const reset = useCallback(() => {
    cancelRef.current = true;
    setStatus('idle');
    setResult(null);
    setError(null);
    setCompletedSteps([]);
    setCurrentStep(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => { cancelRef.current = true; };
  }, []);

  return {
    status,
    result,
    error,
    completedSteps,
    currentStep,
    analyze,
    reset,
    loadingSteps,
  };
}
