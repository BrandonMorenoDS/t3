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
# graficos
import matplotlib.pyplot as plt
import seaborn as sns

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
page = st.sidebar.radio("Ir a", ["Dashboard", "Registrar usuario","Graficos"])

# ---------------------------
# Página: Registrar usuario
# ---------------------------
if page == "Registrar usuario":
    st.header("Registrar nuevo usuario")
    with st.form("form_registrar"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Ingrese su nombres")
            apellidos = st.text_input("Ingrese sus apellidos")
            edad = st.number_input("Edad", min_value=0, max_value=120, value=18)
            ocupacion = st.selectbox("Ocupación",
                                     ["Estudiante", "Empleado", "Jubilado", "Desempleado", "Otro"])
            direccion = st.text_input("Ingrese su direccion")

        with col2:
            acceso_internet = st.selectbox("Acceso a internet", [0, 1], format_func=lambda x: "No" if x == 0 else "Sí",
                                           index=0)
            dispositivo_propio = st.selectbox("Dispositivo propio", [0, 1],
                                              format_func=lambda x: "No" if x == 0 else "Sí", index=0)
            correo_electronico = st.text_input("Correo electrónico", value=None)

            sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])

            telefono = st.text_input("Ingrese su telefono")

        registrar = st.form_submit_button("Registrar usuario")
        if registrar:
            usuarios = st.session_state["usuarios"]
            new_id = int(usuarios["id"].max()) + 1 if not usuarios.empty else 1
            nuevo = {
                "id": new_id,
                "nombre": nombre,
                "apellidos": apellidos,
                "edad": edad,
                "sexo": sexo,
                "direccion": direccion,
                "telefono": telefono,
                "correo_electronico": correo_electronico,
                "ocupacion": ocupacion,
                "internet": acceso_internet,
                "dispositivo": dispositivo_propio,
                "fecha_registro": datetime.now().date().isoformat(),
            }
            usuarios = pd.concat([usuarios, pd.DataFrame([nuevo])], ignore_index=True)

            st.session_state["usuarios"] = usuarios

            conexion_activa.insertar_registro("usuarios", nuevo)
            st.success("Usuario registrado ✅")

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
    col_s1, col_s2 = st.columns([1, 1])
    with col_s1:
        capacidad = st.number_input("Capacidad diaria", min_value=1, value=5)
    with col_s2:
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
# Pagina : Graficos
# ---------------------------

