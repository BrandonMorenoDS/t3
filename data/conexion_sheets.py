# data/conexion_sheets.py
import gspread
import pandas as pd


class ConexionSheets:
    """
    Clase para manejar la conexión y lectura de datos desde Google Sheets.
    """

    def __init__(self, creds_json, spreadsheet_name):

        self.creds_json = creds_json
        self.spreadsheet_name = spreadsheet_name
        self.client = None
        self.spreadsheet = None

    def connect(self):

        if self.spreadsheet is None:
            self.client = gspread.service_account(filename=self.creds_json)
            self.spreadsheet = self.client.open(self.spreadsheet_name)
        return self.spreadsheet

    def get_worksheet_df(self, sheet_name):

        ASSIGNACIONES_COLUMNS = [
            'id_usuario',
            'id_recurso',
            'puntaje',
            'estado',
            'fecha_cita',
            'intentos_fallidos'
        ]

        spreadsheet = self.connect()
        worksheet = spreadsheet.worksheet(sheet_name)

        # Obtiene el DataFrame (será Empty DataFrame, Columns: [] si está vacía)
        df = pd.DataFrame(worksheet.get_all_records())

        # Lógica de verificación para hojas vacías
        if df.empty and not df.columns.any() and sheet_name == "Asignaciones":
            print(f"⚠️ Aviso: La hoja '{sheet_name}' está vacía. Creando estructura de columnas.")
            # Crea un DataFrame vacío con las columnas predefinidas
            df = pd.DataFrame(columns=ASSIGNACIONES_COLUMNS)

        return df

    def load_data(self, sheet_names):

        spreadsheet = self.connect()
        data = {sheet: self.get_worksheet_df(sheet) for sheet in sheet_names}
        return data

    def save_or_update(self, sheet_name: str, row: list):

        if not row:
            print("Error: La fila de datos está vacía.")
            return

        spreadsheet = self.connect()
        worksheet = spreadsheet.worksheet(sheet_name)

        # Definir la clave de búsqueda (user_id)
        search_key_value = str(row[0])

        # Buscar la celda: worksheet.find() devuelve un objeto Cell si encuentra, o lanza una excepción si no
        # la forma más robusta es intentar buscar, pero si lanza una excepción (la que sea, ya que la anterior falla)
        # asumir que no existe. Sin embargo, gspread.find lanza CellNotFound al no encontrar.



        cell = None
        try:
            # Intentamos encontrar la celda con el user_id en la Columna 1 ('A')
            cell = worksheet.find(search_key_value, in_column=1)
        except Exception as e:
            # Capturamos la excepción

            pass

        if cell is not None:
            # Caso 1:
            row_to_update_index = cell.row

            # Ejecutar la actualización
            range_to_update = f'A{row_to_update_index}'
            worksheet.update(range_to_update, [row], value_input_option='USER_ENTERED')
            print(
                f"✅ Fila actualizada en '{sheet_name}' para user_id = '{search_key_value}' (Fila {row_to_update_index}).")

        else:

            worksheet.append_row(row, value_input_option='USER_ENTERED')
            print(f"✅ Nueva fila insertada en '{sheet_name}' para user_id = '{search_key_value}'.")

