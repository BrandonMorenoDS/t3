import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# Tus módulos personalizados
import core.priorizacion
import ui.session_manager
import core.agendador
from data.conexion_sqlite import ConexionSQLite

# --- 1. CONFIGURACIÓN Y CARGA INICIAL ---
st.set_page_config(page_title="Gestión Bibliotecaria", layout="wide", page_icon="📚")


# ---------------------------
# Acciones: marcar entregado / ausente
# ---------------------------
def marcar_entregado(id_asig):
    """Actualiza el estado de una asignación a 'entregado' en la DB."""
    datos_a_actualizar = {
        "estado": "entregado",
        "creado_ts": datetime.now().isoformat()
    }
    condicion_where = "id = ?"
    argumentos_where = (id_asig,)

    exito = conexion_activa.actualizar_registros(
        "asignaciones",
        datos_a_actualizar,
        condicion_where,
        argumentos_where
    )
    if exito:
        st.success("Marcado como entregado ✅")
        conexion_activa.cargar_tabla_df.clear()

        # Borrar caché de sesión para forzar recarga
        if "asignaciones" in st.session_state: del st.session_state["asignaciones"]

        st.rerun()
    else:
        st.error("Error al actualizar el estado.")


def marcar_ausente(id_asig):
    """
    Maneja la falta del usuario:
    - 1ra falta: Reprograma para mañana (mueve de Tab).
    - 2da falta: Elimina asignación, libera recurso y BORRA al usuario.
    """
    asign = st.session_state["asignaciones"]

    # Obtener datos actuales de la fila
    fila = asign[asign["id"] == id_asig]
    if fila.empty:
        st.error("Asignación no encontrada")
        return

    # --- CORRECCIÓN DE BUG: Manejo robusto de NULL/NaN ---
    val_intentos = fila.iloc[0]["intentos_fallidos"]

    # Verificamos explícitamente si es nulo usando pd.isna()
    if pd.isna(val_intentos) or val_intentos is None or val_intentos == "":
        intentos_actuales = 0
    else:
        try:
            intentos_actuales = int(val_intentos)
        except ValueError:
            intentos_actuales = 0
    # -----------------------------------------------------

    id_usuario = int(fila.iloc[0]["id_usuario"])
    id_recurso = int(fila.iloc[0]["id_recurso"])
    fecha_actual_str = fila.iloc[0]["fecha_cita"]

    # --- LÓGICA DE STRIKES ---

    if intentos_actuales == 0:
        # === STRIKE 1: REPROGRAMAR ===

        # 1. Calcular fecha siguiente (Mañana)
        try:
            # Intentamos parsear la fecha actual
            fecha_dt = datetime.strptime(fecha_actual_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            # Si falla, usamos hoy como base
            fecha_dt = datetime.now()

        nueva_fecha = (fecha_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        # 2. Preparar actualización
        datos_a_actualizar = {
            "intentos_fallidos": intentos_actuales + 1,
            "estado": "ausente_1",
            "fecha_cita": nueva_fecha,  # <--- ¡ESTO LO MUEVE DE PESTAÑA!
            "creado_ts": datetime.now().isoformat()
        }

        exito = conexion_activa.actualizar_registros(
            "asignaciones",
            datos_a_actualizar,
            "id = ?",
            (id_asig,)
        )

        if exito:
            st.toast(f"Reprogramado para {nueva_fecha} (Falta 1/2).", icon="📅")

    else:
        # === STRIKE 2: ELIMINACIÓN TOTAL ===

        # 1. Liberar el recurso (volver a disponible)
        conexion_activa.actualizar_registros(
            "recursos",
            {"estado": "disponible"},
            "id = ?",
            (id_recurso,)
        )

        # 2. Eliminar la ASIGNACIÓN (borrar registro)
        conexion_activa.eliminar_registros(
            "asignaciones",
            "id = ?",
            (id_asig,)
        )

        # 3. Eliminar al USUARIO (borrar registro para que no vuelva a postular)
        conexion_activa.eliminar_registros(
            "usuarios",
            "id = ?",
            (id_usuario,)
        )

        st.toast("Usuario eliminado del sistema por inasistencias.", icon="🚫")

    # --- LIMPIEZA FINAL ---
    # Forzamos recarga de TODO porque hemos tocado las 3 tablas
    conexion_activa.cargar_tabla_df.clear()

    if "asignaciones" in st.session_state: del st.session_state["asignaciones"]
    if "recursos" in st.session_state: del st.session_state["recursos"]
    if "usuarios" in st.session_state: del st.session_state["usuarios"]

    st.rerun()


# --- CSS BLINDADO ---
st.markdown("""
<style>
    /* Fuente Global */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    }

    /* Fondo de la App */
    .stApp {
        background-color: #dae7ee;
    }

    /* 1. TARJETAS KPI (Métricas Superiores) */
    .metric-card {
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(62, 151, 134, 0.1);
        border-left: 5px solid #3e9786;
        margin-bottom: 15px;
    }
    .metric-title {
        color: #566573;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    .metric-value {
        color: #252727;
        font-size: 28px;
        font-weight: 700;
    }

    /* 2. NUEVA TARJETA FINANCIERA (Estilo Personalizado) */
    .finance-card {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
    }
    .finance-header {
        color: #3e9786;
        font-size: 18px;
        font-weight: 700;
        border-bottom: 2px solid #f0f2f6;
        padding-bottom: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .finance-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        text-align: left;
    }
    .finance-item label {
        display: block;
        font-size: 12px;
        color: #666;
        margin-bottom: 4px;
    }
    .finance-item span {
        font-size: 24px;
        font-weight: 700;
        color: #333;
    }
    .finance-footer {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px dashed #ddd;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .total-price {
        color: #3e9786;
        font-size: 32px;
        font-weight: 800;
    }

    /* 3. CONTENEDORES DE GRÁFICOS (Selector Comodín) */
    /* Usamos [class*="..."] para atrapar cualquier variante del borde */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important; 
        border-radius: 15px !important;
        padding: 15px !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }

    /* Títulos de gráficos */
    h5 {
        color: #566573;
        font-weight: 600;
        margin-top: 0;
        margin-bottom: 15px;
        text-align: center;
    }

    /* Limpieza */
    div[data-testid="column"] { background-color: transparent !important; }
</style>
""", unsafe_allow_html=True)

ui.session_manager.init_session()
conexion_activa = ConexionSQLite()


# --- 2. COMPONENTES HTML PERSONALIZADOS ---

def crear_tarjeta_kpi(titulo, valor):
    return f"""
    <div class="metric-card">
        <div class="metric-title">{titulo}</div>
        <div class="metric-value">{valor}</div>
    </div>
    """


# ¡ESTE ES EL NUEVO COMPONENTE PARA EL PRESUPUESTO!
def crear_tarjeta_financiera(demanda, stock, deficit, costo_unit, costo_total):
    return f"""
    <div class="finance-card">
        <div class="finance-header">
             Proyección Financiera
        </div>
        <div class="finance-grid">
            <div class="finance-item">
                <label>Demanda Real (Usuarios)</label>
                <span>{demanda}</span>
            </div>
            <div class="finance-item">
                <label>Stock Actual (Dispositivos)</label>
                <span>{stock}</span>
            </div>
            <div class="finance-item">
                <label>Déficit de Recursos</label>
                <span style="color: #e76f51;">{deficit}</span>
            </div>
        </div>
        <div class="finance-footer">
            <div>
                <div style="font-size: 12px; color: #666;">Costo Promedio por Unidad</div>
                <div style="font-size: 18px; font-weight: 600;">S/ {costo_unit:,.2f}</div>
            </div>
            <div>
                <div style="font-size: 12px; color: #666; text-align: right;">Presupuesto Total Requerido</div>
                <div class="total-price">S/ {costo_total:,.2f}</div>
            </div>
        </div>
    </div>
    """


def binario_a_si_no_local(serie):
    s = serie.astype(str).str.strip().str.lower().fillna("")
    si_vals = {"1", "true", "t", "si", "sí", "yes", "y"}
    return s.map(lambda v: "Sí" if v in si_vals else "No")


# Estilo Gráfico: Fondo blanco explícito
def estilo_grafico(fig):
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"color": "#252727"},
        margin=dict(l=20, r=20, t=10, b=50),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#f0f2f6'),
    )
    return fig


