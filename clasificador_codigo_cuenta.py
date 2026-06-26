"""
clasificador_codigo_cuenta.py

Módulo de clasificación por código de cuenta contable.
Es el PRIMER paso del pipeline, antes del diccionario.
Confianza: 0.95-0.98 (más alta que cualquier otro método)

Detectado en los balances reales analizados:
  - Formato DSI/genérico: 1-XX-YY-ZZ
  - Formato Wilug/compacto: XYYZZZ (7-8 dígitos)  
  - Formato KAME ONE: X.XX.YY.ZZ
  - Formato Inmobiliaria: XYYYYY (6-7 dígitos)
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ResultadoCodigo:
    codigo_estandar: str
    confianza: float
    tipo_formato: str
    razon: str


class ClasificadorCodigo:
    """
    Clasifica una cuenta contable basándose exclusivamente en su código numérico.
    Detecta el formato del código automáticamente y aplica el mapeo correspondiente.
    """

    # ── FORMATO 1: guiones separados  1-XX-YY-ZZ ─────────────────────────────
    # DSI, muchos sistemas contables chilenos modernos
    MAPEO_GUION = {
        # Activo corriente
        r'^1-01':          ('AC',    0.85),  # se refina con subgrupo
        r'^1-01-01':       ('AC.01', 0.97),  # caja/bancos
        r'^1-01-02':       ('AC.02', 0.93),  # inversiones CP
        r'^1-01-03':       ('AC.02', 0.90),
        r'^1-01-04':       ('AC.03', 0.97),  # clientes
        r'^1-01-05':       ('AC.04', 0.95),  # documentos x cobrar
        r'^1-01-06':       ('AC.07', 0.90),  # otras cxc / relacionadas
        r'^1-01-07':       ('AC.06', 0.95),  # relacionadas CP
        r'^1-01-08':       ('AC.05', 0.97),  # inventarios/existencias
        r'^1-01-09':       ('AC.07', 0.93),  # impuestos recuperar
        r'^1-01-10':       ('AC.07', 0.90),
        r'^1-01-11':       ('ANC.06', 0.88), # diferidos (puede ser nc)
        # Activo no corriente
        r'^1-02-01':       ('ANC.01', 0.97), # terrenos
        r'^1-02-02':       ('ANC.01', 0.97), # construcciones
        r'^1-02-03':       ('ANC.01', 0.97), # maquinarias/equipos
        r'^1-02-04':       ('ANC.01', 0.97), # muebles/útiles
        r'^1-02-05':       ('ANC.01', 0.97), # depreciación acumulada
        r'^1-02-06':       ('ANC.03', 0.95), # intangibles
        r'^1-02-07':       ('ANC.04', 0.93), # inversiones permanentes
        r'^1-03':          ('ANC.05', 0.92), # relacionadas LP
        # Pasivo corriente
        r'^2-01-01':       ('PC.02', 0.97),  # obligaciones bancarias
        r'^2-01-02':       ('PC.03', 0.95),  # leasing CP
        r'^2-01-03':       ('PC.01', 0.97),  # proveedores
        r'^2-01-04':       ('PC.07', 0.95),  # relacionadas CP pasivo
        r'^2-01-05':       ('PC.04', 0.97),  # factoring
        r'^2-01-06':       ('PC.08', 0.90),  # anticipos clientes
        r'^2-01-07':       ('PC.08', 0.90),  # provisiones varias
        r'^2-01-08':       ('PC.06', 0.97),  # remuneraciones
        r'^2-01-09':       ('PC.05', 0.97),  # impuestos
        r'^2-01-10':       ('PC.08', 0.88),
        r'^2-01-11':       ('PC.08', 0.85),
        r'^2-01-12':       ('PC.05', 0.93),
        r'^2-01-13':       ('PC.08', 0.88),
        r'^2-01-14':       ('PC.08', 0.87),
        # Pasivo no corriente
        r'^2-02-01':       ('PNC.01', 0.97), # banco LP
        r'^2-02-02':       ('PNC.02', 0.97), # leasing LP
        r'^2-02-03':       ('PNC.03', 0.95), # bonos
        r'^2-02-04':       ('PNC.04', 0.95), # relacionadas LP
        r'^2-02-05':       ('PNC.05', 0.90), # otros LP
        # Patrimonio
        r'^3-01-01':       ('PAT.01', 0.97),
        r'^3-01-02':       ('PAT.01', 0.93),
        r'^3-01-03':       ('PAT.02', 0.95),
        r'^3-01-04':       ('PAT.02', 0.93),
        r'^3-01-05':       ('PAT.03', 0.93),
        r'^3-01-06':       ('PAT.03', 0.95),
        r'^3-02':          ('PAT.03', 0.90),
        r'^3-03':          ('PAT.04', 0.95),
        r'^3-07':          ('PAT.04', 0.93),
        # Estado de Resultados
        r'^4-01':          ('ER.01', 0.96),
        r'^4-02':          ('ER.01', 0.93),
        r'^5-01':          ('ER.02', 0.97),
        r'^6-01-01':       ('ER.04', 0.93),
        r'^6-01-02':       ('ER.04', 0.90),
        r'^6-01-03':       ('ER.04', 0.95),
        r'^6-01-04':       ('ER.07', 0.97),
        r'^6-01-05':       ('ER.04', 0.90),
        r'^6-01-06':       ('ER.05', 0.95),
        r'^7-01':          ('ER.01', 0.88),
        r'^8-01':          ('ER.09', 0.95),
        r'^8-02':          ('ER.09', 0.90),
        r'^9-03':          ('ER.10', 0.97),
    }

    # ── FORMATO 2: compacto sin separador XYYZZZ (Wilug, Inmobiliaria) ────────
    MAPEO_COMPACTO = {
        r'^111[0-9]':      ('AC.01', 0.97),
        r'^112[0-9]':      ('AC.01', 0.97),
        r'^113[0-9]':      ('AC.07', 0.93),
        r'^114[0-9]':      ('AC.03', 0.95),
        r'^115[0-9]':      ('AC.06', 0.95),
        r'^116[0-9]':      ('AC.05', 0.97),
        r'^117[0-9]':      ('AC.04', 0.93),
        r'^118[0-9]':      ('AC.07', 0.95),
        r'^119[0-9]':      ('ANC.06', 0.88),
        r'^121[0-9]':      ('ANC.01', 0.95),
        r'^122[0-9]':      ('ANC.01', 0.97),
        r'^123[0-9]':      ('ANC.04', 0.93),
        r'^1010[0-9]':     ('AC.01', 0.97),
        r'^1011[0-9]':     ('AC.07', 0.93),
        r'^102[0-9]':      ('ANC.01', 0.97),
        r'^103[0-9]':      ('AC.06', 0.93),
        r'^213[0-9]':      ('PC.01', 0.95),
        r'^214[0-9]':      ('PC.07', 0.95),
        r'^217[0-9]':      ('PC.05', 0.97),
        r'^201[0-9]':      ('PC.02', 0.95),
        r'^202[0-9]':      ('PC.01', 0.93),
        r'^2010[12]':      ('PC.02', 0.95),
        r'^2010[3-9]':     ('PC.05', 0.93),
        r'^2020':          ('PNC.01', 0.95),
        r'^203[0-9]':      ('PAT.01', 0.95),
        r'^317[0-9]':      ('PAT.01', 0.97),
        r'^411[0-9]':      ('ER.01', 0.97),
        r'^401[0-9]':      ('ER.01', 0.97),
        r'^402[0-9]':      ('ER.01', 0.90),
        r'^301[0-9]':      ('ER.04', 0.85),  # personal/remuneraciones (sección resultados)
        r'^302[0-9]':      ('ER.04', 0.88),  # gastos generales (sección resultados)
        r'^404[0-9]':      ('ER.09', 0.85),  # corrección monetaria
        r'^511[0-9]':      ('ER.02', 0.97),
        r'^611[0-9]':      ('ER.04', 0.95),
        r'^812[0-9]':      ('ER.09', 0.97),
        r'^815[0-9]':      ('ER.10', 0.95),
    }

    # ── FORMATO 3: puntos  X.XX.YY.ZZ (KAME ONE) ─────────────────────────────
    MAPEO_PUNTO = {
        r'^1\.01':         ('AC',    0.85),
        r'^1\.01\.01':     ('AC.01', 0.97),
        r'^1\.01\.02':     ('AC.02', 0.93),
        r'^1\.01\.05':     ('AC.03', 0.97),
        r'^1\.01\.06':     ('AC.07', 0.92),
        r'^1\.01\.07':     ('AC.07', 0.92),
        r'^1\.01\.09':     ('AC.05', 0.97),
        r'^1\.01\.10':     ('AC.07', 0.93),
        r'^1\.01\.11':     ('AC.07', 0.90),
        r'^1\.02':         ('ANC.01', 0.95),
        r'^1\.02\.01':     ('ANC.01', 0.97),
        r'^1\.02\.02':     ('ANC.01', 0.97),
        r'^1\.02\.03':     ('ANC.01', 0.97),
        r'^1\.02\.04':     ('ANC.01', 0.97),
        r'^1\.02\.06':     ('ANC.01', 0.97),
        r'^1\.03':         ('ANC.05', 0.90),
        r'^2\.01\.01':     ('PC.02', 0.97),
        r'^2\.01\.07':     ('PC.01', 0.97),
        r'^2\.01\.06':     ('PC.04', 0.97),  # factoring en KAME
        r'^2\.01\.08':     ('PC.06', 0.97),
        r'^2\.01\.12':     ('PC.05', 0.97),
        r'^2\.01\.14':     ('PC.08', 0.90),
        r'^2\.02\.01':     ('PNC.01', 0.97),
        r'^2\.03\.01':     ('PAT.01', 0.97),
        r'^2\.03\.02':     ('PAT.01', 0.93),
        r'^2\.03\.06':     ('PAT.03', 0.95),
        r'^2\.03\.07':     ('PAT.04', 0.97),
        r'^3\.01':         ('ER.01', 0.95),
        r'^3\.02':         ('ER.01', 0.88),
        r'^4\.01':         ('ER.02', 0.95),
        r'^4\.02':         ('ER.04', 0.93),
        r'^4\.03\.01':     ('ER.10', 0.97),
    }

    def __init__(self):
        # Compilar patrones ordenados de más específico a más general
        self._guion = [(re.compile(p), c, f) for p, (c, f) in sorted(
            self.MAPEO_GUION.items(), key=lambda x: -len(x[0]))]
        self._compacto = [(re.compile(p), c, f) for p, (c, f) in sorted(
            self.MAPEO_COMPACTO.items(), key=lambda x: -len(x[0]))]
        self._punto = [(re.compile(p), c, f) for p, (c, f) in sorted(
            self.MAPEO_PUNTO.items(), key=lambda x: -len(x[0]))]

    def detectar_formato(self, codigo: str) -> str:
        """Detecta el tipo de formato del código."""
        if not codigo or not codigo.strip():
            return 'sin_codigo'
        c = codigo.strip()
        if '-' in c and re.match(r'^\d+-\d+', c):
            return 'guion'
        if '.' in c and re.match(r'^\d+\.\d+', c):
            return 'punto'
        if re.match(r'^\d{6,10}$', c):
            return 'compacto'
        return 'desconocido'

    def clasificar(self, codigo: Optional[str]) -> Optional[ResultadoCodigo]:
        """
        Clasifica una cuenta por su código.
        Retorna None si no hay código o no se puede clasificar.
        """
        if not codigo or not codigo.strip():
            return None

        codigo = codigo.strip()
        formato = self.detectar_formato(codigo)

        if formato == 'guion':
            return self._buscar_en_mapa(codigo, self._guion, 'guion_separado')
        elif formato == 'punto':
            return self._buscar_en_mapa(codigo, self._punto, 'punto_separado')
        elif formato == 'compacto':
            return self._buscar_en_mapa(codigo, self._compacto, 'compacto')

        return None

    def _buscar_en_mapa(
        self, codigo: str,
        patrones: list[tuple],
        tipo_formato: str
    ) -> Optional[ResultadoCodigo]:
        for patron, cod_estandar, confianza in patrones:
            if patron.match(codigo):
                return ResultadoCodigo(
                    codigo_estandar=cod_estandar,
                    confianza=confianza,
                    tipo_formato=tipo_formato,
                    razon=f"Código {codigo} coincide con patrón → {cod_estandar}"
                )
        return None


# ── Tests rápidos ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    clf = ClasificadorCodigo()

    casos = [
        # DSI
        ('1-01-01-02-01', 'Banco Bci'),
        ('1-01-04-01-01', 'Clientes Ventas a Credito'),
        ('1-01-08-01-02', 'Materiales Directos'),
        ('2-01-03-01-01', 'Proveedores Nacionales'),
        ('2-01-08-01-01', 'Remuneraciones por Pagar'),
        ('2-01-09-01-01', 'IVA Débito Fiscal'),
        ('2-02-01-01-01', 'Obligaciones Bancos LP'),
        ('3-01-01-01-01', 'Capital Pagado'),
        ('4-01-01-01-01', 'Ingresos por ventas'),
        ('5-01-01-01-01', 'Costo de Venta'),
        ('6-01-03-01-01', 'Gastos Administración'),
        ('6-01-06-01-01', 'Gastos de Venta'),
        ('8-01-02-01-02', 'Intereses Bancarios'),
        # Wilug
        ('1112001', 'BANCO DE CHILE'),
        ('1141001', 'CLIENTES NACIONALES'),
        ('1161001', 'EXISTENCIAS ANSUL'),
        ('2131001', 'PROVEEDORES NACIONALES'),
        ('2171003', 'IMPUESTOS POR PAGAR (F29)'),
        ('4111001', 'VENTAS NACIONALES'),
        ('5111001', 'COSTOS EN MANO DE OBRA'),
        ('8121004', 'INTERES Y GASTOS FACTORING'),
        # KAME ONE
        ('1.01.01.02', 'Banco Cta Cte BCI'),
        ('1.01.05.01', 'Clientes por Serv y Mantencion'),
        ('1.02.03.01', 'Maquinarias y equipos'),
        ('2.01.01.01', 'Prestamo Bancario Banco Estado'),
        ('2.01.07.01', 'Proveedores Nacionales'),
        ('2.03.01.01', 'Capital'),
        ('3.01.01.01', 'Ventas Afectas Obras y Montajes'),
        ('4.01.02.01', 'Costo de Material de Obras'),
    ]

    print(f"{'Código':<22} {'Nombre':<35} {'→ Estándar':<12} {'Conf':>6} {'Formato'}")
    print('-' * 90)
    correctos = 0
    for codigo, nombre in casos:
        r = clf.clasificar(codigo)
        if r:
            print(f"{codigo:<22} {nombre[:34]:<35} {r.codigo_estandar:<12} {r.confianza:>6.2f} {r.tipo_formato}")
            correctos += 1
        else:
            print(f"{codigo:<22} {nombre[:34]:<35} {'NO CLASIFICADO':<12}")

    print(f"\nClasificados: {correctos}/{len(casos)} ({100*correctos/len(casos):.0f}%)")
