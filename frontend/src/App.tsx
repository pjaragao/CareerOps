import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { FileText, Files, BookOpen, Globe, Briefcase, MessageSquare, Key, Puzzle, PenLine, Search } from 'lucide-react';
import MainLayout from './layouts/MainLayout';
import TabbedPage from './components/TabbedPage';
import Home from './pages/Home';
import Profile from './pages/Profile';
import DocumentRepository from './pages/DocumentRepository';
import LinkedInTexts from './pages/LinkedInTexts';
import GeneralResumes from './pages/GeneralResumes';
import JobBoard from './pages/JobBoard';
import JobSearch from './pages/JobSearch';
import Interview from './pages/Interview';
import LinkedInCopilot from './pages/LinkedInCopilot';
import Settings from './pages/Settings';
import InstallExtension from './pages/InstallExtension';
import AISettings from './pages/AISettings';

// Five screens: Início · Meu Perfil · Vagas · LinkedIn Copilot · Configurações
const MyProfile = () => (
  <TabbedPage tabs={[
    { id: 'cv', label: 'Dados e CVs', icon: <FileText size={16} />, render: () => <Profile /> },
    { id: 'cvs-gerais', label: 'CVs gerais', icon: <Files size={16} />, render: () => <GeneralResumes /> },
    { id: 'conhecimento', label: 'Base de conhecimento', icon: <BookOpen size={16} />, render: () => <DocumentRepository /> },
    { id: 'linkedin', label: 'Textos do LinkedIn', icon: <Globe size={16} />, render: () => <LinkedInTexts /> },
  ]} />
);

const Jobs = () => (
  <TabbedPage tabs={[
    { id: 'vagas', label: 'Vagas e candidaturas', icon: <Briefcase size={16} />, render: () => <JobBoard /> },
    { id: 'pesquisar', label: 'Pesquisar vagas', icon: <Search size={16} />, render: () => <JobSearch /> },
    { id: 'entrevistas', label: 'Preparação de entrevistas', icon: <MessageSquare size={16} />, render: () => <Interview /> },
  ]} />
);

const SettingsHub = () => (
  <TabbedPage tabs={[
    { id: 'estilo', label: 'Estilo e modelos', icon: <PenLine size={16} />, render: () => <AISettings /> },
    { id: 'ia', label: 'Chaves de IA', icon: <Key size={16} />, render: () => <Settings /> },
    { id: 'extensao', label: 'Instalar extensão', icon: <Puzzle size={16} />, render: () => <InstallExtension /> },
  ]} />
);

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route path="" element={<Home />} />
          <Route path="perfil" element={<MyProfile />} />
          <Route path="vagas" element={<Jobs />} />
          <Route path="linkedin-copilot" element={<LinkedInCopilot />} />
          <Route path="configuracoes" element={<SettingsHub />} />
          {/* old addresses */}
          <Route path="profile" element={<Navigate to="/perfil" replace />} />
          <Route path="onboarding" element={<Navigate to="/perfil?tab=conhecimento" replace />} />
          <Route path="linkedin-optimizer" element={<Navigate to="/perfil?tab=linkedin" replace />} />
          <Route path="jobs" element={<Navigate to="/vagas" replace />} />
          <Route path="pipeline" element={<Navigate to="/vagas" replace />} />
          <Route path="interview" element={<Navigate to="/vagas?tab=entrevistas" replace />} />
          <Route path="settings" element={<Navigate to="/configuracoes" replace />} />
          <Route path="extensao" element={<Navigate to="/configuracoes?tab=extensao" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
