"""
reglas_especiales.py

Manejo de los 5 casos especiales detectados en el análisis del vaciador.
Se ejecuta DESPUÉS de la clasificación estándar, como post-procesamiento.

Reglas:
  R1: Banco con saldo negativo → PC.02 (sobregiro)
  R2: Terrenos en activo corriente en empresa inmobiliaria → AC.05
  R3: Ingresos percibidos por adelantado → PC.08 (pasivo, no activo)
  R4: Clientes con saldo negativo → PC.08 (anticipo recibido)
  R5: Cta. Cte. Socios → AC.06S + descuento de PAT (criterio conservador)
"""

import re
from dataclasses import dataclass
from typing import Optional


SECTORES_INMOBILIARIOS = {
    'inmobiliaria', 'arriendo bienes inmuebles', 'construccion',
    'promotora', 'bienes raices', 'desarrollo inmobiliario'
}


@dataclass
class AjusteEspecial:
    aplica: bool
    codigo_original: str
    codigo_final: str
    flag: Optional[str]
    nota: str


class ProcesadorReglasEspeciales:
    """
    Post-procesador que aplica las 5 reglas especiales después de la
    clasificación estándar. Recibe el resultado del motor híbrido
    y puede modificarlo.
    """

    def aplicar(
        self,
        nombre_cuenta: str,
        codigo_clasificado: str,
        monto: Optional[float],
        giro_empresa: Optional[str] = None,
    ) -> AjusteEspecial:
        """
        Aplica todas las reglas en orden. Retorna el ajuste si alguna aplica,
        o un AjusteEspecial con aplica=False si ninguna corresponde.
        """
        nombre_norm = nombre_cuenta.lower().strip()

        # R1: Banco negativo → sobregiro → PC.02
        r1 = self._r1_banco_negativo(nombre_norm, codigo_clasificado, monto)
        if r1.aplica:
            return r1

        # R2: Terrenos en corriente en inmobiliaria → inventario
        r2 = self._r2_terrenos_corriente(nombre_norm, codigo_clasificado, giro_empresa)
        if r2.aplica:
            return r2

        # R3: Ingresos percibidos adelantado → pasivo
        r3 = self._r3_ingresos_adelantado(nombre_norm, codigo_clasificado, monto)
        if r3.aplica:
            return r3

        # R4: Clientes negativo → anticipo recibido
        r4 = self._r4_clientes_negativo(nombre_norm, codigo_clasificado, monto)
        if r4.aplica:
            return r4

        # R5: Cta cte socios → ajuste patrimonio conservador
        r5 = self._r5_cta_socios(nombre_norm, codigo_clasificado)
        if r5.aplica:
            return r5

        return AjusteEspecial(
            aplica=False,
            codigo_original=codigo_clasificado,
            codigo_final=codigo_clasificado,
            flag=None,
            nota='Sin regla especial aplicable'
        )

    # ── REGLA 1 ───────────────────────────────────────────────────────────────
    def _r1_banco_negativo(
        self, nombre: str, codigo: str, monto: Optional[float]
    ) -> AjusteEspecial:
        """
        Si una cuenta de banco/disponible tiene saldo negativo (deudor < 0),
        es un sobregiro → reclasificar a PC.02.
        """
        es_banco = codigo == 'AC.01' or any(k in nombre for k in [
            'banco', 'cta cte', 'cuenta corriente banco',
            'disponible', 'efectivo'
        ])
        es_negativo = monto is not None and monto < 0

        if es_banco and es_negativo:
            return AjusteEspecial(
                aplica=True,
                codigo_original='AC.01',
                codigo_final='PC.02',
                flag='es_sobregiro',
                nota=f'Banco con saldo negativo (${monto:,.0f}) → sobregiro bancario → PC.02'
            )
        return AjusteEspecial(aplica=False, codigo_original=codigo,
                              codigo_final=codigo, flag=None, nota='')

    # ── REGLA 2 ───────────────────────────────────────────────────────────────
    def _r2_terrenos_corriente(
        self, nombre: str, codigo: str, giro_empresa: Optional[str]
    ) -> AjusteEspecial:
        """
        Terrenos clasificados en ANC.01, pero si el giro es inmobiliario
        y aparece en la sección corriente del balance → AC.05 (para venta).
        """
        es_terreno = bool(re.search(r'\bterreno(s)?\b', nombre))
        clasificado_como_anc01 = codigo == 'ANC.01'
        es_inmobiliaria = (
            giro_empresa is not None and
            any(s in giro_empresa.lower() for s in SECTORES_INMOBILIARIOS)
        )

        if es_terreno and clasificado_como_anc01 and es_inmobiliaria:
            return AjusteEspecial(
                aplica=True,
                codigo_original='ANC.01',
                codigo_final='AC.05',
                flag='terreno_para_venta',
                nota='Terrenos en empresa inmobiliaria → inventario para venta (AC.05)'
            )
        return AjusteEspecial(aplica=False, codigo_original=codigo,
                              codigo_final=codigo, flag=None, nota='')

    # ── REGLA 3 ───────────────────────────────────────────────────────────────
    def _r3_ingresos_adelantado(
        self, nombre: str, codigo: str, monto: Optional[float]
    ) -> AjusteEspecial:
        """
        'Ingresos percibidos por adelantado' es un PASIVO.
        Si el clasificador lo puso en activo, corregir a PC.08.
        """
        patron = re.search(
            r'ingreso(s)?\s+(percibido|recibido).*(adelantado|anticipado|avance)|'
            r'anticipo\s+de\s+cliente(s)?|'
            r'ing\s+percibido(s)?\s+por\s+adelantado',
            nombre
        )
        esta_en_activo = codigo.startswith('AC') or codigo.startswith('ANC')

        if patron and esta_en_activo:
            return AjusteEspecial(
                aplica=True,
                codigo_original=codigo,
                codigo_final='PC.08',
                flag='era_activo_incorrecto',
                nota='Ingresos percibidos adelantado → pasivo PC.08 (obligación de servicio)'
            )
        return AjusteEspecial(aplica=False, codigo_original=codigo,
                              codigo_final=codigo, flag=None, nota='')

    # ── REGLA 4 ───────────────────────────────────────────────────────────────
    def _r4_clientes_negativo(
        self, nombre: str, codigo: str, monto: Optional[float]
    ) -> AjusteEspecial:
        """
        Clientes con saldo negativo = anticipo recibido de cliente → PC.08.
        """
        es_cliente = codigo in ('AC.03', 'AC.04') or any(k in nombre for k in [
            'cliente', 'deudor por venta', 'factura por cobrar'
        ])
        es_negativo = monto is not None and monto < 0

        if es_cliente and es_negativo:
            return AjusteEspecial(
                aplica=True,
                codigo_original=codigo,
                codigo_final='PC.08',
                flag='anticipo_cliente_negativo',
                nota=f'Clientes con saldo negativo (${monto:,.0f}) → anticipo recibido → PC.08'
            )
        return AjusteEspecial(aplica=False, codigo_original=codigo,
                              codigo_final=codigo, flag=None, nota='')

    # ── REGLA 5 ───────────────────────────────────────────────────────────────
    def _r5_cta_socios(self, nombre: str, codigo: str) -> AjusteEspecial:
        """
        Cta. Cte. Socios en activo → AC.06S (criterio conservador).
        Se descuenta del patrimonio al calcular indicadores crediticios.
        """
        patron = re.search(
            r'(cuenta\s+(particular|corriente)\s+(socio|accionista))|'
            r'(cta\.?\s*(cte\.?|particular)\s+(socio|accionista))|'
            r'\bretiro(s)?\s+(de\s+)?(socio|utilidad)\b|'
            r'\bdividendo(s)?\s+(provisorio(s)?|anticipado(s)?|pagado(s)?)\b|'
            r'\bdistribucion(es)?\s+(a\s+)?(socio|accionista)\b|'
            r'\bsocios?\s+cuenta\s+corriente\b',
            nombre
        )

        if patron:
            return AjusteEspecial(
                aplica=True,
                codigo_original=codigo,
                codigo_final='AC.06S',
                flag='ajuste_patrimonio_conservador',
                nota=(
                    'Criterio conservador (BCI/Santander): cta cte socios = distribución encubierta. '
                    'Se clasifica en AC.06S y se descuenta del patrimonio para calcular '
                    'ROE y endeudamiento. Patrimonio efectivo = PAT - AC.06S.'
                )
            )
        return AjusteEspecial(aplica=False, codigo_original=codigo,
                              codigo_final=codigo, flag=None, nota='')


