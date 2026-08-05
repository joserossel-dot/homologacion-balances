# P2 — Knowledge Manager: Mockup de UI (pestaña Streamlit)

Fecha: 2026-08-03 · Tipo: MOCKUP Y ARQUITECTURA — **no implementada aún** · Aditivo a `app_validacion.py`
(no se toca ninguna pestaña existente).

---

## 1. Ubicación

Nueva pestaña en la barra de `st.tabs` (`app_validacion.py:614`) — se agrega como `tab_knowledge_manager`
sin modificar las 8 pestañas existentes.

```
tab_resumen, tab_revision, tab_balance, tab_diccionario, tab_aprendizaje,
tab_analytics, tab_conocimiento, tab_inteligencia, tab_km = st.tabs(...)
```

> La pestaña se agrega al final para no cambiar el orden ni el comportamiento actual.

---

## 2. Estructura de la pestaña

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🧠 Knowledge Manager                                          [buscar 🔍] │
│ (filtros: Estado ▾ | Tipo ▾ | Batch ▾ | Fecha desde-hasta ▾)              │
├────────┬────────┬────────┬────────┬────────┬─────────────────────────────┤
│ 📥     │ 🚀     │ ⚔️     │ 🗃️     │ 📜     │  Panel de detalle            │
│ Pend.  │ Prom.  │ Conf.  │ Vers.  │ Hist.  │  (contextual)               │
│ (n)    │ (n)    │ (n)    │ (n)    │ (n)    │                             │
├────────┴────────┴────────┴────────┴────────┴─────────────────────────────┤
│                                                                          │
│  ════ TAB 1: PENDIENTES ════                                             │
│  Candidatos de gold_records sin proceso (final_code != '', no batch)     │
│  [✔ Aprobar todo AUTO (106)]  [🔍 Previsualizar]  [🧹 Recargar]         │
│                                                                          │
│  | # | Cuenta        | Código | Reviewer     | Confianza | Acción       |│
│  | 1 | Caja          | AC.01  | analista     | ALTA      | [✔] [✖]     │
│  | 2 | Proveedores   | PC.01  | analista     | ALTA      | [✔] [✖]     │
│  | … | …             | …      | …            | …         | …            │
│                                                                          │
│  ════ TAB 2: PROMOCIONES ════                                             │
│  Batches: id | estado | auto | review | discard | conflict | fecha       │
│  Botón por fila: [Detalle] [Aprobar] [Rechazar] [Aplicar] [Dry-run]      │
│                                                                          │
│  ════ TAB 3: CONFLICTOS ════                                              │
│  Normalized | Códigos | Frecuencia | Resolución | Acción                 │
│  (cada fila permite elegir código + nota + [Confirmar])                  │
│                                                                          │
│  ════ TAB 4: VERSIONES ════                                              │
│  v# | label | batch | fecha | cuentas | diff | [Detalle] [Rollback]      │
│                                                                          │
│  ════ TAB 5: HISTORIAL ════                                              │
│  timestamp | actor | evento | cuenta | código | batch | decisión         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mockup de cada tab

### 3.1 Tab "📥 Pendientes"

**Objetivo:** revisar y decidir sobre candidatos aún no agrupados.

- Métricas arriba: total pendientes, aprobables AUTO, requieren revisión, descartables.
- Tabla con checkboxes de selección múltiple.
- Botón principal: **"Aprobar selección (auto)"** → crea batch, lo somete a aprobación.
- Botón **"Previsualizar"** → `PromotionBatch.dry_run()` sin escribir.
- Cada fila muestra: cuenta, normalized, código final, reviewer, confianza (P1.2 ALTA/MEDIA/BAJA).

### 3.2 Tab "🚀 Promociones"

**Objetivo:** gestionar batches ya creados.

- Tabla de batches con estado (pending/approved/applied/rejected/rolled_back).
- Acciones por fila: **Detalle** (modal con candidatos), **Aprobar**, **Rechazar**, **Aplicar** (solo si
  aprobado), **Dry-run** (previsualizar sin aplicar).
- Filtro por estado.
- `apply()` escribe SOLO en `gold_standard_runtime.db`; nunca en el benchmark.

### 3.3 Tab "⚔️ Conflictos"

**Objetivo:** resolver el mismo nombre → códigos distintos.

- Lista de `conflict_resolution` con estado open/resolved/discarded.
- Selector de código por conflicto + campo nota + botón **Confirmar resolución**.
- Una resolución confirmada habilita que el candidato vuelva al batch (re-clasificado).

### 3.4 Tab "🗃️ Versiones"

**Objetivo:** historial y rollback del conocimiento runtime.

