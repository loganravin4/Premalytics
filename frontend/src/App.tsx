/**
 * Root route table. All main pages share `Layout` (sidebar, background, animated outlet).
 * Unknown paths redirect to `/` — tighten later with a dedicated 404 page if needed.
 */
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Teams } from './pages/Teams';
import { TeamDetail } from './pages/TeamDetail';
import { Players } from './pages/Players';
import { PlayerDetail } from './pages/PlayerDetail';
import { Predictions } from './pages/Predictions';
import { Standings } from './pages/Standings';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/teams/:id" element={<TeamDetail />} />
          <Route path="/players" element={<Players />} />
          <Route path="/players/:id" element={<PlayerDetail />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/standings" element={<Standings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
