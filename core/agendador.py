import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from data.conexion_sqlite import ConexionSQLite


def calcular_fecha_cita(i, capacidad_diaria, fecha_inicio):
    """Calcula el día de la cita basado en el índice y la capacidad."""
    dia_offset = i // capacidad_diaria
    return (fecha_inicio + timedelta(days=dia_offset)).isoformat()


def agendar_citas_disponibles(conexion: ConexionSQLite, capacidad_diaria: int, fecha_inicio: datetime.date):
    """
    Toma TODOS los recursos disponibles y los asigna a los usuarios
    con mayor prioridad que estén pendientes.

    Esta versión es EFICIENTE: solo escribe en la DB dos veces (1 UPDATE, 1 INSERT).
    """

    # 1. Cargar el estado actual desde la sesión (que viene de la DB)
    recursos_df = st.session_state["recursos"].copy()
    usuarios_df = st.session_state["usuarios"].copy()
    asignaciones_df = st.session_state["asignaciones"].copy()

    # 2. Calcular el LÍMITE (Tu restricción)
    recursos_disponibles = recursos_df[recursos_df["estado"] == "disponible"].reset_index(drop=True)
    stock_real = len(recursos_disponibles)

    if stock_real == 0:
        st.warning("No hay recursos 'disponibles' para agendar.")
        return

    # 3. Encontrar a los usuarios candidatos (pendientes)
    ids_con_cita_activa = set(
        asignaciones_df[asignaciones_df["estado"].isin(["asignado", "entregado"])]
        ["id_usuario"].astype(int).tolist()
    ) if not asignaciones_df.empty else set()

    usuarios_pendientes = usuarios_df[
        ~usuarios_df["id"].astype(int).isin(ids_con_cita_activa)
    ].sort_values(["puntaje", "fecha_registro"], ascending=[False, True]).reset_index(drop=True)

    if usuarios_pendientes.empty:
        st.warning("No hay usuarios pendientes para agendar.")
        return

    # 4. Determinar el lote a procesar
    lote_a_procesar = min(stock_real, len(usuarios_pendientes))
    print(f"Iniciando agendamiento: {lote_a_procesar} citas se crearán.")

    # --- Listas de "borrador" para preparar la escritura en DB ---
    nuevas_asignaciones_list = []  # Para las NUEVAS filas de 'asignaciones'
    recursos_ids_a_actualizar = []  # Para los IDs de 'recursos' que hay que ACTUALIZAR

    # 5. El Bucle de Agendamiento (¡Solo en Memoria!)
    id_asignacion_max = asignaciones_df["id"].max() if not asignaciones_df.empty else 0

    for i in range(lote_a_procesar):
        # Tomar al usuario y al recurso de este "lote"
        usuario_actual = usuarios_pendientes.iloc[i]
        recurso_actual = recursos_disponibles.iloc[i]

        # Calcular la fecha usando tu parámetro de capacidad diaria
        fecha_cita_calculada = calcular_fecha_cita(i, capacidad_diaria, fecha_inicio)

        # --- A. Preparar la actualización del Recurso ---
        # (¡ARREGLO DE BUG 1!)
        # Guardamos el ID del recurso para actualizarlo más tarde
        recursos_ids_a_actualizar.append(int(recurso_actual["id"]))

        # --- B. Preparar la Nueva Asignación ---
        nuevo_dict = {
            "id": id_asignacion_max + 1 + i,
            "id_usuario": int(usuario_actual["id"]),
            "id_recurso": int(recurso_actual["id"]),
            "puntaje": float(usuario_actual["puntaje"]),  # ¡Importante! La foto del puntaje
            "estado": "asignado",
            "fecha_cita": fecha_cita_calculada,
            "creado_ts": datetime.now().isoformat(),
            # ... (tus otros campos)
        }
        nuevas_asignaciones_list.append(nuevo_dict)

        # --- (¡ARREGLO DE BUG 2!) ---
        # ¡HEMOS QUITADO la llamada a conexion.insertar_registro() de aquí!
        # Ya no hablamos con la DB dentro del bucle.

    # 6. Guardar los cambios en la Base de Datos (¡Ahora SÍ!)
    # El bucle terminó. Ahora hacemos las 2 operaciones de DB.

    if not nuevas_asignaciones_list:
        st.warning("No se preparó ninguna asignación nueva.")
        return

    # --- Guardado 1: Actualizar 'recursos' (con UPDATE quirúrgico) ---
    datos_a_actualizar = {"estado": "asignado"}
    placeholders = ', '.join(['?'] * len(recursos_ids_a_actualizar))
    condicion_where = f"id IN ({placeholders})"
    argumentos_where = tuple(recursos_ids_a_actualizar)  # ¡Ahora esta variable SÍ existe!

    exito_recursos = conexion.actualizar_registros(
        "recursos",
        datos_a_actualizar,
        condicion_where,
        argumentos_where
    )

    if not exito_recursos:
        st.error("¡Fallo crítico! No se pudo actualizar el estado de los recursos.")
        return  # Detener si falla el primer guardado

    # --- Guardado 2: Insertar 'asignaciones' (con INSERT masivo) ---
    df_nuevas = pd.DataFrame(nuevas_asignaciones_list)  # Convertimos la lista de dicts en un DataFrame

    exito_asignaciones = conexion.insertar_dataframe(df_nuevas, "asignaciones")

    if not exito_asignaciones:
        st.error("¡Fallo crítico! No se pudieron guardar las nuevas asignaciones.")
        return

    # Si todo salió bien, limpiamos la caché para que Streamlit recargue
    conexion.cargar_tabla_df.clear()

    st.success(f"¡Éxito! Se agendaron {len(df_nuevas)} nuevas citas.")