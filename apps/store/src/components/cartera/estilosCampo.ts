/**
 * Estilos de los campos de formulario de la cartera.
 *
 * Viven separados de `Campo.tsx` para que ese archivo exporte **sólo** el
 * componente: un módulo que mezcla componentes con otras exportaciones rompe el
 * fast refresh de Vite. Es la misma razón por la que `clienteActivoStore` está
 * aparte de su proveedor.
 */

export const campoInput: React.CSSProperties = {
  width: '100%',
  padding: 'var(--space-sm)',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
};

export const etiquetaCampo: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  color: 'var(--text-secondary)',
  marginBottom: 4,
  textTransform: 'uppercase',
  letterSpacing: 0.4,
};
