from datetime import datetime

import streamlit as st
import  core.priorizacion
from data.conexion_sqlite import ConexionSQLite
from core.priorizacion import recalcular_puntajes_asignaciones

conexion_activa = ConexionSQLite()


def init_session():


    if "recursos" not in st.session_state:
        st.session_state["recursos"] = conexion_activa.cargar_tabla_df("recursos")
        print(st.session_state["recursos"])

    if "asignaciones" not in st.session_state:
        st.session_state["asignaciones"] = conexion_activa.cargar_tabla_df("asignaciones")
        print(st.session_state["asignaciones"])

    # Inicializa los pesos globales con un valor por defecto
    if "pesos_globales" not in st.session_state:
        st.session_state["pesos_globales"] = {"ocupacion": 4, "acceso_internet": 5, "dispositivo_propio": 4, "edad": 3}

    # Estado temporal para los sliders (solo se usa en modo edición)
    if "temp_pesos" not in st.session_state:
        st.session_state["temp_pesos"] = st.session_state["pesos_globales"].copy()
    if "editando" not in st.session_state:
        st.session_state["editando"] = False
    if "last_saved" not in st.session_state:
        st.session_state["last_saved"] = None

    # inicializar data en session_state para no recargar constantemente
    if "usuarios" not in st.session_state:
        st.session_state["usuarios"] = conexion_activa.cargar_tabla_df("usuarios")
        print(st.session_state["usuarios"])

        if "puntaje" not in st.session_state["usuarios"].columns:
            # 2. Si no existe, créala y asígnale un valor por defecto (ej. 0.0)
            st.session_state["usuarios"]["puntaje"] = 0.0
            print("Columna 'puntaje' virtual añadida a st.session_state['usuarios'].")

    print("Primera carga: Calculando puntajes iniciales...")
    recalcular_puntajes_asignaciones()

# --- FUNCIONES DE MANEJO DE ESTADO ---

def cambiar_estado_edicion():
    st.session_state.editando = not st.session_state.editando

    # Si acabamos de entrar en modo edición, inicializamos los valores temporales
    if st.session_state.editando:
        st.session_state.temp_pesos = st.session_state.pesos_globales.copy()


def guardar_cambios():
    st.session_state.pesos_globales = st.session_state.temp_pesos
    st.session_state.last_saved = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.session_state.editando = False
    core.priorizacion.recalcular_puntajes_asignaciones()


def cancelar_edicion():
    st.session_state.editando = False
