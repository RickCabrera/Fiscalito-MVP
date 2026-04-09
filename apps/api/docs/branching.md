# Estrategia de ramas — Fiscal Agent API

## Rama principal

| Rama | Propósito |
|------|-----------|
| `stable` | Código listo para producción. Todo lo que está aquí puede desplegarse en Cloud Run en cualquier momento. |
| `main` | Mirror de `stable`. Se mantiene sincronizado después de cada release. |

**Regla de oro:** nunca se hace push directo a `stable` sin que los tests pasen (`pytest tests/ -v`).

---

## Flujo de trabajo

```
feature/nombre-corto
        │
        ▼
    (PR + review)
        │
        ▼
      stable  ──►  deploy Cloud Run
```

### 1. Ramas de funcionalidad

Formato: `feature/<descripcion-corta>`

```bash
git checkout stable
git pull origin stable
git checkout -b feature/nuevo-endpoint-diot
```

Ejemplos válidos:
- `feature/comparador-multi-regimen`
- `feature/agente-tool-retenciones`
- `fix/isr-arrendamiento-predial`

### 2. Ramas de corrección urgente

Formato: `fix/<descripcion>`

Se abren desde `stable` y se fusionan directamente a `stable` una vez verificados los tests.

### 3. Ramas de experimento / worktree de agentes IA

Formato: `worktree-agent-<id>` (generadas automáticamente por Claude Code)

Estas ramas son temporales. Se fusionan a `stable` o se eliminan. **No deben quedar abiertas en remote por más de 48 horas.**

Para limpiar ramas de agentes:
```bash
git branch -r | grep worktree-agent | sed 's/origin\///' | xargs -I{} git push origin --delete {}
```

---

## Reglas de merge

- **Squash merge** para features pequeñas (1-3 commits relacionados).
- **Merge commit** para features grandes o integraciones entre módulos.
- **No rebase en `stable`** — el historial de producción no se reescribe.
- El mensaje del commit de merge debe describir el cambio funcional, no los pasos intermedios.

---

## Checklist antes de hacer merge a `stable`

- [ ] `pytest tests/ -v` — todos los tests pasan (actualmente 84/84)
- [ ] No hay `print()` ni `logger.debug()` innecesarios
- [ ] Nuevos endpoints tienen su schema Pydantic completo
- [ ] Si se modificaron tablas ISR, hay fuente oficial en el docstring
- [ ] El servicio arranca sin errores: `uvicorn app.main:app --reload`

---

## Convenciones de commits

Prefijos obligatorios:

| Prefijo | Cuándo usarlo |
|---------|---------------|
| `feat:` | Nueva funcionalidad o endpoint |
| `fix:` | Corrección de bug |
| `refactor:` | Reestructuración sin cambio de comportamiento |
| `test:` | Agregar o corregir tests |
| `chore:` | Config, dependencias, CI |
| `docs:` | Documentación únicamente |

Ejemplo:
```
feat: comparador multi-régimen — 5 regímenes de PF entre sí

Calcula ISR estimado para 626, 612, 606, 625 y 605.
Ordena resultados de menor a mayor costo fiscal.
Tests: 9 nuevos en TestComparador.
```
