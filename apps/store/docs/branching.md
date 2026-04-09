# Estrategia de ramas — Fiscalito Store

## Ramas principales

| Rama | Propósito |
|------|-----------|
| `stable` | Código listo para producción. Todo lo que está aquí puede desplegarse en Firebase Hosting en cualquier momento. |
| `koss-fiscalito` | Rama de integración activa. Features completadas se fusionan aquí antes de ir a `stable`. |

**Regla de oro:** `stable` solo recibe merges desde `koss-fiscalito` (u otras ramas de feature) después de que el build pase sin errores TypeScript (`npm run build`).

---

## Flujo de trabajo

```
feature/nombre-corto
        │
        ▼
  koss-fiscalito  ──►  (review + build)  ──►  stable  ──►  deploy
```

### 1. Ramas de funcionalidad

Formato: `feature/<descripcion-corta>`

```bash
git checkout koss-fiscalito
git pull origin koss-fiscalito
git checkout -b feature/nuevo-tab-agente
```

Ejemplos válidos:
- `feature/comparador-multi-regimen`
- `feature/dashboard-service-cards`
- `fix/sidebar-mobile-responsive`

### 2. Ramas de corrección urgente

Formato: `fix/<descripcion>`

Si el bug está en producción (`stable`), la rama se abre desde `stable` y se fusiona directamente ahí, luego se sincroniza con `koss-fiscalito`.

### 3. Sincronizar `koss-fiscalito` con `stable`

Después de hacer merge a `stable`:
```bash
git push origin stable:koss-fiscalito
```

---

## Reglas de merge

- **Squash merge** para features pequeñas o fixes.
- **Merge commit** para features grandes con historial significativo.
- **No rebase en `stable`** — el historial de producción no se reescribe.
- Verificar que `npm run build` completa sin errores antes de fusionar.

---

## Checklist antes de hacer merge a `stable`

- [ ] `npm run build` — sin errores TypeScript
- [ ] Componentes nuevos usan CSS variables de `global.css` (sin colores hardcodeados)
- [ ] Llamadas async tienen `try/catch` y estado de error
- [ ] No hay `console.log()` en código de producción
- [ ] Rutas nuevas están registradas en `src/main.tsx` y protegidas si aplica
- [ ] Tipos TypeScript nuevos coinciden con el schema del Fiscal Agent API

---

## Convenciones de commits

Prefijos obligatorios:

| Prefijo | Cuándo usarlo |
|---------|---------------|
| `feat:` | Nueva página, componente o funcionalidad visible |
| `fix:` | Corrección de bug |
| `refactor:` | Reestructuración sin cambio de comportamiento |
| `style:` | Cambios puramente visuales (CSS, layout) |
| `chore:` | Config, dependencias, build |
| `docs:` | Documentación únicamente |

Ejemplo:
```
feat: rediseño dashboard con tarjetas por herramienta fiscal

Reemplaza CTA único de Fiscalito por grilla de tarjetas,
una por cada herramienta según el perfil del usuario.
Muestra último dato calculado por categoría desde Firestore.
```
