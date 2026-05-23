import { Moon, Sun, Coffee } from 'lucide-react';
import { useTheme, Theme } from '../context/ThemeContext';

interface ThemeToggleProps {
  mini?: boolean;
}

const OPTIONS: Array<{ value: Theme; icon: React.ReactNode; label: string }> = [
  { value: 'dark',    icon: <Moon size={14} />,   label: 'Oscuro'  },
  { value: 'light',   icon: <Sun size={14} />,    label: 'Claro'   },
  { value: 'vanilla', icon: <Coffee size={14} />, label: 'Vanilla' },
];

const iconMap: Record<Theme, React.ReactNode> = {
  dark:    <Moon size={18} />,
  light:   <Sun size={18} />,
  vanilla: <Coffee size={18} />,
};

export default function ThemeToggle({ mini = false }: ThemeToggleProps) {
  const { theme, setTheme, cycleTheme } = useTheme();

  if (mini) {
    return (
      <button
        onClick={cycleTheme}
        title={`Tema: ${theme}`}
        aria-label="Cambiar tema"
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
        {iconMap[theme]}
      </button>
    );
  }

  return (
    <div style={{
      display: 'flex',
      padding: 3,
      background: 'var(--bg-input)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      gap: 2,
    }}>
      {OPTIONS.map(opt => {
        const isActive = theme === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => setTheme(opt.value)}
            title={opt.label}
            aria-label={`Tema ${opt.label}`}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '6px 8px',
              background: isActive ? 'var(--bg-card)' : 'transparent',
              border: 'none',
              borderRadius: 'var(--radius-xs)',
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontSize: '0.72rem',
              fontWeight: isActive ? 600 : 400,
              cursor: 'pointer',
              transition: 'all 0.15s',
              boxShadow: isActive ? 'var(--shadow-sm)' : 'none',
            }}
          >
            {opt.icon}
          </button>
        );
      })}
    </div>
  );
}