if page == "Graficos":

    st.title("📊 Análisis y Estadísticas de Usuarios")

    # --- Cargar datos ---
    usuarios_df = st.session_state["usuarios"]

    # --- Validación de datos ---
    if usuarios_df is None or usuarios_df.empty:
        st.warning("⚠️ No hay datos registrados aún.")
        st.stop()
    # --- ¡NUEVA SECCIÓN DE PRESUPUESTO! ---
    # (El código de la función está en core/agendador.py)
    core.agendador.calcular_y_mostrar_presupuesto()
    st.markdown("---")
    # --- FIN DE LA NUEVA SECCIÓN ---
    st.write("👥 Total de usuarios registrados:", len(usuarios_df))

    # --- Tema visual coherente con Streamlit ---
    sns.set_theme(style="whitegrid")
    plt.rcParams["figure.facecolor"] = "#0E1117"
    plt.rcParams["axes.facecolor"] = "#0E1117"
    plt.rcParams["text.color"] = "white"
    plt.rcParams["axes.labelcolor"] = "white"
    plt.rcParams["xtick.color"] = "white"
    plt.rcParams["ytick.color"] = "white"

    # --- GRÁFICO DE DISTRIBUCIÓN DE PUNTAJES ---
    st.subheader("Distribución de Puntajes de Prioridad")
    if "puntaje" in usuarios_df.columns:
        # Asegurarse de que el puntaje sea numérico
        puntajes_num = pd.to_numeric(usuarios_df["puntaje"], errors='coerce').dropna()

        if not puntajes_num.empty:
            fig_puntaje, ax_puntaje = plt.subplots()
            sns.histplot(puntajes_num, bins=15, kde=True, color="#58a6ff", ax=ax_puntaje)
            ax_puntaje.set_xlabel("Puntaje")
            ax_puntaje.set_ylabel("Cantidad de Usuarios")
            ax_puntaje.set_title("Distribución de Puntajes", color="white")
            st.pyplot(fig_puntaje)
        else:
            st.info("No hay datos de puntaje válidos para mostrar.")
    else:
        st.info("La columna 'puntaje' no está disponible en los datos de sesión.")
    # --- FIN DE GRÁFICO NUEVO ---

    # --- DISTRIBUCIÓN POR OCUPACIÓN ---
    st.subheader("Distribución de usuarios por ocupación")
    if "ocupacion" in usuarios_df.columns:
        ocupacion_counts = usuarios_df["ocupacion"].value_counts()
        st.bar_chart(ocupacion_counts)
    else:
        st.info("No se encontró la columna 'ocupacion'.")

    # --- DISTRIBUCIÓN DE EDADES ---
    st.subheader("Distribución de edades")
    if "edad" in usuarios_df.columns:
        fig1, ax1 = plt.subplots()
        sns.histplot(usuarios_df["edad"], bins=10, kde=True, color="#58a6ff", ax=ax1)
        ax1.set_xlabel("Edad")
        ax1.set_ylabel("Cantidad")
        ax1.set_title("Distribución de edades de los usuarios", color="white")
        st.pyplot(fig1)
    else:
        st.info("No se encontró la columna 'edad'.")

    # --- DISTRIBUCIÓN POR SEXO (Pie Chart) ---
    st.subheader("Distribución por sexo")
    if "sexo" in usuarios_df.columns:
        sexo_counts = usuarios_df["sexo"].value_counts()
        fig2, ax2 = plt.subplots(facecolor="#0E1117")
        ax2.set_facecolor("#0E1117")
        ax2.pie(
            sexo_counts,
            labels=sexo_counts.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=["#8ecae6", "#219ebc"],
            textprops={"color": "white"}
        )
        ax2.axis("equal")
        st.pyplot(fig2)
    else:
        st.info("No se encontró la columna 'sexo'.")


    # --- función utilitaria para normalizar valores binarios a "Sí"/"No" ---
    def binario_a_si_no(serie):
        # Convertir a string, limpiar espacios y bajar a minúsculas
        s = serie.astype(str).str.strip().str.lower().fillna("")
        # Mapeo amplio: reconoce 1, "1", "true", "t", "si", "sí", "yes" como Sí
        si_vals = {"1", "true", "t", "si", "sí", "yes", "y"}
        no_vals = {"0", "false", "f", "no", "n", ""}
        # Aplicar mapeo
        mapped = s.map(lambda v: "Sí" if v in si_vals else ("No" if v in no_vals else "No"))
        # Finalmente, contar
        return mapped


    # --- ACCESO A INTERNET (Pie Chart) ---
    st.subheader("Usuarios con acceso a internet")
    if "internet" in usuarios_df.columns:
        # normalizar y contar
        acceso_normal = binario_a_si_no(usuarios_df["internet"])
        acceso_df = acceso_normal.value_counts().reindex(["Sí", "No"]).fillna(0)
        fig3, ax3 = plt.subplots(facecolor="#0E1117")
        ax3.set_facecolor("#0E1117")
        ax3.pie(
            acceso_df,
            labels=acceso_df.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=["#ffb703", "#fb8500"],
            textprops={"color": "white"}
        )
        ax3.axis("equal")
        st.pyplot(fig3)
    else:
        st.info("No se encontró la columna 'internet'.")

    # --- DISPOSITIVO PROPIO (Pie Chart) ---
    st.subheader("Usuarios con dispositivo propio")
    if "dispositivo" in usuarios_df.columns:
        disp_normal = binario_a_si_no(usuarios_df["dispositivo"])
        disp_df = disp_normal.value_counts().reindex(["Sí", "No"]).fillna(0)
        fig4, ax4 = plt.subplots(facecolor="#0E1117")
        ax4.set_facecolor("#0E1117")
        ax4.pie(
            disp_df,
            labels=disp_df.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=["#adb5bd", "#2a9d8f"],
            textprops={"color": "white"}
        )
        ax4.axis("equal")
        st.pyplot(fig4)
    else:
        st.info("No se encontró la columna 'dispositivo'.")

    # --- REGISTROS POR FECHA ---
    st.subheader("Usuarios registrados por fecha")
    if "fecha_registro" in usuarios_df.columns:
        try:
            usuarios_df["fecha_registro"] = pd.to_datetime(usuarios_df["fecha_registro"], errors="coerce")
            registros_por_fecha = usuarios_df["fecha_registro"].dt.date.value_counts().sort_index()
            st.line_chart(registros_por_fecha)
        except Exception as e:
            st.info(f"No se pudo procesar la fecha de registro: {e}")
    else:
        st.info("No se encontró la columna 'fecha_registro'.")

    # --- VISTA GENERAL DE USUARIOS ---
    st.subheader("Vista general de usuarios")
    if all(col in usuarios_df.columns for col in ["nombre", "apellidos", "ocupacion", "edad"]):
        vista = usuarios_df[["nombre", "apellidos", "ocupacion", "edad"]].sort_values("edad")
        st.dataframe(vista)

# ---------------------------
# Fin
# ---------------------------
