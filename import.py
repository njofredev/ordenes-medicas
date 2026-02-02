import pandas as pd
from sqlalchemy import create_engine

# Configuración
DB_URL = "postgresql://postgres:oIZEFdX4TwqvCqoRurMkEOBjLxXRpwfwNMRzwrTyaH5OhUNINqv9lNqAzmD4fLeV@181.42.232.26:5432/db_ordenes_medicas"

def cargar_datos_csv():
    try:
        # Crear conexión
        engine = create_engine(DB_URL)
        
        # Leer el archivo (usando el separador ';' que identificamos)
        df = pd.read_csv('ordenes-medicas.csv', sep=';')
        
        # Mapear columnas del CSV a las de la DB
        df.columns = ['categoria', 'examen', 'codigo_fonasa']
        
        # Insertar datos en la tabla 'examenes'
        # Usamos index=False para no subir el ID de la fila de pandas
        df.to_sql('examenes', engine, if_exists='append', index=False)
        
        print(f"✅ Éxito: {len(df)} exámenes insertados en 'db_ordenes_medicas'.")
        
    except Exception as e:
        print(f"❌ Error al conectar o cargar datos: {e}")

if __name__ == "__main__":
    cargar_datos_csv()