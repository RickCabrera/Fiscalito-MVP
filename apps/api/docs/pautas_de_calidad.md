# Pautas de calidad — Fiscal Agent API

## Principios fundamentales

1. **El motor fiscal es determinístico.** Ningún cálculo de ISR o IVA se delega al LLM. Las tablas ISR están hardcodeadas con fuente oficial (Anexo 8 RMF, DOF). El LLM solo genera texto explicativo.
2. **Stateless.** El API no guarda estado de usuario. Todo viaja en el request, se procesa, se responde.
3. **Fuente de verdad fiscal.** Cada tabla, tasa o límite debe citar el artículo LISR o la regla RMF correspondiente en el docstring o comentario.

---

## Estándares de código Python

### Type hints — obligatorios en toda función pública

```python
# ✅ Correcto
def calcular_isr_resico(ingresos_gravados: float) -> tuple[float, float]:
    ...

# ❌ Incorrecto
def calcular_isr_resico(ingresos):
    ...
```

### Docstrings en español

```python
def calcular_declaracion(
    contribuyente: PerfilContribuyente,
    facturas: list[CFDI],
    periodo_month: int,
) -> DesgloseFiscal:
    """
    Orquesta el cálculo de ISR e IVA para el periodo dado.

    Clasifica las facturas, aplica la lógica del régimen del contribuyente
    y retorna el desglose fiscal completo.
    """
```

### Sin `print()` en código de producción

Usar siempre el logger configurado:
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Calculando declaracion para RFC %s", contribuyente.rfc)
logger.exception("Error en cálculo: %s", e)
```

### Manejo de errores en endpoints

```python
# ✅ Correcto: HTTPException con mensaje claro
if req.ingresos_mensuales_estimados <= 0:
    raise HTTPException(status_code=400, detail="Los ingresos deben ser mayores a cero.")

# ❌ Incorrecto: dejar que el 500 explote solo
```

---

## Estándares de tests

### Regla: toda lógica de cálculo tiene test

Antes de hacer merge de cualquier cambio al motor fiscal (`fiscal_engine/`), debe existir al menos un test que valide el caso principal y uno que valide el caso borde (ingresos = 0, tope excedido, etc.).

### Estructura de tests

```python
class TestNombreModulo:
    def test_caso_principal(self):
        """Descripción breve del caso."""
        resultado = funcion_a_testear(...)
        assert resultado.campo == valor_esperado

    def test_caso_borde(self):
        """Caso borde: ingresos cero retorna ISR cero."""
        isr, tasa = calcular_isr_resico(0)
        assert isr == 0.0
```

### Ejecutar tests antes de cada commit

```bash
pytest tests/ -v
# Debe terminar: X passed, 0 failed
```

El número mínimo de tests aceptable es **el número actual** — no se hace merge si se rompen tests existentes.

---

## Estructura de archivos

| Capa | Carpeta | Responsabilidad |
|------|---------|-----------------|
| Endpoints | `app/routes/` | Validar request, llamar servicio, retornar response |
| Lógica fiscal | `app/fiscal_engine/` | Cálculos determinísticos. Sin llamadas HTTP, sin I/O |
| Schemas | `app/schemas/` | Modelos Pydantic de entrada/salida |
| Servicios | `app/services/` | Llamadas externas (LLM). Siempre tienen fallback estático |
| Tests | `tests/` | Un archivo por módulo de `fiscal_engine/` |

**Tamaño máximo de archivo:** 300 líneas. Si se excede, extraer a módulo.

---

## Modificar tablas ISR

Las tablas en `app/fiscal_engine/tablas_isr.py` se actualizan **una vez al año** cuando el SAT publica el Anexo 8 del RMF en el DOF (normalmente diciembre).

Checklist para actualizar tablas:
- [ ] Fuente citada en el comentario: `# Fuente: Anexo 8 RMF YYYY, DOF DD/mes/YYYY`
- [ ] Actualizar `TABLA_ISR_MENSUAL` (Art. 96) y `TABLA_ISR_ANUAL` (Art. 152)
- [ ] Las tasas RESICO **no cambian** (son inamovibles en Art. 113-E LISR)
- [ ] Actualizar `UMA_DIARIA_YYYY` con el valor publicado por INEGI
- [ ] Todos los tests existentes pasan con las nuevas tablas

---

## Seguridad

- Las API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) van **solo en `.env`**, nunca en código.
- `.env` está en `.gitignore`. Usar `.env.example` como template sin valores reales.
- El API no recibe ni almacena contraseñas, tokens de sesión ni datos bancarios.
- Los RFC se reciben como texto plano y no se persisten (stateless).

---

## Checklist de revisión de código

Antes de aprobar un PR:

- [ ] Tests pasan: `pytest tests/ -v`
- [ ] Sin `print()` ni secrets en código
- [ ] Nuevas funciones tienen type hints y docstring
- [ ] Cambios al motor fiscal citan artículo LISR o regla RMF
- [ ] Nuevos endpoints tienen schema Pydantic completo (request + response)
- [ ] El fallback del LLM funciona si `OPENAI_API_KEY` no está disponible
