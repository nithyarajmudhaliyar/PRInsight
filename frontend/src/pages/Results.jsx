import ResultSummary from '../components/ResultSummary';
import ConflictList from '../components/ConflictList';
import EmptyState from '../components/EmptyState';

export default function Results({ data, onReset }) {
  if (!data) return null;

  return (
    <>
      <ResultSummary data={data} />
      {data.conflicts.length > 0 ? (
        <ConflictList conflicts={data.conflicts} />
      ) : (
        <EmptyState onAnalyzeAnother={onReset} />
      )}
    </>
  );
}
