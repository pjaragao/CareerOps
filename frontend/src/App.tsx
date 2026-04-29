import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import JobBoard from './pages/JobBoard';
import Profile from './pages/Profile';
import Interview from './pages/Interview';
import Strategies from './pages/Strategies';
import Pipeline from './pages/Pipeline';
import Kanban from './pages/Kanban';
import Settings from './pages/Settings';
import LinkedInOptimizer from './pages/LinkedInOptimizer';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route path="" element={<Dashboard />} />
          <Route path="profile" element={<Profile />} />
          <Route path="strategies" element={<Strategies />} />
          <Route path="jobs" element={<JobBoard />} />
          <Route path="kanban" element={<Kanban />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="interview" element={<Interview />} />
          <Route path="linkedin-optimizer" element={<LinkedInOptimizer />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
