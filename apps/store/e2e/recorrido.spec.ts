/**
 * El recorrido completo de un despacho (P6-04), por la UI real:
 * alta de despacho → cliente → e.firma/CSD → descarga SAT (falsa) → pólizas → balanza →
 * declaración → nómina → timbrado (PAC falso) → envío (correo falso).
 *
 * Lo único que se siembra por la API son las checadas: vienen de un aparato, no de una
 * pantalla. Las aserciones son sobre lo que el usuario VE (totales, estados), y los
 * importes salen de los CFDI sintéticos de `e2e/cfdis.py`:
 *   ventas 10,000 + 5,000 (IVA 2,400) y un gasto de 2,000 (IVA 320) en el mes anterior.
 */
import { expect, test, type Page } from '@playwright/test';
import {
  API, CLAVE_CLIENTE, CORREO_CONTADORA, EMPLEADO, RAZON_SOCIAL, RFC_CLIENTE, UID_CONTADORA,
  checadas, diasEntre, generarCertificados, mesAnterior,
} from './datos';

const MES = mesAnterior();

/** Entra por el sidebar, como el usuario. La entrada de Nómina lleva debajo el cliente activo. */
async function irA(page: Page, enlace: string) {
  await page.getByRole('navigation').getByRole('link', { name: new RegExp(`^${enlace}\\b`) }).first().click();
}

