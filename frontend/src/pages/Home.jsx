import Hero from '../components/Hero';
import SearchBar from '../components/SearchBar';
import FeatureCards from '../components/FeatureCards';

export default function Home({ onAnalyze, isLoading }) {
  return (
    <>
      <Hero />
      <SearchBar onAnalyze={onAnalyze} disabled={isLoading} />
      <FeatureCards />
    </>
  );
}
