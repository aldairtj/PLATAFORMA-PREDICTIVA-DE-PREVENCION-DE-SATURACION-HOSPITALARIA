from flask import Flask, render_template, request, redirect, url_for, session, flash
import firebirdsql
import os
import pickle
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_temporal_para_prototipo'

# Configuración de la base de datos - CODIFICACIÓN CORREGIDA
def get_db_connection():
    try:
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_bd = os.path.join(directorio_actual, 'data', 'BASEH.fdb')
        
        print(f"🔍 Buscando BD en: {ruta_bd}")
        
        if not os.path.exists(ruta_bd):
            print("❌ ERROR: El archivo BASEH.FDB no existe")
            return None
            
        conn = firebirdsql.connect(
            host='localhost',
            database=ruta_bd,
            user='SYSDBA', 
            password='masterkey',
            charset='ISO8859_1'
        )
        print("✅ Conexión a BD exitosa")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a BD: {e}")
        return None

# Cargar modelo ML
def cargar_modelo_ml(hospital_id):
    try:
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        modelo_path = os.path.join(directorio_actual, 'ml', 'modelos', f'hospital_{hospital_id}.pkl')
        
        if not os.path.exists(modelo_path):
            print(f"❌ Modelo no encontrado: {modelo_path}")
            return None
            
        with open(modelo_path, 'rb') as f:
            modelo = pickle.load(f)
        print(f"✅ Modelo ML cargado para hospital {hospital_id}")
        return modelo
    except Exception as e:
        print(f"❌ Error cargando modelo ML: {e}")
        return None

# Obtener métricas REALES desde BD
def obtener_metricas_reales(hospital_id):
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo conectar a BD para métricas")
        return None
        
    try:
        cur = conn.cursor()
        
        # Obtener datos MÁS RECIENTES
        cur.execute("""
            SELECT 
                ch.CAMAS_UCI_OCUPADAS,
                ch.CAMAS_UCI_TOTALES,
                ch.CAMAS_EMERGENCIA_OCUPADAS,
                ch.PACIENTES_ESPERA,
                ad.TOTAL_PACIENTES
            FROM CAPACIDAD_HOSPITAL ch
            JOIN ASISTENCIA_DIARIA ad ON ch.FECHA = ad.FECHA AND ch.ID_HOSPITAL = ad.ID_HOSPITAL
            WHERE ch.ID_HOSPITAL = ?
            ORDER BY ch.FECHA DESC
            ROWS 1
        """, (hospital_id,))
        
        datos = cur.fetchone()
        
        if not datos:
            print("❌ No se encontraron datos para el hospital")
            return None
            
        print(f"📊 Datos BD obtenidos: UCI={datos[0]}/{datos[1]}, Espera={datos[3]}, Total={datos[4]}")
        
        # Calcular porcentajes
        ocupacion_uci = round((datos[0] / datos[1]) * 100) if datos[1] > 0 else 0
        pacientes_urgencias = datos[3]
        total_pacientes = datos[4]
        
        # Obtener evolución semanal (últimos 5 días)
        cur.execute("""
            SELECT CAMAS_UCI_OCUPADAS 
            FROM CAPACIDAD_HOSPITAL 
            WHERE ID_HOSPITAL = ? 
            ORDER BY FECHA DESC 
            ROWS 5
        """, (hospital_id,))
        
        evolucion_data = [fila[0] for fila in cur.fetchall()]
        # Rellenar si no hay suficientes datos
        while len(evolucion_data) < 5:
            evolucion_data.append(evolucion_data[-1] if evolucion_data else datos[0])
            
        evolucion_semanal = [round((camas / datos[1]) * 100) if datos[1] > 0 else 0 for camas in evolucion_data]
        
        # Generar predicción con ML
        modelo = cargar_modelo_ml(hospital_id)
        prediccion_24h = 0
        
        if modelo:
            try:
                # Preparar datos para predicción
                datos_prediccion = [
                    total_pacientes,      # TOTAL_PACIENTES
                    datos[2],             # EMERGENCIA
                    25,                   # PEDIATRIA (valor ejemplo)
                    datos[0],             # CAMAS_UCI_OCUPADAS
                    datos[1],             # CAMAS_UCI_TOTALES
                    0,                    # ES_FESTIVO
                    1 if datetime.now().weekday() >= 5 else 0  # ES_FIN_SEMANA
                ]
                
                prediccion = modelo.predict([datos_prediccion])
                prediccion_24h = min(100, max(0, round(prediccion[0])))
                print(f"🤖 Predicción ML: {prediccion_24h}%")
                
            except Exception as e:
                print(f"❌ Error en predicción ML: {e}")
                prediccion_24h = min(100, ocupacion_uci + 5)
        else:
            prediccion_24h = min(100, ocupacion_uci + 8)
        
        metricas = {
            'ocupacion_uci': ocupacion_uci,
            'pacientes_urgencias': pacientes_urgencias,
            'insumos_criticos': max(70, 100 - ocupacion_uci),
            'prediccion_24h': prediccion_24h,
            'evolucion_semanal': evolucion_semanal,
            'ocupacion_areas': [ocupacion_uci, 65, 58]  # UCI, Urgencias, Hospitalización
        }
        
        print(f"📈 Métricas calculadas: UCI={ocupacion_uci}%, Predicción={prediccion_24h}%")
        return metricas
        
    except Exception as e:
        print(f"❌ Error obteniendo métricas: {e}")
        return None
    finally:
        conn.close()

