import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api, { setAccessToken } from '../services/api';

// A one-time link (made on the server) gives this browser the access token, so the phone needs no typing
const Enter = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;   // the code works once: never send it twice
    started.current = true;
    const code = params.get('codigo') || '';
    window.history.replaceState(null, '', '/entrar');   // the code does not stay in the address bar or history
    api.post<{ token: string }>('/automation/login-links/redeem', { code })
      .then((r) => { setAccessToken(r.data.token); navigate('/automacao?tab=aprovar', { replace: true }); })
      .catch((e) => setError(e?.response?.data?.detail || 'Não deu certo: peça outro link.'));
  }, [params, navigate]);
  return (
    <div className="panel" style={{ maxWidth: 480 }}>
      <h1 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 8 }}>Entrar</h1>
      <p style={{ color: error ? '#ff7675' : 'var(--text-muted)' }}>{error || 'Guardando o acesso neste navegador…'}</p>
    </div>
  );
};

export default Enter;
