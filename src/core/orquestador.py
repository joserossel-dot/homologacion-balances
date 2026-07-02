"""Orquestador Central del Pipeline de Inteligencia Financiera.

Este módulo fusiona el mundo fiscal (TaxFolder/Carpeta Tributaria) con el
mundo contable (Balances), aplicando las reglas de riesgo bancario y
ejecutando auditorías cruzadas de coherencia antes de la pre-calificación.
"""

import logging
from typing import Dict, Any, List

# Importamos tu repositorio dinámico recién subido a GitHub
from db_repository import RepositorioDiccionario
# Importamos tus reglas especiales de riesgo patrimonial y leverage
from reglas_especiales import ProcesadorReglasEspeciales, calcular_patrimonio_efectivo
# Importamos el clasificador por códigos numéricos (DSI, Kame, Wilug)
from clasificador_codigo_cuenta import ClasificadorCodigo

logger = logging.getLogger(__name__)

class PipelineOrquestador:
    """Orquestador que unifica, audita y persiste el dossier del cliente."""

    def __init__(self, repo: RepositorioDiccionario) -> None:
        """Se le inyecta el repositorio para mantenerlo desacoplado."""
        self.repo = repo
        self.clasificador_codigo = ClasificadorCodigo()
        self.procesador_riesgo = ProcesadorReglasEspeciales()

    def procesar_analisis_completo(
        self, 
        datos_fiscales_raw: dict, 
        balance_raw: List[Dict[str, Any]], 
        giro_empresa: str
    ) -> dict:
        """
        Ejecuta el pipeline completo de extracción, homologación y cruce fiscal.
        
        :param datos_fiscales_raw: Datos crudos extraídos de la Carpeta Tributaria (F29/F22)
        :param balance_raw: Lista de cuentas extraídas del PDF del balance [{codigo, cuenta, monto}]
        :param giro_empresa: Actividad económica para calibración de activos (ej: Inmobiliaria)
        """
        resultado_final = {
            "coherencia_fiscal_contable": True,
            "desviacion_ventas_porcentaje": 0.0,
            "alertas_comite_riesgo": [],
            "balance_homologado": {},
            "patrimonio_efectivo_analisis": {}
        }

        # ── FASE 1: PROCESAMIENTO FISCAL ──────────────────────────────────────
        ventas_fiscales_anuales = datos_fiscales_raw.get("ventas_anuales_f29", 0.0)
        
        # ── FASE 2: HOMOLOGACIÓN CONTABLE (SINGLE-SHOT) ────────────────────────
        balance_procesado = {}
        monto_ac06s = 0.0  # Para acumular retiros/cuentas de socios

        for cuenta in balance_raw:
            cta_nombre = cuenta.get("cuenta_original", "")
            cta_codigo = cuenta.get("codigo_contable", None)
            cta_monto = cuenta.get("monto", 0.0)

            # 1. Intentar clasificar por código numérico (Máxima confianza)
            res_codigo = self.clasificador_codigo.clasificar(cta_codigo)
            codigo_estandar = res_codigo.codigo_estandar if res_codigo else None

            # 2. Si no hay código, ir al repositorio Postgres en la nube / fallback
            if not codigo_estandar:
                match_exacto = self.repo.buscar_exacto(cta_nombre)
                if match_exacto:
                    codigo_estandar = match_exacto[0].get("codigo_estandar")
                else:
                    # Búsqueda difusa por trigramas si es cuenta nueva
                    match_difuso = self.repo.buscar_similares_trgm(cta_nombre, limite=1)
                    if match_difuso:
                        codigo_estandar = match_difuso[0].get("codigo_estandar")
                    else:
                        codigo_estandar = "ANC.06"  # Otros activos/pasivos por defecto

            # 3. Aplicar Post-Procesamiento de Reglas Especiales
            ajuste = self.procesador_riesgo.aplicar(
                nombre_cuenta=cta_nombre,
                codigo_clasificado=codigo_estandar,
                monto=cta_monto,
                giro_empresa=giro_empresa
            )
            
            codigo_final = ajuste.codigo_final
            
            if ajuste.aplica and ajuste.flag:
                resultado_final["alertas_comite_riesgo"].append(
                    f"Regla Aplicada en {cta_nombre}: {ajuste.nota}"
                )

            # Acumular montos en el diccionario del balance estandarizado
            balance_procesado[codigo_final] = balance_procesado.get(codigo_final, 0.0) + cta_monto
            
            # Registrar si la cuenta mutó a cuenta de socios (Castigo patrimonial)
            if codigo_final == "AC.06S":
                monto_ac06s += cta_monto

        resultado_final["balance_homologado"] = balance_procesado

        # ── FASE 3: MOTOR DE VALIDACIÓN Y CRUCE (CROSS-CHECK) ──────────────────
        # Cruce A: Ventas F29 vs Ventas Contables (ER.01)
        ventas_contables = balance_procesado.get("ER.01", 0.0)
        
        if ventas_contables > 0:
            desviacion = abs(ventas_fiscales_anuales - ventas_contables) / ventas_contables
            resultado_final["desviacion_ventas_porcentaje"] = round(desviacion * 100, 2)
            
            if desviacion > 0.02:  # Tolerancia bancaria estricta del 2%
                resultado_final["coherencia_fiscal_contable"] = False
                resultado_final["alertas_comite_riesgo"].append(
                    f"CRÍTICO: Inconsistencia Fiscal-Contable. Desviación de ventas del "
                    f"{resultado_final['desviacion_ventas_porcentaje']}% entre F29 y Balance."
                )

        # Cruce B: Calibración de Patrimonio Efectivo con regla R5
        analisis_patrimonio = calcular_patrimonio_efectivo(balance_procesado, monto_ac06s)
        resultado_final["patrimonio_efectivo_analisis"] = analisis_patrimonio
        
        if analisis_patrimonio.get("alerta"):
            resultado_final["alertas_comite_riesgo"].append(
                f"RIESGO PATRIMONIAL: Cuenta corriente de socios ({monto_ac06s:,.0f}) "
                f"supera el 20% del patrimonio contable."
            )

        return resultado_final
