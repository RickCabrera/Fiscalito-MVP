/**
 * ThemeToggle — botón para alternar entre light y dark mode.
 * Versión "full" para el sidebar desktop y versión "mini" para mobile.
 */
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

interface ThemeToggleProps {
  mini?: boolean;
}

export default function ThemeToggle({ mini = false }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  if (mini) {
    return (
      <button
        onClick={toggleTheme}
        title={isDark ? 'Activar modo claro' : 'Activar modo oscuro'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 44,
          height: 44,
          background: 'transparent',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          borderRadius: 'var(--radius-sm)',
          transition: 'all 0.2s',
        }}
        onMouseOver={(e) => { e.currentTarget.style.color = 'var(--teal-light)'; }}
        onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
      >
        {isDark ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    );
  }

  return (
    <button
      onClick={toggleTheme}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        padding: '9px 12px',
        background: 'transparent',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text-primary)',
        fontSize: '0.85rem',
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'all 0.2s',
        width: '100%',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.borderColor = 'var(--teal-light)';
        e.currentTarget.style.color = 'var(--teal-light)';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.color = 'var(--text-primary)';
      }}
    >
      {isDark ? <Sun size={15} /> : <Moon size={15} />}
      {isDark ? 'Modo claro' : 'Modo oscuro'}
    </button>
  );
}