# Middleware para verificar login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta de login
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_hospital = request.form.get('id_hospital')
        password = request.form.get('password')
        
        print(f"🔐 Intento de login: ID={id_hospital}")
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                
                cur.execute(
                    "SELECT ID_HOSPITAL FROM HOSPITALES WHERE ID_HOSPITAL = ? AND PASSWORD = ?", 
                    (id_hospital, password)
                )
                resultado = cur.fetchone()
                
                if resultado:
                    hospital_id = resultado[0]
                    
                    # Obtener nombre del hospital
                    hospital_nombre = f"Hospital {hospital_id}"
                    try:
                        cur.execute("SELECT NOMBRE_HOSPITAL FROM HOSPITALES WHERE ID_HOSPITAL = ?", (hospital_id,))
                        nombre_result = cur.fetchone()
                        if nombre_result:
                            hospital_nombre = nombre_result[0]
                    except Exception as nombre_error:
                        print(f"⚠️  Error obteniendo nombre: {nombre_error}")
                    
                    session['hospital_id'] = hospital_id
                    session['hospital_nombre'] = hospital_nombre
                    session['logged_in'] = True
                    conn.close()
                    print(f"✅ Login exitoso: {hospital_nombre}")
                    return redirect(url_for('dashboard'))
                else:
                    flash('ID de hospital o contraseña incorrectos', 'error')
                    print("❌ Login fallido: credenciales incorrectas")
                    
            except Exception as e:
                flash('Error en el sistema de autenticación', 'error')
                print(f"❌ Error en login: {e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
        else:
            flash('Error conectando a la base de datos', 'error')
            print("❌ No se pudo conectar a la BD")
    
    return render_template('login.html')

# Ruta de logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard principal CON DATOS REALES
@app.route('/dashboard')
@login_required
def dashboard():
    hospital_id = session['hospital_id']
    
    print(f"📊 Obteniendo métricas REALES para hospital {hospital_id}")
    
    # Obtener métricas REALES desde BD
    metricas = obtener_metricas_reales(hospital_id)
    
    if not metricas:
        # Fallback si hay error
        metricas = {
            'ocupacion_uci': 76,
            'pacientes_urgencias': 142,
            'insumos_criticos': 87,
            'prediccion_24h': 92,
            'evolucion_semanal': [72, 70, 75, 82, 78],
            'ocupacion_areas': [76, 65, 58]
        }
        flash('Usando datos de demostración - Verifique conexión a BD', 'warning')
        print("⚠️  Usando datos de demostración")
    else:
        print("✅ Mostrando datos REALES de BD")
    
    # Alertas basadas en métricas reales
    alertas = []
    if metricas['ocupacion_uci'] >= 80:
        alertas.append({'mensaje': f'UCI al {metricas["ocupacion_uci"]}% - ALTA OCUPACIÓN', 'tiempo': 'Actual', 'nivel_urgencia': 'ALTO'})
    if metricas['insumos_criticos'] >= 80:
        alertas.append({'mensaje': 'Insumos críticos bajos', 'tiempo': 'Hace 1 hora', 'nivel_urgencia': 'MEDIO'})
    
    if not alertas:
        alertas.append({'mensaje': 'Sistema operando normalmente', 'tiempo': 'Actual', 'nivel_urgencia': 'BAJO'})
    
    return render_template('index.html',
                         hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                         fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                         metricas=metricas,
                         alertas=alertas)

# Predicciones CON DATOS REALES
@app.route('/predictions')
@login_required  
def predictions():
    hospital_id = session['hospital_id']
    
    print(f"🤖 Obteniendo predicciones para hospital {hospital_id}")
    
    # Obtener métricas REALES para predicciones
    metricas = obtener_metricas_reales(hospital_id)
    
    if not metricas:
        # Fallback
        metricas = {
            'ocupacion_uci': 76,
            'prediccion_24h': 92
        }
        print("⚠️  Usando datos de demostración para predicciones")
    
    # Determinar nivel de riesgo
    if metricas['prediccion_24h'] >= 80:
        nivel_riesgo = 'Crítico'
    elif metricas['prediccion_24h'] >= 60:
        nivel_riesgo = 'Moderado'
    else:
        nivel_riesgo = 'Bajo'
    
    predicciones_principal = {
        'prediccion_modelo': metricas['prediccion_24h'],
        'tendencia': 'aumento' if metricas['prediccion_24h'] > metricas['ocupacion_uci'] else 'estable',
        'hospitales_riesgo': 2,
        'ocupacion_actual': metricas['ocupacion_uci'],
        'prediccion_24h': metricas['prediccion_24h'],
        'prediccion_48h': min(100, metricas['prediccion_24h'] + 3),
        'nivel_riesgo': nivel_riesgo
    }
    
    # Datos para gráficas basados en datos reales
    datos_grafica_prediccion = {
        'labels': ["0h", "6h", "12h", "18h", "24h", "30h", "36h", "42h", "48h"],
        'actual': [
            max(0, metricas['ocupacion_uci'] - 10),
            max(0, metricas['ocupacion_uci'] - 5), 
            metricas['ocupacion_uci'],
            min(100, metricas['ocupacion_uci'] + 2),
            min(100, metricas['ocupacion_uci'] + 5),
            None, None, None, None
        ],
        'prediccion': [
            None, None, None, None,
            min(100, metricas['ocupacion_uci'] + 5),
            metricas['prediccion_24h'] - 2,
            metricas['prediccion_24h'],
            metricas['prediccion_24h'] - 1,
            predicciones_principal['prediccion_48h']
        ]
    }
    
    # Datos comparativa (simplificado)
    datos_comparativa = {
        'labels': [session['hospital_nombre'], "Hospital 2", "Hospital 3", "Hospital 4", "Hospital 5"],
        'actual': [
            metricas['ocupacion_uci'],
            metricas['ocupacion_uci'] - 15,
            metricas['ocupacion_uci'] - 25, 
            metricas['ocupacion_uci'] - 30,
            metricas['ocupacion_uci'] + 10
        ],
        'prediccion_24h': [
            metricas['prediccion_24h'],
            metricas['prediccion_24h'] - 10,
            metricas['prediccion_24h'] - 20,
            metricas['prediccion_24h'] - 25,
            metricas['prediccion_24h'] + 5
        ]
    }
    
    otros_hospitales = [
        {'id': 2, 'nombre': 'Hospital Juliaca', 'prediccion_24h': datos_comparativa['prediccion_24h'][1], 'nivel_riesgo': 'Moderado'},
        {'id': 3, 'nombre': 'Hospital Ilave', 'prediccion_24h': datos_comparativa['prediccion_24h'][2], 'nivel_riesgo': 'Bajo'},
        {'id': 4, 'nombre': 'Hospital Ayaviri', 'prediccion_24h': datos_comparativa['prediccion_24h'][3], 'nivel_riesgo': 'Bajo'},
        {'id': 5, 'nombre': 'Hospital Arequipa', 'prediccion_24h': datos_comparativa['prediccion_24h'][4], 'nivel_riesgo': 'Alto'}
    ]
    
    return render_template('predictions.html',
                         hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                         fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                         predicciones=predicciones_principal,
                         otros_hospitales=otros_hospitales,
                         datos_grafica_prediccion=datos_grafica_prediccion,
                         datos_comparativa=datos_comparativa)

# ✅ NUEVA RUTA: Formulario de ingreso de datos
@app.route('/formulario_datos')
@login_required
def formulario_datos():
    return render_template('formulario_datos.html',
                         hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                         fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                         fecha_hoy=datetime.now().strftime("%Y-%m-%d"))

# ✅ NUEVA RUTA: Guardar datos en BD
@app.route('/guardar_datos', methods=['POST'])
@login_required
def guardar_datos():
    hospital_id = session['hospital_id']
    
    try:
        # Obtener datos del formulario
        fecha = request.form.get('fecha')
        total_pacientes = request.form.get('total_pacientes')
        emergencia = request.form.get('emergencia')
        pediatria = request.form.get('pediatria')
        medicina_interna = request.form.get('medicina_interna')
        cirugia_general = request.form.get('cirugia_general')
        ginecologia = request.form.get('ginecologia')
        
        camas_uci_totales = request.form.get('camas_uci_totales')
        camas_uci_ocupadas = request.form.get('camas_uci_ocupadas')
        camas_emergencia_totales = request.form.get('camas_emergencia_totales')
        camas_emergencia_ocupadas = request.form.get('camas_emergencia_ocupadas')
        camas_hospitalizacion_totales = request.form.get('camas_hospitalizacion_totales')
        camas_hospitalizacion_ocupadas = request.form.get('camas_hospitalizacion_ocupadas')
        pacientes_espera = request.form.get('pacientes_espera')
        tiempo_espera_promedio = request.form.get('tiempo_espera_promedio')
        
        emergencia_doctores = request.form.get('emergencia_doctores')
        emergencia_enfermeras = request.form.get('emergencia_enfermeras')
        pediatria_doctores = request.form.get('pediatria_doctores')
        pediatria_enfermeras = request.form.get('pediatria_enfermeras')
        medicina_doctores = request.form.get('medicina_doctores')
        medicina_enfermeras = request.form.get('medicina_enfermeras')
        
        es_festivo = request.form.get('es_festivo', 0)
        nombre_festivo = request.form.get('nombre_festivo', '')
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            
            # 1. Insertar en ASISTENCIA_DIARIA
            cur.execute("""
                INSERT INTO ASISTENCIA_DIARIA 
                (FECHA, ID_HOSPITAL, TOTAL_PACIENTES, EMERGENCIA, PEDIATRIA, MEDICINA_INTERNA, CIRUGIA_GENERAL, GINECOLOGIA)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, total_pacientes, emergencia, pediatria, medicina_interna, cirugia_general, ginecologia))
            
            # 2. Insertar en CAPACIDAD_HOSPITAL
            cur.execute("""
                INSERT INTO CAPACIDAD_HOSPITAL 
                (FECHA, ID_HOSPITAL, CAMAS_UCI_TOTALES, CAMAS_UCI_OCUPADAS, CAMAS_EMERGENCIA_TOTALES, 
                 CAMAS_EMERGENCIA_OCUPADAS, CAMAS_HOSPITALIZACION_TOTALES, CAMAS_HOSPITALIZACION_OCUPADAS,
                 PACIENTES_ESPERA, TIEMPO_ESPERA_PROMEDIO)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, camas_uci_totales, camas_uci_ocupadas, camas_emergencia_totales,
                 camas_emergencia_ocupadas, camas_hospitalizacion_totales, camas_hospitalizacion_ocupadas,
                 pacientes_espera, tiempo_espera_promedio))
            
            # 3. Insertar en PERSONAL_MEDICO
            total_doctores = int(emergencia_doctores) + int(pediatria_doctores) + int(medicina_doctores)
            total_enfermeras = int(emergencia_enfermeras) + int(pediatria_enfermeras) + int(medicina_enfermeras)
            
            cur.execute("""
                INSERT INTO PERSONAL_MEDICO 
                (FECHA, ID_HOSPITAL, EMERGENCIA_DOCTORES, EMERGENCIA_ENFERMERAS, 
                 PEDIATRIA_DOCTORES, PEDIATRIA_ENFERMERAS, MEDICINA_INTERNA_DOCTORES, MEDICINA_INTERNA_ENFERMERAS,
                 TOTAL_DOCTORES, TOTAL_ENFERMERAS)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, emergencia_doctores, emergencia_enfermeras, 
                 pediatria_doctores, pediatria_enfermeras, medicina_doctores, medicina_enfermeras,
                 total_doctores, total_enfermeras))
            
            # 4. Insertar en FACTORES_EXTERNOS
            es_fin_semana = 1 if datetime.strptime(fecha, '%Y-%m-%d').weekday() >= 5 else 0
            dia_semana = datetime.strptime(fecha, '%Y-%m-%d').strftime('%A')
            
            cur.execute("""
                INSERT INTO FACTORES_EXTERNOS 
                (FECHA, ID_HOSPITAL, ES_FESTIVO, NOMBRE_FESTIVO, ES_FIN_SEMANA, DIA_SEMANA)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, es_festivo, nombre_festivo, es_fin_semana, dia_semana))
            
            conn.commit()
            conn.close()
            
            flash('✅ Datos guardados exitosamente', 'success')
            print(f"✅ Datos guardados para hospital {hospital_id}, fecha {fecha}")
            
        else:
            flash('❌ Error conectando a la base de datos', 'error')
            
    except Exception as e:
        flash(f'❌ Error guardando datos: {str(e)}', 'error')
        print(f"❌ Error guardando datos: {e}")
    
    return redirect(url_for('formulario_datos'))

# Gestión Operativa
@app.route('/gestion_operativa')
@login_required
def gestion_operativa():
    return render_template('gestion_operativa.html',
                         hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                         fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"))

# Acerca de
@app.route('/acerca_de')
@login_required
def acerca_de():
    return render_template('acerca_de.html',
                         hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                         fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"))

if __name__ == '__main__':
    app.run(debug=True, port=5000)