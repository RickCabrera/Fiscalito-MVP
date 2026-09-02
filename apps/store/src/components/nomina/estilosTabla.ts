/**
 * Estilos de las tablas de nómina (E-04). DEMO: se borran en F2 con la épica.
 *
 * Se componen de `utils/styles.ts`, que es lo que ya usan los tabs de
 * Fiscalito, en vez de inventar otra escala. Viven aquí y no allá para no
 * cambiar de paso las tablas del contribuyente, que están fuera del alcance de
 * la épica.
 *
 * NINGÚN COLOR NI ESPACIADO NUEVO: todo sale de los tokens de `global.css`, que
 * es la condición para que los tres temas (dark, light, vanilla) sigan
 * funcionando sin inspeccionarlos uno por uno.
 */

import { thStyle, tdStyle } from '../../utils/styles';

/** Encabezado de columna. */
export const th: React.CSSProperties = thStyle;

/** Encabezado de una columna numérica: alineado a la derecha, como sus celdas. */
export const thNum: React.CSSProperties = { ...thStyle, textAlign: 'right' };

/** Celda de texto. */
export const td: React.CSSProperties = {
  ...tdStyle,
  color: 'var(--text-primary)',
};

/**
 * Celda numérica.
 *
 * `tabular-nums` es lo que hace que una columna de importes se lea de un
 * vistazo: sin él los dígitos tienen anchos distintos y las cifras no alinean.
 * **Sin `text-overflow` ni ancho fijo**: un importe recortado a `$93,27…` es un
 * número equivocado enfrente de un contador. Si no cabe, la tabla scrollea.
 */
export const tdNum: React.CSSProperties = {
  ...tdStyle,
  color: 'var(--text-primary)',
  textAlign: 'right',
  fontFamily: "'JetBrains Mono', monospace",
  fontVariantNumeric: 'tabular-nums',
};

/** Celda numérica de un total: mismo formato, más peso. */
export const tdNumFuerte: React.CSSProperties = { ...tdNum, fontWeight: 700 };

/**
 * Envoltura de la tabla.
 *
 * `overflowX: auto` **solo no basta**: con la tabla en `width: 100%` las
 * columnas se comprimen en vez de desbordar y el scroll nunca aparece. El par
 * es este contenedor más un `minWidth` en la tabla.
 */
export const envoltura: React.CSSProperties = {
  overflowX: 'auto',
  margin: '0 calc(var(--space-lg) * -1)',
  padding: '0 var(--space-lg)',
};

/** La tabla. `minWidth` es el otro medio del par de arriba. */
export function tabla(minWidth: number): React.CSSProperties {
  return {
    width: '100%',
    minWidth,
    borderCollapse: 'collapse',
    fontSize: '0.88rem',
  };
}

/** Fila con cebra sutil, para seguir el renglón en una tabla ancha. */
export function fila(indice: number): React.CSSProperties {
  return {
    background: indice % 2 === 1 ? 'var(--bg-card-hover)' : 'transparent',
    borderTop: '1px solid var(--border)',
  };
}

/** Encabezado de sección dentro de una card. */
export const tituloSeccion: React.CSSProperties = {
  fontSize: '0.95rem',
  fontWeight: 600,
  letterSpacing: -0.2,
  margin: 0,
};
