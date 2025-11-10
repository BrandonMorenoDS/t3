# app.py


import core.priorizacion
import ui.session_manager
from data.conexion_sqlite import ConexionSQLite
import core.agendador

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import data.conexion_sqlite

# Obtengo el objeto conexión
conexion_activa = ConexionSQLite()

# Inicializar los pesos globales y internos
ui.session_manager.init_session()


# ---------------------------
# Función de asignación (simple)
# ---------------------------


# ---------------------------
# Acciones: marcar entregado / ausente
# ---------------------------
def marcar_entregado(id_asig):
    asign = st.session_state["asignaciones"]
    idx = asign.index[asign["id"] == id_asig]
    if len(idx) == 0:
        st.error("Asignación no encontrada")
        return
    i = idx[0]
    asign.at[i, "estado"] = "entregado"
    asign.at[i, "creado_ts"] = datetime.now().isoformat()
    st.session_state["asignaciones"] = asign
    # guardar

    st.success("Marcado como entregado")


def marcar_ausente(id_asig):
    asign = st.session_state["asignaciones"]
    recursos = st.session_state["recursos"]
    idxs = asign.index[asign["id"] == id_asig]
    if len(idxs) == 0:
        st.error("Asignación no encontrada")
        return
    i = idxs[0]
    asign.at[i, "intentos_falta"] = int(asign.at[i, "intentos_falta"]) + 1
    if asign.at[i, "intentos_falta"] == 1:
        asign.at[i, "estado"] = "ausente_1"
        st.info("Usuario marcado como ausente (1). Reprograma manualmente o ejecutar reasignación más tarde.")
    else:
        asign.at[i, "estado"] = "eliminado"
        # liberar recurso
        r_id = asign.at[i, "id_recurso"]
        recursos.loc[recursos["id"] == r_id, "estado"] = "disponible"
        st.info("Usuario eliminado por segunda falta. Reasignar disponible ahora.")
    asign.at[i, "creado_ts"] = datetime.now().isoformat()
    st.session_state["asignaciones"] = asign
    st.session_state["recursos"] = recursos


# ---------------------------
# Layout: navegación simple
# ---------------------------
st.sidebar.title("Navegación")
page = st.sidebar.radio("Ir a", ["Dashboard", "Registrar usuario", "Configuración"])