# --- 3. NAVEGACIÓN ---
def navegar_a(pagina):
    st.session_state.pagina_actual = pagina
    st.session_state.editando = False


st.sidebar.markdown("<h2 style='text-align: center; color: #252727;'>Menú</h2>", unsafe_allow_html=True)
st.sidebar.button(" Dashboard", on_click=navegar_a, args=("Dashboard",), use_container_width=True)
st.sidebar.button(" Registrar Usuario", on_click=navegar_a, args=("Registrar usuario",), use_container_width=True)
st.sidebar.markdown("---")


# ==========================================
# PÁGINA: REGISTRAR USUARIO
# ==========================================
if st.session_state.pagina_actual == "Registrar usuario":
    st.title(" Registro de Nuevo Usuario")
    with st.container(border=True):
        st.markdown("#### Formulario de Ingreso")
        with st.form("form_registrar", border=False):
            col1, col2 = st.columns(2)
            with col1:
                st.caption("Datos Personales")
                nombre = st.text_input("Nombres")
                apellidos = st.text_input("Apellidos")
                edad = st.number_input("Edad", min_value=0, max_value=120, value=18)
                sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
                direccion = st.text_input("Dirección")
            with col2:
                st.caption("Perfil Socioeconómico")
                ocupacion = st.selectbox("Ocupación", ["Estudiante", "Empleado", "Jubilado", "Desempleado", "Otro"])
                telefono = st.text_input("Teléfono")
                correo_electronico = st.text_input("Correo electrónico")
                c_int, c_disp = st.columns(2)
                with c_int:
                    acceso_internet = st.selectbox("¿Tiene Internet?", [0, 1],
                                                   format_func=lambda x: "No" if x == 0 else "Sí")
                with c_disp:
                    dispositivo_propio = st.selectbox("¿Tiene Dispositivo?", [0, 1],
                                                      format_func=lambda x: "No" if x == 0 else "Sí")
            st.markdown("---")
            registrar = st.form_submit_button(" Guardar Ficha", type="primary", use_container_width=True)
            if registrar:
                # ... (Tu lógica de guardado se mantiene igual)
                usuarios = st.session_state["usuarios"]
                new_id = int(usuarios["id"].max()) + 1 if not usuarios.empty else 1
                nuevo = {
                    "id": new_id, "nombre": nombre, "apellidos": apellidos, "edad": edad,
                    "sexo": sexo, "direccion": direccion, "telefono": telefono,
                    "correo_electronico": correo_electronico, "ocupacion": ocupacion,
                    "internet": acceso_internet, "dispositivo": dispositivo_propio,
                    "fecha_registro": datetime.now().date().isoformat(),
                    "puntaje": 0.0
                }
                usuarios = pd.concat([usuarios, pd.DataFrame([nuevo])], ignore_index=True)
                st.session_state["usuarios"] = usuarios
                conexion_activa.insertar_registro("usuarios", nuevo)
                core.priorizacion.recalcular_puntajes_asignaciones()
                st.success(f" Ficha creada.")

