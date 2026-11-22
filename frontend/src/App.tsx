import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { Matches } from './pages/Matches';
import { MatchPage } from './pages/MatchPage';
import { Nation, Nations } from './pages/Nations';
import { Method } from './pages/Method';
import { NotFound } from './pages/NotFound';

// The labs carry their own data (the xG grid alone is ~76 KB), so they load only when visited
const XgLab = lazy(() => import('./pages/XgLab').then((m) => ({ default: m.XgLab })));
const PenaltyLab = lazy(() => import('./pages/PenaltyLab').then((m) => ({ default: m.PenaltyLab })));

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
          <Route
            path="/lab/xg"
            element={
              <Suspense fallback={<p className="px-4 py-24 text-center text-muted">Loading the xG lab…</p>}>
                <XgLab />
              </Suspense>
            }
          />
          <Route
            path="/lab/penalties"
            element={
              <Suspense fallback={<p className="px-4 py-24 text-center text-muted">Loading penalties…</p>}>
                <PenaltyLab />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
