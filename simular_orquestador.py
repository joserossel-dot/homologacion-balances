import logging
import asyncio
from src.core.orquestador import PipelineOrquestador
from src.db_repository import RepositorioDiccionario

async def simular_pipeline():
    logging.basicConfig(level=logging.INFO)
    
    # Inicializamos el repositorio (operará en fallback si no detecta DATABASE_URL)
    repo = RepositorioDiccionario()
    await repo.inicializar()
    orquestador = PipelineOrquestador(repo)
    
    # 1. Datos simulados de Carpeta Tributaria (Ventas F29 acumuladas del año)
    datos_fiscales = {"ventas_anuales_f29": 100_000_000}
    
    # 2. Datos contables crudos simulados de un Balance PDF
    balance_pdf = [
        {"cuenta_original": "Ventas del Giro", "codigo_contable": "ER.01", "monto": 105_000_000}, # Provocará alerta > 2% desviación
        {"cuenta_original": "Banco de Chile", "codigo_contable": "AC.01", "monto": 12_000_000},
        {"cuenta_original": "Cta Cte Socio Juan", "codigo_contable": "AC.06S", "monto": 25_000_000}, # Retiro grande
        {"cuenta_original": "Capital Social", "codigo_contable": "PAT.01", "monto": 50_000_000}
    ]
    
    print("\n🚀 EJECUTANDO ORQUESTADOR CENTRAL...")
    analisis = await orquestador.procesar_analisis_completo(
        datos_fiscales_raw=datos_fiscales,
        balance_raw=balance_pdf,
        giro_empresa="Tecnologia"
    )
    
    print("\n⚠️ ALERTAS DE RIESGO GENERADAS:")
    for alerta in analisis["alertas_comite_riesgo"]:
        print(f"  - {alerta}")
        
    print("\n📊 BALANCE ESTANDARIZADO:")
    print(analisis["balance_homologado"])
    
    await repo.cerrar()

if __name__ == "__main__":
    asyncio.run(simular_pipeline())
