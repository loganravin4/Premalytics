import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { Matches } from './pages/Matches';
import { MatchPage } from './pages/MatchPage';
import { Nation, Nations } from './pages/Nations';
import { Method } from './pages/Method';
import { NotFound } from './pages/NotFound';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/wc2026" element={<Matches />} />
          <Route path="/wc2026/:slug" element={<MatchPage />} />
          <Route path="/nations" element={<Nations />} />
          <Route path="/nations/:code" element={<Nation />} />
          <Route path="/method" element={<Method />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