test('recorrido completo del despacho', async ({ page }) => {
  const certs = generarCertificados();

  await test.step('alta del despacho (registro + onboarding)', async () => {
    await page.goto('/login');
    await page.getByText('Registrate').click();
    await page.getByPlaceholder('tu@correo.com').fill(CORREO_CONTADORA);
    await page.getByPlaceholder('Minimo 6 caracteres').fill('secreto123');
    await page.getByRole('button', { name: 'Crear cuenta' }).click();
    await expect(page).toHaveURL(/\/app\/onboarding/);
    await page.getByPlaceholder('Tu nombre completo').fill('Laura Contadora');
    await page.getByPlaceholder('Despacho Contable Ejemplo').fill('Despacho Pruebas E2E');
    await page.getByPlaceholder('10 digitos').fill('5512345678');
    await page.getByRole('button', { name: /Siguiente/ }).click();
    await page.getByRole('button', { name: /Comenzar a usar/ }).click();
    await expect(page).toHaveURL(/\/app\/inicio/);
    await expect(page.getByText('0 clientes a la vista')).toBeVisible();
  });

  await test.step('alta del cliente', async () => {
    await irA(page, 'Clientes');
    await page.getByRole('button', { name: /^Nuevo cliente/ }).click();
    await page.getByLabel(/Identificador/i).fill(CLAVE_CLIENTE);
    await page.getByLabel(/Razón social/i).fill(RAZON_SOCIAL);
    await page.getByLabel(/Giro/i).fill('Comercio');
    await page.getByLabel(/Régimen fiscal/i).selectOption('601');
    await page.getByLabel(/^RFC/i).fill(RFC_CLIENTE);
    await page.getByLabel(/Código postal/i).fill('06000');
    await page.getByLabel(/Entidad federativa/i).selectOption('CMX');
    await page.getByLabel(/Clase de riesgo/i).selectOption({ label: 'Clase 1' });
    await page.getByLabel(/Registro patronal/i).fill('Y1234567890');
    await page.getByRole('button', { name: 'Dar de alta' }).click();
    await expect(page.getByText('1 / 25 clientes · plan Contador')).toBeVisible();
    await expect(page.getByRole('main').getByText(RAZON_SOCIAL, { exact: true })).toBeVisible();
  });

  await test.step('e.firma y CSD del cliente', async () => {
    await page.goto(`/app/clientes/${CLAVE_CLIENTE}`);
    for (const [tipo, certificado] of [['efirma', '30001000000500003416'], ['csd', '30001000000500003417']]) {
      const form = page.getByRole('form', { name: `Subir ${tipo}` });
      await form.getByLabel('Certificado (.cer)').setInputFiles(`${certs.dir}/${tipo}.cer`);
      await form.getByLabel('Llave privada (.key)').setInputFiles(`${certs.dir}/${tipo}.key`);
      await form.getByLabel('Contraseña de la llave').fill(certs.password);
      await form.locator('button[type=submit]').click();
      await expect(page.getByText(`Certificado ${certificado}`)).toBeVisible();
    }
    await expect(page.getByText(`RFC ${RFC_CLIENTE}`)).toHaveCount(2);
  });

  await test.step('descarga del SAT (falso) del mes anterior', async () => {
    await irA(page, 'Descarga SAT');
    await page.getByLabel('Descargar desde').fill(MES.desde);
    await page.getByLabel('Descargar hasta').fill(MES.hasta);
    await page.getByRole('button', { name: 'Descargar ahora' }).last().click();
    // El worker toma la solicitud, el SAT falso la termina a la primera verificación.
    await expect(async () => {
      await page.reload();
      await expect(page.getByText('Terminada: 2 XML nuevos en la bóveda')).toBeVisible({ timeout: 2_000 });
      await expect(page.getByText('Terminada: 1 XML nuevos en la bóveda')).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 60_000, intervals: [1_000, 2_000] });
    await irA(page, 'Bóveda');
    await page.getByLabel('Desde').first().fill(MES.desde);
    await page.getByLabel('Hasta').first().fill(MES.hasta);
    await expect(page.getByText('$11,600.00')).toBeVisible();
    await expect(page.getByText('$5,800.00')).toBeVisible();
    await expect(page.getByText('$2,320.00')).toBeVisible();
  });

  await test.step('pólizas del periodo desde la bóveda', async () => {
    await irA(page, 'Contabilito');
    await page.getByRole('tab', { name: 'Catálogo' }).click();
    await page.getByRole('button', { name: /Sembrar catálogo base/ }).click();
    await expect(page.getByText(/\d+ cuentas/)).toBeVisible();
    await page.getByRole('tab', { name: 'Pólizas' }).click();
    await page.getByLabel('Desde').fill(MES.desde);
    await page.getByLabel('Hasta').fill(MES.hasta);
    await page.getByRole('button', { name: /Generar pólizas del periodo/ }).click();
    await expect(page.getByText('3 generadas · 0 ya existían')).toBeVisible();
    await expect(page.getByText('3 pólizas · página 1 de 1')).toBeVisible();
  });

  await test.step('balanza de comprobación', async () => {
    await page.getByRole('tab', { name: 'Balanza' }).click();
    await page.getByLabel('Mes').fill(MES.aaaamm);
    await expect(page.getByText('La balanza cuadra: cargos = abonos y los saldos suman cero.')).toBeVisible();
    const totales = page.getByRole('row', { name: /^Totales/ });
    // Mes sin saldos iniciales: cargos = abonos = 17,400 de ventas cobradas + 2,320 del
    // gasto pagado + sus pasos por clientes/proveedores.
    await expect(totales.getByRole('cell')).toHaveText([
      'Totales', '0.00', '0.00', '$39,440.00', '$39,440.00', '$17,400.00', '$17,400.00',
    ]);
    await expect(page.getByRole('row', { name: /^Auxiliar de 401 Ingresos/ })).toContainText('$15,000.00');
    await expect(page.getByRole('row', { name: /^Auxiliar de 102 Bancos/ })).toContainText('$15,080.00');
  });

  await test.step('declaración: resumen de impuestos del mes', async () => {
    await irA(page, 'Fiscalito');
    await page.getByRole('button', { name: 'Resumen de impuestos' }).click();
    await page.getByLabel('Año').fill(String(MES.anio));
    await page.getByLabel('Mes').fill(String(MES.mes));
    await page.getByRole('button', { name: 'Calcular' }).click();
    // IVA a cargo = 2,400 trasladado − 320 acreditable (los recargos dependen del día).
    await expect(page.getByRole('row', { name: /^IVA a cargo/ })).toContainText('2080.00');
    await expect(page.getByRole('row', { name: /^ISR personas morales/ })).toBeVisible();
  });

  await test.step('nómina ordinaria de la quincena', async () => {
    await irA(page, 'Empleados');
    await page.getByRole('button', { name: 'Nuevo empleado' }).click();
    await page.getByLabel(/Número de empleado/i).fill(EMPLEADO.numero);
    await page.getByLabel(/^Nombre \*/i).fill(EMPLEADO.nombre);
    await page.getByLabel(/Apellido paterno/i).fill(EMPLEADO.paterno);
    await page.getByLabel(/Apellido materno/i).fill(EMPLEADO.materno);
    await page.getByLabel(/Nombre\(s\) de pila/i).fill(EMPLEADO.pila);
    await page.getByLabel(/Puesto/i).fill('Auxiliar');
    await page.getByLabel(/Correo/i).fill(EMPLEADO.correo);
    await page.getByLabel(/Salario diario/i).fill('450.00');
    await page.getByLabel(/Fecha de alta/i).fill('2025-01-15');
    await page.getByLabel(/RFC del trabajador/i).fill(EMPLEADO.rfc);
    await page.getByLabel(/CURP/i).fill(EMPLEADO.curp);
    await page.getByLabel(/CP del domicilio/i).fill('06000');
    await page.getByLabel(/NSS/i).fill(EMPLEADO.nss);
    await page.getByLabel(/employeeNo del aparato/i).fill(EMPLEADO.checador);
    await page.getByRole('button', { name: 'Dar de alta' }).click();
    await expect(page.getByRole('row', { name: new RegExp(`^${EMPLEADO.numero} ${EMPLEADO.nombre}`) })).toBeVisible();

    await irA(page, 'Nómina');
    await expect(page.getByLabel('Inicio del periodo')).toHaveValue(/^\d{4}-\d\d-\d\d$/);
    const inicio = await page.getByLabel('Inicio del periodo').inputValue();
    const fin = await page.getByLabel('Fin del periodo').inputValue();
    const r = await page.request.post(`${API}/api/v1/asistencia/eventos?cliente=${CLAVE_CLIENTE}&fuente=simulado`, {
      headers: { Authorization: `Bearer ${UID_CONTADORA}` },
      data: checadas(diasEntre(inicio, fin), EMPLEADO.checador),
    });
    expect(r.ok()).toBeTruthy();
    expect((await r.json()).recibidos).toBe(diasEntre(inicio, fin).length * 2);
    // El panel del checador se refresca solo cada 3 s.
    await expect(page.getByText(`${EMPLEADO.checador} (${EMPLEADO.checador})`).first()).toBeVisible();
    await page.getByRole('button', { name: 'Cerrar quincena' }).click();
    await expect(page.getByText(`Incidencias · ${inicio} a ${fin}`)).toBeVisible();
    await page.getByRole('button', { name: 'Calcular nómina' }).click();
    await expect(page.getByText(/Neto del periodo \$[\d,]+\.\d\d/)).toBeVisible();
    // 15 días de 450 (la quincena vale 15 días siempre, criterio default §D27).
    const recibo = page.getByRole('row', { name: new RegExp(`^${EMPLEADO.nombre} \\(${EMPLEADO.numero}\\) \\$`) });
    await expect(recibo).toContainText('$6,750.00');
  });

  await test.step('cierre y timbrado del periodo (PAC falso)', async () => {
    await page.getByRole('tab', { name: 'Historial' }).click();
    const fila = page.getByRole('row', { name: /ordinaria/ });
    await expect(fila).toContainText('calculada');
    await fila.getByRole('button', { name: 'Cerrar', exact: true }).click();
    await expect(fila).toContainText('cerrada');
    await fila.getByRole('button', { name: 'Abrir' }).click();
    await page.getByRole('button', { name: 'Timbrar' }).click();
    const recibo = page.getByRole('row', { name: new RegExp(`^${EMPLEADO.numero} ${EMPLEADO.nombre}`) });
    await expect(recibo).toContainText('Timbrado', { timeout: 60_000 });
    await expect(recibo).toContainText(/[0-9A-F]{8}-[0-9A-F]{4}-/);
    await expect(page.getByText('El PAC configurado es el de PRUEBAS')).toBeVisible();
    await expect(fila).toContainText('timbrada');
  });

  await test.step('envío de recibos por correo (falso)', async () => {
    const fila = page.getByRole('row', { name: /ordinaria/ });
    await fila.getByRole('button', { name: 'Enviar recibos' }).click();
    const panel = page.getByRole('region', { name: 'Envío de recibos' });
    await panel.getByRole('button', { name: 'Enviar recibos' }).click();
    await expect(async () => {
      await panel.getByRole('button', { name: 'Actualizar estado' }).click();
      await expect(panel.getByText(/1 enviado/)).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 60_000, intervals: [1_000, 2_000] });
    await expect(panel.getByRole('table', { name: 'Estado por recibo' })).toContainText(EMPLEADO.correo);
    await expect(panel.getByRole('table', { name: 'Estado por recibo' })).toContainText('enviado');
  });
});
