# Benchmark: Filtro de Líneas Basura (FASE 24B.2)

- **Fecha**: 2026-07-09
- **Documentos analizados**: 186
- **Líneas totales extraídas**: 58,924
- **Líneas identificadas como basura**: 217 (0.37%)
- **Cuentas del pipeline revisadas**: 6,763 (únicas)
- **Tiempo de escaneo**: 111.7s

## Resultados

| Métrica | Valor |
|---------|-------|
| Líneas totales | 58,924 |
| Líneas basura detectadas | 217 |
| Tasa de basura | 0.37% |
| Falsos negativos (basura → cuenta) | **0** |
| Falsos positivos (cuentas reales filtradas) | **0** |
| Correcciones (basura que el parser antiguo trataba como cuenta) | **10** |

## Falsos Positivos

**0** — ninguna cuenta real del pipeline (6,763 nombres únicos) fue filtrada.

### Correcciones del parser antiguo

**10** líneas que el parser antiguo trataba incorrectamente como cuentas contables y que ahora son correctamente filtradas:

- `Comuna : Bulnes PAGINA :`
- `DIRECCION : AV TAJAMAR 183 OF`
- `DIRECCION : AVENIDA LA DEHESA 1201 OFICINA`
- `DIRECCION : AVENIDA LAS TORRES`
- `DIRECCION : AVTAJAMAR 183 OF`
- `DIRECCION : BRTURO PRAT S/N SAN FELIX CIUDAD`
- `DIRECCION : DDD`
- `Dirección : SANTA MARIA`
- `Dirección: Alonso de Ercilla`
- `RUT:`

Todas ellas son basura (direcciones, etiquetas RUT, fragmentos de encabezado) que el parser aceptaba por no tener filtro de líneas basura. El filtro las elimina correctamente.

## Falsos Negativos

**0** — toda línea identificada como basura fue correctamente filtrada y no generó cuentas.

## Distribución por Patrón

| Patrón | Aciertos |
|--------|---------|
| Email | 6 |
| RUT | 2 |
| Página/Folio | 7 |
| Etiqueta admin (RUT/Domicilio/Comuna/etc.) | 72 |
| Firma/cargo | 30 |
| Decorador ---- | 71 |
| Fecha texto | 29 |
| **Total** | **217** |

No se activaron: URL, teléfono, firma auditoría, ornamento -N-, fecha numérica.

## Conclusión

- ✅ **0 falsos positivos** — ninguna cuenta real fue filtrada
- ✅ **0 falsos negativos** — toda basura detectada fue correctamente descartada
- ✅ **10 correcciones** — líneas de basura que el parser antiguo trataba como cuentas ahora se filtran correctamente
- ✅ **8.780 UNKNOWN** no se ven afectados (el filtro actúa antes de parsear, no cambia lógica de clasificación)
