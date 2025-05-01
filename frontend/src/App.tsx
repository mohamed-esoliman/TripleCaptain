import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './pages/Dashboard';
import SquadBuilder from './pages/SquadBuilder';
import TeamPage from './pages/TeamPage';
import TransferPlanner from './pages/TransferPlanner';
import Optimize from './pages/Optimize';
import PlayersPage from './pages/PlayersPage';
import AnalyticsPage from './pages/AnalyticsPage';
import LoadingSpinner from './components/common/LoadingSpinner';
import SettingsPage from './pages/SettingsPage';
import AdminPage from './pages/AdminPage';

const App: React.FC = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    );
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/team" element={<TeamPage />} />
        <Route path="/wildcard" element={<SquadBuilder />} />
        <Route path="/transfer-planner" element={<TransferPlanner />} />
        <Route path="/optimize" element={<Optimize />} />
        <Route path="/players" element={<PlayersPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
};

export default App;