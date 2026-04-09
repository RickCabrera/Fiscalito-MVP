/** Shared inline style objects used across tab components */

export const thStyle: React.CSSProperties = {
  padding: '10px 14px',
  textAlign: 'left',
  color: 'var(--text-muted)',
  fontWeight: 500,
  fontSize: '0.75rem',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
};

export const tdStyle: React.CSSProperties = {
  padding: '10px 14px',
  color: 'var(--text-secondary)',
};

export const tdMonoStyle: React.CSSProperties = {
  ...tdStyle,
  fontFamily: "'JetBrains Mono', monospace",
  textAlign: 'right',
};

export const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.8rem',
  color: 'var(--text-muted)',
  marginBottom: 6,
};
