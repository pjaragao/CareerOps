import React, { useEffect, useState } from 'react';
import { Download, Copy, Check, Puzzle, RefreshCw, AlertTriangle, Store } from 'lucide-react';

const muted: React.CSSProperties = { color: 'var(--text-muted)', fontSize: '0.9rem' };
const code: React.CSSProperties = {
  background: 'rgba(255,255,255,0.08)', padding: '2px 8px', borderRadius: 6, fontFamily: 'monospace', fontSize: '0.9rem',
};

const CopyButton = ({ text }: { text: string }) => {
  const [ok, setOk] = useState(false);
  return (
    <button className="btn btn-secondary" style={{ padding: '4px 10px' }}
      onClick={async () => { try { await navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* select manually */ } }}>
      {ok ? <Check size={14} /> : <Copy size={14} />} {ok ? 'Copiado' : 'Copiar'}
    </button>
  );
};

const Step = ({ n, title, children }: { n: number; title: string; children: React.ReactNode }) => (
  <div className="panel" style={{ display: 'flex', gap: '1.2rem', alignItems: 'flex-start' }}>
    <div style={{
      minWidth: 36, height: 36, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex',
      alignItems: 'center', justifyContent: 'center', fontWeight: 700,
    }}>{n}</div>
    <div style={{ flex: 1 }}>
      <h3 style={{ marginBottom: '0.5rem' }}>{title}</h3>
      <div style={{ ...muted, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>{children}</div>
    </div>
  </div>
);

const InstallExtension = () => {
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    fetch('/careerops-extension.json').then(r => (r.ok ? r.json() : null)).then(d => setVersion(d?.version ?? null)).catch(() => setVersion(null));
  }, []);

  return (
    <div className="animate-fade-in" style={{ maxWidth: 860 }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Puzzle /> Instalar a extensão
        </h1>
        <p style={muted}>
          A extensão coloca o painel <strong>CareerOps · Perfil</strong> no LinkedIn (textos do seu perfil em inglês e português),
          importa vagas e envia posts e perfis ao LinkedIn Copilot. Leva uns 2 minutos, uma vez só, no Chrome ou no Edge.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <Step n={1} title="Baixe o pacote">
          <div>
            <a className="btn btn-primary" href="/careerops-extension.zip" download style={{ display: 'inline-flex' }}>
              <Download size={16} /> Baixar extensão {version ? `v${version}` : ''}
            </a>
          </div>
          {version === null && (
            <span style={{ color: 'var(--error)' }}>
              Pacote ainda não gerado no servidor: rode <code style={code}>python3 extension/package.py</code> na pasta do projeto.
            </span>
          )}
        </Step>

        <Step n={2} title="Extraia numa pasta fixa">
          <span>Clique com o botão direito no arquivo baixado → <strong>Extrair tudo…</strong> e escolha uma pasta que você não vá apagar, por exemplo:</span>
          <span><code style={code}>Documentos\CareerOps</code></span>
          <span>Vai aparecer a pasta <code style={code}>careerops-extension</code>. O Chrome lê a extensão dali — se a pasta for apagada, a extensão some.</span>
        </Step>

        <Step n={3} title="Abra a página de extensões">
          <span>Copie o endereço, cole na barra do navegador e tecle Enter (por segurança o navegador não deixa abrir por link):</span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <code style={code}>chrome://extensions</code> <CopyButton text="chrome://extensions" />
            <span>no Edge:</span> <code style={code}>edge://extensions</code> <CopyButton text="edge://extensions" />
          </div>
        </Step>

        <Step n={4} title="Ative o Modo do desenvolvedor">
          <span>Chrome: chave <strong>Modo do desenvolvedor</strong> no canto superior direito. Edge: no menu da esquerda.</span>
        </Step>

        <Step n={5} title="Carregue a pasta">
          <span>Clique em <strong>Carregar sem compactação</strong> e selecione a pasta <code style={code}>careerops-extension</code> (a pasta, não o .zip).</span>
          <span>Depois, no ícone de quebra-cabeça da barra, fixe a <strong>CareerOps LinkedIn Importer</strong>.</span>
        </Step>

        <Step n={6} title="Confira no LinkedIn">
          <span>Abra <code style={code}>linkedin.com</code>: o botão <strong>CareerOps · Perfil</strong> aparece no canto inferior esquerdo.
            Se o painel disser que o backend está indisponível, o computador precisa estar no Tailscale (o backend fica em
            <code style={code}>100.109.242.35:8005</code>).</span>
        </Step>
      </div>

      <div className="panel" style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
        <RefreshCw size={20} style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={muted}>
          <strong style={{ color: '#fff' }}>Atualizar depois:</strong> baixe o pacote de novo, extraia por cima da mesma pasta
          e clique no ícone ↻ (recarregar) da extensão em <code style={code}>chrome://extensions</code>.
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
        <Store size={20} style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={muted}>
          <strong style={{ color: '#fff' }}>Instalação em um clique:</strong> só é possível publicando a extensão na Chrome Web Store
          (pode ser como <em>não listada</em>, visível só para quem tem o link). Exige uma conta de desenvolvedor do Google
          (taxa única de US$ 5) e uma revisão de alguns dias. Depois disso, instalar e atualizar passam a ser automáticos.
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
        <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: 2, color: '#ffb020' }} />
        <div style={muted}>
          A extensão não curte, comenta, segue nem conecta por você: ela só lê a página que você mandar e preenche o campo que você
          clicar. Quem salva no LinkedIn é sempre você.
        </div>
      </div>
    </div>
  );
};

export default InstallExtension;