# ─────────────────────────────────────────────────────────────────────────────
# IMPACTO EN CALCULADORA DE INDICADORES
# ─────────────────────────────────────────────────────────────────────────────

def calcular_patrimonio_efectivo(
    estados: dict[str, float],
    monto_ac06s: float = 0.0
) -> dict:
    """
    Aplica el criterio conservador D5 al cálculo de patrimonio.
    Retorna patrimonio contable y efectivo para los indicadores.
    """
    pat_codigos = ['PAT.01', 'PAT.02', 'PAT.03', 'PAT.04']
    patrimonio_contable = sum(estados.get(c, 0) for c in pat_codigos)
    patrimonio_efectivo = patrimonio_contable - abs(monto_ac06s)

    return {
        'patrimonio_contable':  round(patrimonio_contable, 2),
        'ajuste_cta_socios':    round(abs(monto_ac06s), 2),
        'patrimonio_efectivo':  round(patrimonio_efectivo, 2),
        'tiene_ajuste':         monto_ac06s > 0,
        'alerta':               monto_ac06s > (patrimonio_contable * 0.20),
        # Si el ajuste supera el 20% del pat → alerta de riesgo crítico
    }


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    proc = ProcesadorReglasEspeciales()

    casos_test = [
        # (nombre, codigo_clasificado, monto, giro, regla_esperada)
        ('Banco BCI Cta Cte',             'AC.01',  -5_000_000, None,            'R1'),
        ('Banco Estado',                   'AC.01',  10_000_000, None,            'NINGUNA'),
        ('Terreno Los Andes',              'ANC.01',  8_000_000, 'inmobiliaria',  'R2'),
        ('Terreno',                        'ANC.01',  8_000_000, 'maestranza',    'NINGUNA'),
        ('Ingresos percibidos adelantado', 'AC.07',   3_000_000, None,            'R3'),
        ('Anticipo de clientes',           'AC.07',   2_000_000, None,            'R3'),
        ('Clientes Nacionales',            'AC.03',  -1_500_000, None,            'R4'),
        ('Clientes por Obra',              'AC.03',  15_000_000, None,            'NINGUNA'),
        ('Cuenta Particular Socio L Fig.', 'AC.06',  22_500_000, None,            'R5'),
        ('Cta Cte Socio los Guris',        'AC.06',  15_000_000, None,            'R5'),
        ('Dividendos Provisorios',         'PAT.04', 10_000_000, None,            'R5'),
        ('Distribuciones',                 'AC.06',   5_000_000, None,            'R5'),
    ]

    print(f"{'Cuenta':<35} {'Cód. inicial':<12} {'Cód. final':<12} {'Flag':<30} {'Regla'}")
    print('-' * 110)
    correctos = 0
    for nombre, codigo, monto, giro, regla_esp in casos_test:
        r = proc.aplicar(nombre, codigo, monto, giro)
        flag_str = r.flag or '-'
        aplico = 'R?' if r.aplica else 'NINGUNA'
        ok = '✓' if (r.aplica and regla_esp != 'NINGUNA') or (not r.aplica and regla_esp == 'NINGUNA') else '✗'
        print(f"{nombre:<35} {codigo:<12} {r.codigo_final:<12} {flag_str:<30} {ok}")
        if ok == '✓':
            correctos += 1

    print(f"\nPrecisión: {correctos}/{len(casos_test)} ({100*correctos/len(casos_test):.0f}%)")

    # Test cálculo patrimonio efectivo con ajuste D5
    print("\n── Test patrimonio efectivo (D5) ─────────────────────")
    estados_ejemplo = {
        'PAT.01': 50_000_000,
        'PAT.02':  5_000_000,
        'PAT.03': 80_000_000,
        'PAT.04': 33_000_000,
    }
    monto_socios = 22_500_000  # INGEFIRE: Cuenta Particular Socio L Figueroa

    resultado = calcular_patrimonio_efectivo(estados_ejemplo, monto_socios)
    print(f"  Patrimonio contable:  ${resultado['patrimonio_contable']:>15,.0f}")
    print(f"  Ajuste cta socios:  - ${resultado['ajuste_cta_socios']:>15,.0f}")
    print(f"  Patrimonio efectivo:  ${resultado['patrimonio_efectivo']:>15,.0f}")
    print(f"  Alerta riesgo:        {'⚠ SÍ — supera 20% del PAT' if resultado['alerta'] else 'No'}")
