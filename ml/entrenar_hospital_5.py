import firebirdsql
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import pickle
import warnings
warnings.filterwarnings('ignore')

print("Entrenamiento Modelo - Hospital Regional Honorio Delgado (Arequipa)")

# Configuración
HOSPITAL_ID = 5
HOSPITAL_NOMBRE = "Hospital Regional Honorio Delgado"
MODELO_ARCHIVO = f'ml/modelos/hospital_{HOSPITAL_ID}.pkl'

# Conexión con ruta completa del proyecto
try:
    print("Conectando a BD...")
    conn = firebirdsql.connect(
        host='localhost',
        database='C:/BD_HOSPITAL/BASEH.FDB',
        user='SYSDBA',
        password='masterkey',
        charset='UTF8'
    )
    print("Conexión exitosa")
except Exception as e:
    print(f"Error: {e}")
    exit()

try:
    # Query simplificada
    query = f"""
    SELECT 
        ad.FECHA,
        ad.TOTAL_PACIENTES,
        ad.EMERGENCIA,
        ad.PEDIATRIA,
        ch.CAMAS_UCI_OCUPADAS,
        ch.CAMAS_UCI_TOTALES,
        fe.ES_FESTIVO,
        fe.ES_FIN_SEMANA
    FROM ASISTENCIA_DIARIA ad
    JOIN CAPACIDAD_HOSPITAL ch ON ad.FECHA = ch.FECHA AND ad.ID_HOSPITAL = ch.ID_HOSPITAL
    JOIN FACTORES_EXTERNOS fe ON ad.FECHA = fe.FECHA AND ad.ID_HOSPITAL = fe.ID_HOSPITAL
    WHERE ad.ID_HOSPITAL = {HOSPITAL_ID}
    ORDER BY ad.FECHA
    """
    
    print("Cargando datos...")
    df = pd.read_sql(query, conn)
    print(f"Datos cargados: {len(df)} registros")
    
    # Preparación de datos
    df = df.sort_values('FECHA')
    df['UCI_24H'] = df['CAMAS_UCI_OCUPADAS'].shift(-1)
    df = df.dropna()
    
    print(f"Datos para entrenamiento: {len(df)} registros")
    
    # Features esenciales
    features = [
        'TOTAL_PACIENTES',
        'EMERGENCIA', 
        'PEDIATRIA',
        'CAMAS_UCI_OCUPADAS',
        'CAMAS_UCI_TOTALES',
        'ES_FESTIVO',
        'ES_FIN_SEMANA'
    ]
    
    X = df[features]
    y = df['UCI_24H']
    
    # Entrenamiento
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = xgb.XGBRegressor(n_estimators=80, max_depth=5, random_state=42)
    modelo.fit(X_train, y_train)
    
    # Evaluación
    y_pred = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    
    print(f"Modelo 24h - Error: {mae:.2f} camas")
    print(f"Rango UCI: {y.min():.0f}-{y.max():.0f} camas")
    
    # Guardar en ml/modelos/
    import os
    os.makedirs('ml/modelos', exist_ok=True)
    with open(MODELO_ARCHIVO, 'wb') as f:
        pickle.dump(modelo, f)
    
    print(f"Modelo guardado: {MODELO_ARCHIVO}")
    print(f"✅ {HOSPITAL_NOMBRE} - Entrenamiento completado")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()