# ==========================================
# PÁGINA: DASHBOARD
# ==========================================
elif st.session_state.pagina_actual == "Dashboard":
    st.title(" Torre de Control")

    # --- KPI CARDS ---
    usuarios_df = st.session_state["usuarios"]
    asignaciones_df = st.session_state["asignaciones"]
    recursos_df = st.session_state["recursos"]

    total_usuarios = len(usuarios_df)
    total_recursos = len(recursos_df)
    disponibles = len(recursos_df[recursos_df["estado"] == "disponible"])
    asignados = len(asignaciones_df[asignaciones_df["estado"] == "asignado"]) if not asignaciones_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(crear_tarjeta_kpi(" Usuarios", total_usuarios), unsafe_allow_html=True)
    with c2:
        st.markdown(crear_tarjeta_kpi(" Recursos", total_recursos), unsafe_allow_html=True)
    with c3:
        st.markdown(crear_tarjeta_kpi(" Disponibles", disponibles), unsafe_allow_html=True)
    with c4:
        st.markdown(crear_tarjeta_kpi(" Asignados Hoy", asignados), unsafe_allow_html=True)

    st.markdown("---")
    tab_gestion, tab_analitica = st.tabs([" Gestión Operativa", " Estadísticas e Insights"])

    with tab_gestion:
        col_izq, col_der = st.columns([2, 1])
        with col_izq:
            with st.container(border=True):
                st.subheader("Ranking (pendientes)")

                # Forzar recarga si acabamos de asignar (doble seguridad)
                df_asig = st.session_state["asignaciones"]
                ids_excluir = set()

                if not df_asig.empty:
                    # Aseguramos que la columna id_usuario sea ENTERO
                    # errors='coerce' convierte basura en NaN, fillna(0) lo hace 0, astype(int) lo hace entero
                    df_asig_clean = df_asig.copy()
                    df_asig_clean["id_usuario"] = pd.to_numeric(df_asig_clean["id_usuario"], errors='coerce').fillna(
                        0).astype(int)

                    ids_excluir = set(
                        df_asig_clean[df_asig_clean["estado"].isin(["asignado", "entregado"])]["id_usuario"]
                    )

                # Filtrar
                df_usuarios = st.session_state["usuarios"]
                # Aseguramos que el ID de usuario también sea entero para comparar peras con peras
                usuarios_pendientes_visual = df_usuarios[~df_usuarios["id"].astype(int).isin(ids_excluir)]

                # 3. Ordenar y mostrar
                if not usuarios_pendientes_visual.empty:
                    usuarios_ord = usuarios_pendientes_visual.sort_values(
                        ["puntaje", "fecha_registro"],
                        ascending=[False, True]
                    ).reset_index(drop=True)

                    st.dataframe(usuarios_ord[["id", "nombre", "ocupacion", "puntaje"]], use_container_width=True)
                else:
                    st.info("¡No hay usuarios pendientes en la cola!")

                # --- FIN DEL FILTRO ---
            st.subheader("Gestión de Asignaciones (Por Fecha)")

            asign = st.session_state["asignaciones"]

            if not asign.empty:
                # 1. Separar ACTIVAS vs HISTORIAL
                # Activas: 'asignado', 'ausente_1'
                # Historial: 'entregado', 'eliminado'
                asign_activas = asign[asign["estado"].isin(["asignado", "ausente_1"])].copy()
                asign_historial = asign[asign["estado"].isin(["entregado", "eliminado"])].copy()

                # --- SECCIÓN DE PESTAÑAS (Solo para activas) ---
                if not asign_activas.empty:
                    # Asegurar orden
                    asign_activas = asign_activas.sort_values("fecha_cita")
                    fechas_unicas = asign_activas["fecha_cita"].unique()
                    fechas_unicas = sorted([f for f in fechas_unicas if f is not None])

                    if len(fechas_unicas) > 0:
                        # Crear pestañas dinámicas
                        tabs = st.tabs([f"📅 {f}" for f in fechas_unicas])

                        for i, fecha in enumerate(fechas_unicas):
                            with tabs[i]:
                                asign_dia = asign_activas[asign_activas["fecha_cita"] == fecha]

                                for index, row in asign_dia.iterrows():
                                    estado_actual = row['estado']
                                    icono = "🔹" if estado_actual == "asignado" else "⚠️"  # ausente_1

                                    with st.expander(
                                            f"{icono} Cita #{row['id']} - Usuario {row['id_usuario']} ({estado_actual})"):
                                        col_info, col_btns = st.columns([2, 1])
                                        with col_info:
                                            st.write(f"**Recurso ID:** {row['id_recurso']}")
                                            st.write(f"**Puntaje:** {row.get('puntaje_snapshot', 'N/A')}")
                                        with col_btns:
                                            # Aquí solo mostramos botones de acción porque SON activas
                                            if st.button("✅ Entregado", key=f"ent_{row['id']}",
                                                         use_container_width=True):
                                                marcar_entregado(row['id'])
                                            if st.button("🚫 Falta", key=f"aus_{row['id']}", use_container_width=True):
                                                marcar_ausente(row['id'])
                    else:
                        st.info("Hay asignaciones activas pero sin fecha válida.")
                else:
                    st.info("¡Todo al día! No hay citas pendientes de atención.")

        with col_der:
            with st.expander("⚙ Criterios", expanded=st.session_state.editando):
                # ... (Tus controles de sliders)
                pesos_ctrl = st.session_state["temp_pesos"]
                disabled = not st.session_state.editando

                # --- CORRECCIÓN: Asignar el valor de retorno al diccionario ---

                pesos_ctrl["ocupacion"] = st.slider(
                    "Ocupación", 1, 10,
                    key="s_ocup",
                    value=pesos_ctrl["ocupacion"],
                    disabled=disabled
                )

                pesos_ctrl["edad"] = st.slider(
                    "Edad", 1, 10,
                    key="s_edad",
                    value=pesos_ctrl["edad"],
                    disabled=disabled
                )

                pesos_ctrl["acceso_internet"] = st.slider(
                    "Internet", 1, 10,
                    key="s_net",
                    value=pesos_ctrl["acceso_internet"],
                    disabled=disabled
                )

                pesos_ctrl["dispositivo_propio"] = st.slider(
                    "Dispositivo", 1, 10,
                    key="s_dev",
                    value=pesos_ctrl["dispositivo_propio"],
                    disabled=disabled
                )
                # ... (Logica de guardar pesos) ...
                if st.session_state.editando:
                    st.button("Guardar", on_click=ui.session_manager.guardar_cambios)
                else:
                    st.button("Editar", on_click=ui.session_manager.cambiar_estado_edicion)

            with st.container(border=True):
                st.markdown("####  Ejecutar")
                capacidad = st.number_input("Cupos", min_value=1, value=5)
                fecha_inicio = st.date_input("Fecha", value=datetime.now().date())

                if st.button(" Asignar", type="primary", use_container_width=True):
                    core.agendador.agendar_citas_disponibles(conexion_activa, capacidad, fecha_inicio)

                    # --- AGREGAR ESTO PARA FORZAR RECARGA ---
                    # Borramos las llaves viejas de la memoria
                    if "asignaciones" in st.session_state: del st.session_state["asignaciones"]
                    if "recursos" in st.session_state: del st.session_state["recursos"]
                    # ----------------------------------------

                    st.rerun()

    with tab_analitica:
        if usuarios_df.empty:
            st.warning("Sin datos.")
        else:
            # --- 1. TARJETA FINANCIERA (HTML PURO - FONDO BLANCO GARANTIZADO) ---
            # Calculamos los datos aquí mismo para pasarlos al componente
            # Supuesto: Demand = Total usuarios - Asignados (aproximado para el ejemplo)
            demanda_real = len(usuarios_df) - len(asignaciones_df[asignaciones_df['estado'] == 'asignado'])
            if demanda_real < 0: demanda_real = 0

            stock_actual = len(recursos_df[recursos_df['estado'] == 'disponible'])
            deficit = max(0, demanda_real - stock_actual)
            costo_unitario = 960.00
            presupuesto_total = deficit * costo_unitario

            # Renderizamos el componente HTML puro (Este SI o SI será blanco)
            st.markdown(
                crear_tarjeta_financiera(demanda_real, stock_actual, deficit, costo_unitario, presupuesto_total),
                unsafe_allow_html=True)

            # --- 2. GRÁFICOS (Dentro de contenedores con borde) ---
            g1, g2 = st.columns(2)

            with g1:
                with st.container(border=True):
                    st.markdown("<h5>Distribución de Puntajes</h5>", unsafe_allow_html=True)
                    if "puntaje" in usuarios_df.columns:
                        fig = px.histogram(usuarios_df, x="puntaje", nbins=15, color_discrete_sequence=["#3e9786"])
                        fig = estilo_grafico(fig)
                        st.plotly_chart(fig, use_container_width=True, theme=None)

            with g2:
                with st.container(border=True):
                    st.markdown("<h5>Distribución de Edades</h5>", unsafe_allow_html=True)
                    if "edad" in usuarios_df.columns:
                        fig = px.histogram(usuarios_df, x="edad", nbins=10, color_discrete_sequence=["#264653"])
                        fig = estilo_grafico(fig)
                        st.plotly_chart(fig, use_container_width=True, theme=None)

            if "ocupacion" in usuarios_df.columns:
                with st.container(border=True):
                    st.markdown("<h5>Ocupaciones Registradas</h5>", unsafe_allow_html=True)
                    conteo = usuarios_df["ocupacion"].value_counts().reset_index()
                    conteo.columns = ["Ocupación", "Cantidad"]
                    fig = px.bar(conteo, x="Ocupación", y="Cantidad", color="Cantidad", color_continuous_scale="Teal")
                    fig = estilo_grafico(fig)
                    fig.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
                    st.plotly_chart(fig, use_container_width=True, theme=None)

            # --- 3. PIE CHARTS ---
            p1, p2, p3 = st.columns(3)


            def plot_pie_wrapper(col, titulo, datos, colores):
                with col:
                    with st.container(border=True):
                        st.markdown(f"<h5>{titulo}</h5>", unsafe_allow_html=True)
                        fig = px.pie(values=datos.values, names=datos.index, color_discrete_sequence=colores, hole=0.4)
                        fig = estilo_grafico(fig)
                        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig, use_container_width=True, theme=None)


            if "sexo" in usuarios_df.columns:
                plot_pie_wrapper(p1, "Sexo", usuarios_df["sexo"].value_counts(), ["#3e9786", "#e9c46a"])

            if "internet" in usuarios_df.columns:
                datos = binario_a_si_no_local(usuarios_df["internet"]).value_counts()
                plot_pie_wrapper(p2, "Internet", datos, ["#264653", "#babbbd"])

            if "dispositivo" in usuarios_df.columns:
                datos = binario_a_si_no_local(usuarios_df["dispositivo"]).value_counts()
                plot_pie_wrapper(p3, "Dispositivo", datos, ["#e76f51", "#babbbd"])