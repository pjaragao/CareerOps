
import React, { useEffect, useState } from 'react';
import { companyService, Company } from '../services/companyService';
import { Search, ExternalLink, Building2, Briefcase, Globe, Info, Filter, ChevronRight, X } from 'lucide-react';

const Companies = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [companyJobs, setCompanyJobs] = useState<any[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, [typeFilter]);

  const loadCompanies = async () => {
    setLoading(true);
    try {
      const data = await companyService.getCompanies(typeFilter === 'all' ? undefined : typeFilter);
      setCompanies(data);
    } catch (error) {
      console.error("Failed to load companies", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCompany = async (company: Company) => {
    setSelectedCompany(company);
    setLoadingJobs(true);
    try {
      const jobs = await companyService.getCompanyJobs(company.id);
      setCompanyJobs(jobs);
    } catch (error) {
      console.error("Failed to load company jobs", error);
    } finally {
      setLoadingJobs(false);
    }
  };

  const filteredCompanies = companies.filter(c => 
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.industry && c.industry.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const getTypeBadgeStyle = (type: string) => {
    switch (type) {
      case 'DIRECT_EMPLOYER': return { bg: 'rgba(34, 197, 94, 0.1)', text: '#4ade80' };
      case 'RECRUITMENT_AGENCY': return { bg: 'rgba(234, 179, 8, 0.1)', text: '#facc15' };
      case 'JOB_PLATFORM': return { bg: 'rgba(59, 130, 246, 0.1)', text: '#60a5fa' };
      default: return { bg: 'rgba(255, 255, 255, 0.05)', text: 'var(--text-muted)' };
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 700, marginBottom: '0.2rem' }}>Empresas & Portais</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Gerencie sua rede de contratação e monitoramento.</p>
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input 
            placeholder="Buscar..." 
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ paddingLeft: '36px', width: '100%', height: '38px', fontSize: '0.9rem' }}
          />
        </div>
        
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          {['all', 'DIRECT_EMPLOYER', 'RECRUITMENT_AGENCY', 'JOB_PLATFORM'].map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`btn ${typeFilter === t ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '0.75rem', padding: '0 12px', height: '38px' }}
            >
              {t === 'all' ? 'Todos' : t.split('_').map(w => w[0] + w.slice(1).toLowerCase()).join(' ')}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', flex: 1, overflow: 'hidden' }}>
        <div className="panel" style={{ flex: selectedCompany ? '0 0 60%' : '1', overflowY: 'auto', padding: 0 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead style={{ position: 'sticky', top: 0, background: 'var(--panel-bg)', zIndex: 1, borderBottom: '1px solid var(--border)' }}>
              <tr>
                <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>Empresa</th>
                <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>Tipo</th>
                <th style={{ textAlign: 'center', padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>Vagas</th>
                <th style={{ textAlign: 'right', padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>Carregando...</td></tr>
              ) : filteredCompanies.map(company => (
                <tr 
                  key={company.id} 
                  onClick={() => handleSelectCompany(company)}
                  style={{ 
                    borderBottom: '1px solid var(--border)', 
                    cursor: 'pointer',
                    background: selectedCompany?.id === company.id ? 'rgba(255,255,255,0.05)' : 'transparent'
                  }}
                  className="row-hover"
                >
                  <td style={{ padding: '8px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '28px', height: '28px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {company.logo_url ? <img src={company.logo_url} style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> : <Building2 size={14} />}
                      </div>
                      <span style={{ fontWeight: 500 }}>{company.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <span style={{ 
                      fontSize: '0.7rem', 
                      padding: '2px 8px', 
                      borderRadius: '4px', 
                      background: getTypeBadgeStyle(company.company_type).bg,
                      color: getTypeBadgeStyle(company.company_type).text,
                      fontWeight: 600
                    }}>
                      {company.company_type.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '8px 16px', textAlign: 'center' }}>
                    <span style={{ 
                      fontWeight: 700, 
                      color: company.job_count > 0 ? 'var(--accent)' : 'var(--text-muted)',
                      background: company.job_count > 0 ? 'rgba(108, 99, 255, 0.1)' : 'transparent',
                      padding: '2px 8px',
                      borderRadius: '10px'
                    }}>
                      {company.job_count}
                    </span>
                  </td>
                  <td style={{ padding: '8px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      {company.career_site_url && (
                        <a href={company.career_site_url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} className="btn btn-secondary" style={{ padding: '4px' }}>
                          <ExternalLink size={14} />
                        </a>
                      )}
                      <ChevronRight size={16} color="var(--text-muted)" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedCompany && (
          <div className="panel animate-slide-in" style={{ flex: '1', display: 'flex', flexDirection: 'column', border: '1px solid var(--accent-low)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0 }}>{selectedCompany.name}</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{selectedCompany.domain || selectedCompany.industry}</p>
              </div>
              <button onClick={() => setSelectedCompany(null)} className="btn btn-secondary" style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              <h3 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '0.8rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.4rem' }}>
                Vagas Vinculadas ({companyJobs.length})
              </h3>
              
              {loadingJobs ? (
                <div style={{ textAlign: 'center', padding: '2rem' }}>Carregando vagas...</div>
              ) : companyJobs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  Nenhuma vaga vinculada ainda.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {companyJobs.map(job => (
                    <div key={job.id} className="card-hover" style={{ padding: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>{job.job_title}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{job.location}</span>
                        <a href={job.url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ padding: '4px', fontSize: '0.7rem' }}>
                          Ver Vaga <ExternalLink size={12} style={{ marginLeft: '4px' }} />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
              <a href={selectedCompany.career_site_url} target="_blank" rel="noreferrer" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                Ir para Site de Carreira <ExternalLink size={16} style={{ marginLeft: '8px' }} />
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Companies;
