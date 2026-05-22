# Pautas de calidad — Fiscalito Store

## Principios fundamentales

1. **El LLM no calcula.** Toda la lógica fiscal (ISR, IVA, deducciones) vive en el Fiscal Agent API. El frontend solo presenta resultados.
2. **Theming light/dark.** La app soporta ambos modos. Siempre se usan variables CSS de `src/styles/global.css`. Nunca colores hex o rgba hardcodeados en componentes.
3. **Sin librerías de UI.** No se usa Tailwind, Material UI, Bootstrap ni ningún framework de componentes. Todo con CSS variables.

---

## TypeScript

### Sin `any` injustificado

```typescript
// ✅ Correcto
const res = await calcularPreDeclaracion(data);

// ❌ Incorrecto
const res: any = await calcularPreDeclaracion(data);
```

Si un tipo externo no está disponible, se define una interfaz en `fiscalAgentApi.ts`, no se recurre a `any`.

### Interfaces alineadas con el backend

Cada endpoint del Fiscal Agent API tiene su interfaz correspondiente en `src/services/fiscalAgentApi.ts`. Cuando el schema del backend cambia, **la interfaz del frontend se actualiza en el mismo commit**.

---

## Componentes React

### Tamaño máximo: 300 líneas

Si un componente supera las 300 líneas, se extrae lógica a un hook personalizado o se divide en subcomponentes.

```
PreDeclaracionTab.tsx        → lógica de upload + cálculo
├── FacturaTable.tsx          → tabla de facturas
├── ResultadoDeclaracion.tsx  → visualización de resultado
└── useDeclaracion.ts         → hook con estado y handlers (si aplica)
```

### Todo async tiene loading + error

```typescript
// ✅ Correcto
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');

const handleCalcular = async () => {
  setLoading(true);
  setError('');
  try {
    const res = await calcularPreDeclaracion(data);
    setResultado(res);
  } catch (e) {
    setError(e instanceof Error ? e.message : 'Error inesperado');
  } finally {
    setLoading(false);
  }
};
```

### Sin `console.log` en producción

Para depuración temporal está bien; se elimina antes del commit a `stable`.

---

## Estilos CSS

### Solo variables de `global.css`

```typescript
// ✅ Correcto
color: 'var(--teal-light)'
background: 'var(--bg-card)'
border: '1px solid var(--border)'

// ❌ Incorrecto
color: '#6e9fa0'
background: '#130e17'
```

### Paleta aprobada

| Variable | Uso |
|----------|-----|
| `--bg-dark` | Fondo principal de la app |
| `--bg-surface` | Sidebar, inputs de fondo |
| `--bg-card` | Cards y contenedores |
| `--teal-light` | Acento principal, highlights, stats |
| `--purple-light` | Acento secundario, hover states |
| `--text-primary` | Texto principal (`#e8e4ec`) |
| `--text-secondary` | Labels, subtítulos |
| `--text-muted` | Placeholders, hints, disabled |
| `--success` | Saldo a favor, confirmaciones |
| `--warning` | Alertas no críticas |
| `--danger` | Errores, montos negativos |

### Tipografía

- UI general: `Outfit` (cargada via Google Fonts)
- Datos numéricos / montos / código: `JetBrains Mono`

```typescript
// ✅ Datos monetarios
fontFamily: "'JetBrains Mono', monospace"

// ✅ UI general (default del body)
// No hace falta especificarlo, se hereda
```

---

## Firebase y Firestore

- Las claves de Firebase van **solo en `.env`**, nunca en código fuente.
- `.env` está en `.gitignore`. Usar `.env.example` como referencia.
- Las operaciones de Firestore se encapsulan en `src/services/declaracionesHistory.ts`. Los componentes nunca importan `firebase/firestore` directamente.

```typescript
// ✅ Correcto — usar el servicio
import { guardarDeclaracion } from '../../services/declaracionesHistory';

// ❌ Incorrecto — acceso directo a Firestore desde componente
import { setDoc } from 'firebase/firestore';
```

---

## Navegación y rutas

Todas las rutas protegidas pasan por `ProtectedRoute`. Las rutas nuevas se registran en `src/main.tsx`.

```typescript
// Ruta pública
<Route path="/login" element={<LoginPage />} />

// Ruta protegida (requiere auth + onboarding)
<Route element={<ProtectedRoute />}>
  <Route element={<AppLayout />}>
    <Route path="/app/nueva-pagina" element={<NuevaPagina />} />
  </Route>
</Route>
```

---

## Integración con Fiscal Agent API

El cliente está centralizado en `src/services/fiscalAgentApi.ts`. No se hace `fetch` directo en componentes.

```typescript
// ✅ Correcto
import { calcularPreDeclaracion } from '../../services/fiscalAgentApi';

// ❌ Incorrecto
const res = await fetch(`${import.meta.env.VITE_FISCAL_AGENT_URL}/api/v1/pre-declaracion`, ...);
```

Si el servidor no está disponible, el error debe mostrarse al usuario mediante `ErrorAlert`, nunca ignorarse silenciosamente.

---

## Theming

La app usa `data-theme="dark"` (default) o `data-theme="light"` en el elemento `<html>`.

### Cómo funciona

- `ThemeContext` (`src/context/ThemeContext.tsx`) gestiona el tema activo, lo persiste en `localStorage` y lo aplica vía `document.documentElement.setAttribute('data-theme', theme)`.
- Las variables de color para cada tema viven en `src/styles/global.css`: bloque `:root, [data-theme="dark"]` para dark y bloque `[data-theme="light"]` para light.
- Un script anti-FOUC en `index.html` aplica el tema **antes** de que React monte.
- El toggle es `ThemeToggle.tsx`, integrado en el sidebar (full y mini).

### Reglas al agregar variables nuevas

Toda variable de color nueva se define **en pareja**:
```css
:root, [data-theme="dark"] { --nueva-var: rgba(110, 159, 160, 0.12); }
[data-theme="light"]       { --nueva-var: rgba(53, 86, 84, 0.08); }
```

Los valores hex de `--purple`, `--purple-light`, `--teal`, `--teal-light` y el `--accent-gradient` son **idénticos** en ambos temas — son la firma visual de la marca.

---

## Checklist de revisión de código

Antes de aprobar un PR:

- [ ] `npm run build` sin errores TypeScript
- [ ] Sin colores hardcodeados (hex/rgba) fuera de `global.css` — solo variables CSS
- [ ] Componentes nuevos probados visualmente en ambos temas (light y dark)
- [ ] Sin `console.log` ni `any` injustificados
- [ ] Llamadas async con loading + error handler
- [ ] Componentes nuevos bajo 300 líneas
- [ ] Firestore accedido solo a través de `declaracionesHistory.ts`
- [ ] Tipos nuevos definidos en `fiscalAgentApi.ts` si vienen del backend
