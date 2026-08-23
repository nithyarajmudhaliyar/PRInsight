import Navbar from './components/Navbar';
import Footer from './components/Footer';
import LoadingScreen from './components/LoadingScreen';
import ErrorScreen from './components/ErrorScreen';
import Home from './pages/Home';
import Results from './pages/Results';
import { useAnalyze } from './hooks/useAnalyze';
import { useAuth } from './hooks/useAuth';

export default function App() {
  const { status, result, error, completedSteps, currentStep, analyze, reset, loadingSteps } = useAnalyze();
  const { user, loading: authLoading, login, logout } = useAuth();

  const handleAnalyze = (parsed) => {
    analyze(parsed);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleReset = () => {
    reset();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <>
      <Navbar user={user} onLogin={login} onLogout={logout} />
      <main className="flex-1">
        {status === 'loading' && (
          <LoadingScreen completedSteps={completedSteps} currentStep={currentStep} steps={loadingSteps} />
        )}
        {status === 'success' && (
          <Results data={result} onReset={handleReset} />
        )}
        {status === 'error' && (
          <ErrorScreen message={error} onRetry={handleReset} />
        )}
        {status === 'idle' && (
          <Home onAnalyze={handleAnalyze} isLoading={status === 'loading'} />
        )}
      </main>
      <Footer />
    </>
  );
}