- Lista de `knowledge_versions` con métricas y diff.
- Botón **Detalle** → muestra snapshot + diff.
- Botón **Rollback a esta versión** → `KnowledgeManager.rollback()` con confirmación explícita.
- Nunca afecta el benchmark.

### 3.5 Tab "📜 Historial"

**Objetivo:** auditoría completa.

- Flujo plano (`promotion_history` + `approval_log`) con filtros por actor, evento, batch, rango de fechas.
- Buscador por cuenta/código.
- Solo lectura (nada se borra).

---

## 4. Filtros y búsqueda globales

- **Filtros** (barra superior): Estado, Tipo (AUTO/REVISION/DESCARTE), Batch id, Rango de fechas.
- **Búsqueda**: texto libre sobre `account_name`, `normalized`, `candidate_code` (fuzzy, sin tocar el motor).

---

## 5. Fuente de datos (solo lectura) y destinos

| Sección | Lee de | Escribe |
|---|---|---|
| Pendientes | `gold_records` (gold_standard.db) | `knowledge_meta.db` (batch + historial) |
| Promociones | `knowledge_meta.db` (batches) | `gold_standard_runtime.db` (apply), `knowledge_meta.db` |
| Conflictos | `knowledge_meta.db` (conflict_resolution) | `knowledge_meta.db` |
| Versiones | `knowledge_meta.db` (knowledge_versions) | `gold_standard_runtime.db` (rollback) |
| Historial | `knowledge_meta.db` (promotion_history, approval_log) | — |

---

## 6. Mockup en Streamlit (pseudocódigo)

```python
def _tab_knowledge_manager():
    st.subheader("🧠 Knowledge Manager")
    f1, f2, f3, f4, busca = st.columns(5)
    estado = f1.selectbox("Estado", ["todos", "pending", "approved", "applied", ...])
    tipo = f2.selectbox("Tipo", ["todos", "AUTO", "REVISION", "DESCARTE"])
    batch = f3.number_input("Batch id", min_value=0, value=0)
    q = busca.text_input("Buscar", placeholder="cuenta o código...")

    tab_pend, tab_prom, tab_conf, tab_ver, tab_hist = st.tabs(
        ["📥 Pendientes", "🚀 Promociones", "⚔️ Conflictos",
         "🗃️ Versiones", "📜 Historial"])

    with tab_pend:
        cands = km.pending_candidates()
        df = pd.DataFrame(cands)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if st.button("✔ Aprobar selección (auto)", use_container_width=True):
            b = km.create_batch(cands, user=st.session_state.get("user", "ui"))
            km.submit_for_approval(b, user="ui")
            st.success(f"Batch {b} creado y sometido a aprobación")

    with tab_prom:
        for b in km.list_batches(estado=None):
            det = km.batch_detail(b["id"])
            c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
            c1.write(f"Batch #{b['id']} · {b['status']} · auto={b['auto_count']} …")
            c2.button("Detalle", key=f"d{b['id']}")
            c3.button("Aprobar", key=f"a{b['id']}")
            c4.button("Rechazar", key=f"r{b['id']}")
            c5.button("Aplicar", disabled=(b['status'] != 'approved'), key=f"ap{b['id']}")

    with tab_conf:
        for c in km.conflicts():
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.write(f"{c['normalized']} → {c['codes']}")
            c2.selectbox("Código", c["codes"], key=f"cc{c['id']}")
            c3.button("Confirmar", key=f"cf{c['id']}")

    with tab_ver:
        for v in km.versions():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"v{v['version']} · {v['label']} · {v['created_at']}")
            c2.button("Detalle", key=f"vd{v['id']}")
            c3.button("Rollback", key=f"vr{v['id']}")

    with tab_hist:
        st.dataframe(km.search(q, estado, tipo, batch),
                     use_container_width=True, hide_index=True)
```

---

## 7. Arquitectura de la UI

```
_tab_knowledge_manager()  (nuevo, app_validacion.py)
   └─► KnowledgeManager (API)          knowledge_manager/
         ├─ pending_candidates()        gold_records
         ├─ create_batch()/apply()      gold_standard_runtime.db + knowledge_meta.db
         ├─ conflicts()                 knowledge_meta.db
         ├─ versions()/rollback()       gold_standard_runtime.db + knowledge_meta.db
         └─ search()                    knowledge_meta.db
```

- La pestaña es **delgada** (solo UI); toda la lógica está en `knowledge_manager/`.
- Sin estado global nuevo requerido; `st.session_state` para el usuario activo y selecciones.

---

## 8. Restricciones

- No se modifica ninguna pestaña existente.
- No se importa el motor (`learning/*`) desde la UI del KM.
- Todas las escrituras pasan por `knowledge_manager/` y apuntan a runtime/meta, nunca al benchmark.