# ---------------------------
# Página: Registrar usuario
# ---------------------------
if page == "Registrar usuario":
    st.header("Registrar nuevo usuario")
    with st.form("form_registrar"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre completo")
            edad = st.number_input("Edad", min_value=0, max_value=120, value=18)
            ocupacion = st.selectbox("Ocupación",
                                     ["estudiante", "docente", "trabajador", "desempleado", "jubilado", "otro"])
        with col2:
            acceso_internet = st.selectbox("Acceso a internet", [0, 1], format_func=lambda x: "No" if x == 0 else "Sí",
                                           index=0)
            dispositivo_propio = st.selectbox("Dispositivo propio", [0, 1],
                                              format_func=lambda x: "No" if x == 0 else "Sí", index=0)
            personas_hogar = st.number_input("Personas en hogar", min_value=1, value=3)
            contacto = st.text_input("Contacto (tel/email)")
        registrar = st.form_submit_button("Registrar usuario")
        if registrar:
            usuarios = st.session_state["usuarios"]
            new_id = int(usuarios["id"].max()) + 1 if not usuarios.empty else 1
            nuevo = {
                "id": new_id,
                "nombre": nombre,
                "edad": edad,
                "ocupacion": ocupacion,
                "acceso_internet": acceso_internet,
                "dispositivo_propio": dispositivo_propio,
                "personas_hogar": personas_hogar,
                "fecha_registro": datetime.now().date().isoformat(),
                "contacto": contacto
            }
            usuarios = pd.concat([usuarios, pd.DataFrame([nuevo])], ignore_index=True)

            st.session_state["usuarios"] = usuarios

            conexion_activa.insertar_registro("usuarios", nuevo)
            st.success("Usuario registrado ✅")
            st.experimental_rerun()

# ---------------------------
# Página: Dashboard
# ---------------------------
if page == "Dashboard":
    st.title("Dashboard")
    # header metrics
    col1, col2, col3, col4 = st.columns(4)
    total_usuarios = len(st.session_state["usuarios"])
    total_recursos = len(st.session_state["recursos"])
    disponibles = len(st.session_state["recursos"][st.session_state["recursos"]["estado"] == "disponible"])
    asignados = len(st.session_state["asignaciones"][st.session_state["asignaciones"]["estado"] == "asignado"]) if not \
        st.session_state["asignaciones"].empty else 0
    col1.metric("Usuarios", total_usuarios)
    col2.metric("Recursos totales", total_recursos)
    col3.metric("Disponibles", disponibles)
    col4.metric("Asignados (pendientes entrega)", asignados)

    st.markdown("---")

    # Mostrar usuarios dataframe (colapsable)
    with st.expander("Ver tabla usuarios"):
        st.dataframe(st.session_state["usuarios"], use_container_width=True)

    # Panel central: controles (centrado)
    slider_disabled = not st.session_state["editando"]

    # Usamos los pesos actuales para el display (pesos_globales)
    # y los pesos temporales (temp_pesos) para el control en modo edición
    pesos_display = st.session_state["pesos_globales"]
    pesos_control = st.session_state["temp_pesos"]

    st.markdown("---")
    st.markdown("###  Controles de Prioridad Global")

    # Muestra el estado actual y el último guardado
    st.write(f"**Último Guardado:** `{st.session_state['last_saved'] or 'Nunca'}`")

    st.markdown("---")

    # --- SLIDERS Y ALINEACIÓN EN FILAS ---

    # 1. Ocupación
    colO, colSO = st.columns([1.5, 3.5], vertical_alignment="center")
    with colO:
        st.write(f"**Ocupación:** `{pesos_display['ocupacion']}`")
    with colSO:
        # Usamos el valor del slider para actualizar la variable temporal
        pesos_control["ocupacion"] = st.slider(
            "Peso global ocupación",
            1, 10,
            pesos_control["ocupacion"],
            disabled=slider_disabled,  # Estado de desactivación
            key='slider_ocupacion'
        )

    # 2. Acceso a Internet
    colI, colSI = st.columns([1.5, 3.5], vertical_alignment="center")
    with colI:
        st.write(f"**Acceso a internet:** `{pesos_display['acceso_internet']}`")
    with colSI:
        pesos_control["acceso_internet"] = st.slider(
            "Peso global acceso a internet",
            1, 10,
            pesos_control["acceso_internet"],
            disabled=slider_disabled,
            key='slider_internet'
        )

    # 3. Dispositivo Propio
    colD, colSD = st.columns([1.5, 3.5], vertical_alignment="center")
    with colD:
        st.write(f"**Dispositivo propio:** `{pesos_display['dispositivo_propio']}`")
    with colSD:
        pesos_control["dispositivo_propio"] = st.slider(
            "Peso global dispositivo propio",
            1, 10,
            pesos_control["dispositivo_propio"],
            disabled=slider_disabled,
            key='slider_dispositivo'
        )

    # 4. Edad
    colE, colSE = st.columns([1.5, 3.5], vertical_alignment="center")
    with colE:
        st.write(f"**Edad:** `{pesos_display['edad']}`")
    with colSE:
        pesos_control["edad"] = st.slider(
            "Peso global edad",
            1, 10,
            pesos_control["edad"],
            disabled=slider_disabled,
            key='slider_edad'
        )

    # --- ZONA DE BOTONES DE ACCIÓN ---
    st.markdown("---")

    if st.session_state["editando"]:
        # MODO EDICIÓN: Mostrar Guardar y Cancelar
        colG, colC, _ = st.columns([1.5, 1.5, 2])
        with colG:
            st.button("Guardar Cambios", on_click=ui.session_manager.guardar_cambios, use_container_width=True)
        with colC:
            st.button("Cancelar", on_click=ui.session_manager.cancelar_edicion, use_container_width=True)

    else:
        # MODO LECTURA: Mostrar solo Editar
        colE, _, _ = st.columns([1.5, 1.5, 2])
        with colE:
            st.button("✏Editar Pesos", on_click=ui.session_manager.cambiar_estado_edicion(), use_container_width=True)

    usuarios_ord = st.session_state["usuarios"].sort_values(["puntaje", "fecha_registro"],
                                                            ascending=[False, True]).reset_index(drop=True)
    st.subheader("Ranking (pendientes)")
    st.dataframe(usuarios_ord[["id", "nombre", "ocupacion", "puntaje"]], use_container_width=True)

    st.markdown("#### Asignar tablets")
    col_s1, col_s2, col_s3 = st.columns([1, 1, 2])
    with col_s1:
        stock = st.number_input("Stock a asignar", min_value=0, value=5)
    with col_s2:
        capacidad = st.number_input("Capacidad diaria", min_value=1, value=5)
    with col_s3:
        fecha_inicio = st.date_input("Fecha inicio", value=datetime.now().date())
    if st.button("Asignar tablets (usar ranking actual)"):
        core.agendador.agendar_citas_disponibles(conexion_activa, capacidad, fecha_inicio)

    st.markdown("---")
    st.subheader("Asignaciones actuales")
    asign = st.session_state["asignaciones"]

    st.dataframe(asign, use_container_width=True)

    st.markdown("---")
    # Export buttons
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("Exportar ranking CSV"):
            # usuarios_ord[["id", "nombre", "puntaje", "fecha_registro"]].to_csv("ranking_prioridad.csv", index=False)
            st.success("ranking_prioridad.csv creado")
    with col_e2:
        if st.button("Exportar asignaciones CSV"):
            st.session_state["asignaciones"].to_csv("asignaciones.csv", index=False)
            st.success("asignaciones.csv creado")

# ---------------------------
# Fin
# ---------------------------
