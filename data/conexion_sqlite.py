# data/conexion_sqlite.py

import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime


class ConexionSQLite:
    """
    Clase para manejar la conexión y operaciones CRUD con SQLite.
    Optimizada para Streamlit usando st.cache_resource y st.cache_data.
    """

    def __init__(self, db_name: str = r"db/libreria.db"):
        """
        Inicializa la clase con el nombre del archivo de la base de datos.

        Args:
            db_name (str): El nombre del archivo .db (ej. "mi_proyecto.db").
        """
        self.db_name = db_name

    @st.cache_resource
    def _get_connection(_self):
        """
        Método interno para crear y cachear la conexión a la DB.

        Usa @_self en lugar de @self por una particularidad de 
        cómo st.cache_resource maneja los métodos de clase.

        Returns:
            sqlite3.Connection: El objeto de conexión a la base de datos.
        """
        print(f"[{datetime.now()}] 🔑 Creando nueva conexión cacheada a: {_self.db_name}")
        try:
            # check_same_thread=False es necesario para SQLite en Streamlit
            conn = sqlite3.connect(_self.db_name, check_same_thread=False)
            return conn
        except sqlite3.Error as e:
            st.error(f"Error fatal al conectar con SQLite: {e}")
            return None

    # --- C: CREATE  ---
    def insertar_registro(self, table_name: str, data: dict) -> bool:
        """
        [CREATE] Inserta un único registro (fila) en una tabla.

        Args:
            table_name (str): Nombre de la tabla (ej. 'usuarios').
            data (dict): {'columna': valor, ...}

        Returns:
            bool: True si fue exitoso, False si falló.
        """
        conn = self._get_connection()
        if conn is None: return False

        try:
            columnas = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            query = f"INSERT INTO {table_name} ({columnas}) VALUES ({placeholders})"

            print(f"[{datetime.now()}] 💾 Ejecutando INSERCIÓN en DB: Tabla '{table_name}'")

            cursor = conn.cursor()
            cursor.execute(query, list(data.values()))
            conn.commit()

            print(f"  > ¡Éxito! Nuevo registro insertado en '{table_name}'.")
            self.cargar_tabla_df.clear()  # Limpiar caché de lectura
            return True

        except Exception as e:
            print(f"  > ¡ERROR! Revertiendo transacción (rollback) para '{table_name}'.")
            conn.rollback()
            print(f"Error al insertar registro en {table_name}: {e}")
            return False

    # --- U: UPDATE (Actualizar) ---

    def actualizar_registros(self, table_name: str, data: dict, where_clause: str, where_args: tuple) -> bool:
        """
        [UPDATE] Actualiza una o más filas que coincidan con una condición.

        Args:
            table_name (str): Nombre de la tabla (ej. 'recursos').
            data (dict): Los datos a cambiar (ej. {'estado': 'asignado'})
            where_clause (str): La condición SQL (ej. "id IN (?, ?, ?)")
            where_args (tuple): Los valores para la condición WHERE (ej. (101, 102, 103))

        Returns:
            bool: True si fue exitoso, False si falló.
        """
        conn = self._get_connection()
        if conn is None: return False

        try:
            # Construye la parte SET de la consulta: "estado = ?, tipo = ?"
            set_clause = ', '.join([f"{key} = ?" for key in data.keys()])

            query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"

            print(query)
            valores = list(data.values()) + list(where_args)

            print(f"[{datetime.now()}] 💾 Ejecutando ACTUALIZACIÓN en DB: Tabla '{table_name}'")

            cursor = conn.cursor()
            cursor.execute(query, valores)
            conn.commit()

            print(f"  > ¡Éxito! {cursor.rowcount} registros actualizados en '{table_name}'.")
            self.cargar_tabla_df.clear()  # Limpiar caché
            return True

        except Exception as e:
            print(f"  > ¡ERROR! Revertiendo transacción (rollback) para '{table_name}'.")
            conn.rollback()
            print(f"Error al actualizar registros en {table_name}: {e}")
            return False

    # --- R: read  ---
    @st.cache_data(ttl=3600)  # Cachea los datos por 1 hora
    def cargar_tabla_df(_self, table_name: str) -> pd.DataFrame:
        """
        Carga una tabla completa de la DB en un DataFrame de Pandas.
        Esta función está CACHEADA: Solo se re-ejecuta si la DB cambia
        (o si el cache expira).

        Args:
            table_name (str): Nombre de la tabla (ej. 'usuarios').

        Returns:
            pd.DataFrame: Un DataFrame con los datos, o uno vacío si falla.
        """
        print(f"[{datetime.now()}] 🔄 Ejecutando LECTURA de DB: 'SELECT * FROM {table_name}'")
        conn = _self._get_connection()
        if conn is None:
            return pd.DataFrame()

        try:
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql_query(query, conn)
            return df
        except pd.errors.DatabaseError as e:
            st.warning(f"No se pudo cargar la tabla {table_name}: {e}. ¿Existe?")
            return pd.DataFrame()

    # --- D: DELETE (Borrar) ---
    def eliminar_registros(self, table_name: str, where_clause: str, where_args: tuple) -> bool:
        """
        [DELETE] Elimina una o más filas que coincidan con una condición.

        Args:
            table_name (str): Nombre de la tabla.
            where_clause (str): La condición SQL (ej. "id_usuario = ?")
            where_args (tuple): Los valores para la condición (ej. (101,))

        Returns:
            bool: True si fue exitoso, False si falló.
        """
        conn = self._get_connection()
        if conn is None: return False

        try:
            query = f"DELETE FROM {table_name} WHERE {where_clause}"

            print(f"[{datetime.now()}] 💾 Ejecutando ELIMINACIÓN en DB: Tabla '{table_name}'")

            cursor = conn.cursor()
            cursor.execute(query, where_args)
            conn.commit()

            print(f"  > ¡Éxito! {cursor.rowcount} registros eliminados de '{table_name}'.")
            self.cargar_tabla_df.clear()  # Limpiar caché
            return True

        except Exception as e:
            print(f"  > ¡ERROR! Revertiendo transacción (rollback) para '{table_name}'.")
            conn.rollback()
            print(f"Error al eliminar registros en {table_name}: {e}")
            return False

    def insertar_dataframe(self, df: pd.DataFrame, table_name: str) -> bool:
        """
        [CREATE-BULK] Inserta un DataFrame completo en una tabla.
        Usa 'append' para AÑADIR los registros, no reemplazar.

        Args:
            df (pd.DataFrame): El DataFrame con las nuevas filas.
            table_name (str): Nombre de la tabla (ej. 'asignaciones').

        Returns:
            bool: True si fue exitoso, False si falló.
        """
        conn = self._get_connection()
        if conn is None: return False

        try:
            print(f"[{datetime.now()}] 💾 Ejecutando INSERCIÓN MASIVA en DB: Tabla '{table_name}'")
            df.to_sql(
                name=table_name,
                con=conn,
                if_exists='append',  # ¡La clave! Añade las filas al final.
                index=False  # No guardar el índice de Pandas
            )

            # Forzar la confirmación de la transacción
            conn.commit()
            print(f"  > ¡Éxito! {len(df)} nuevos registros insertados en '{table_name}'.")

            # Limpiar la caché de lectura para Streamlit
            self.cargar_tabla_df.clear()

            return True

        except Exception as e:
            # Revertir si algo sale mal
            print(f"  > ¡ERROR! Revertiendo transacción (rollback) para '{table_name}'.")
            conn.rollback()
            print(f"Error al insertar dataframe en {table_name}: {e}")
            return False
