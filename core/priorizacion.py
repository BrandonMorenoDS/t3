import datetime

import pandas as pd

import streamlit as st

from data.conexion_sqlite import ConexionSQLite

pesos_internos = {
    "ocupacion": {"estudiante": 10, "docente": 8, "trabajador": 6, "desempleado": 5, "jubilado": 7, "otro": 3},
    "acceso_internet": {0: 1,
                        1: 0}
    ,
    "dispositivo_propio": {0: 1,
                           1: 0}
}


def calcular_puntaje_row(row, pesos_internos, pesos_globales):
    s = 0

    s += pesos_internos["ocupacion"].get(row.get("ocupacion"), 0) * pesos_globales["ocupacion"]

    s += pesos_internos["acceso_internet"].get(int(row.get("acceso_internet", 0)), 0) * pesos_globales[
        "acceso_internet"]

    s += pesos_internos["dispositivo_propio"].get(int(row.get("dispositivo_propio", 0)), 0) * pesos_globales[
        "dispositivo_propio"]

    s += edad_interna(row.get("edad", 0)) * pesos_globales["edad"]

    return s



def recalcular_puntajes_asignaciones():
    """ Calcula los puntajes y lo guarda en la columna puntaje de la sessionState usuarios"""
    usuarios_df = st.session_state["usuarios"]
    print("🔄 Recalculando puntajes...")

    nuevos_puntajes = usuarios_df.apply(
        calcular_puntaje_row,  # La función que se llamará por cada fila
        axis=1,  # ¡Importante! Significa "por fila"

        # --- Argumentos extra que se pasarán a 'calcular_puntaje_row' ---
        pesos_globales=st.session_state["pesos_globales"],
        pesos_internos=pesos_internos
    )

    st.session_state["usuarios"]["puntaje"] = nuevos_puntajes

    print("✅ Recálculo local completado")

def edad_interna(e):
    try:
        e = int(e)
    except:
        return 0
    if e <= 5: return 10
    if e <= 10: return 9
    if e <= 17: return 7
    if e <= 30: return 5
    if e <= 59: return 4
    return 8
