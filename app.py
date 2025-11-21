from flask import Flask, render_template, request, redirect, url_for, session, flash
import firebirdsql
import os
import pickle
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_temporal_para_prototipo'

# Configuración de la base de datos
def get_db_connection():
    try:
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        ruta_bd = os.path.join(directorio_actual, 'data', 'BASEH.fdb')
        
        print(f"Buscando BD en: {ruta_bd}")
        
        if not os.path.exists(ruta_bd):
            print("ERROR: El archivo BASEH.FDB no existe")
            return None
            
        conn = firebirdsql.connect(
            host='localhost',
            database=ruta_bd,
            user='SYSDBA',
            password='masterkey',
            charset='ISO8859_1'
        )
        print("Conexión a BD exitosa")
        return conn
    except Exception as e:
        print(f"Error conectando a BD: {e}")
        return None

# Cargar modelo ML
def cargar_modelo_ml(hospital_id):
    try:
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        modelo_path = os.path.join(directorio_actual, 'ml', 'modelos', f'hospital_{hospital_id}.pkl')
        
        if not os.path.exists(modelo_path):
            print(f"Modelo no encontrado: {modelo_path}")
            return None
            
        with open(modelo_path, 'rb') as f:
            modelo = pickle.load(f)
        print(f"Modelo ML cargado para hospital {hospital_id}")
        return modelo
    except Exception as e:
        print(f"Error cargando modelo ML: {e}")
        return None

# Obtener métricas REALES desde BD
def obtener_metricas_reales(hospital_id):
    conn = get_db_connection()
    if not conn:
        print("No se pudo conectar a BD para métricas")
        return None
        
    try:
        cur = conn.cursor()
        
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
            print("No se encontraron datos para el hospital")
            return None
            
        print(f"Datos BD obtenidos: UCI={datos[0]}/{datos[1]}, Espera={datos[3]}, Total={datos[4]}")
        
        ocupacion_uci = round((datos[0] / datos[1]) * 100) if datos[1] > 0 else 0
        pacientes_urgencias = datos[3]
        total_pacientes = datos[4]
        
        cur.execute("""
            SELECT CAMAS_UCI_OCUPADAS
            FROM CAPACIDAD_HOSPITAL
            WHERE ID_HOSPITAL = ?
            ORDER BY FECHA DESC
            ROWS 5
        """, (hospital_id,))
        
        evolucion_data = [fila[0] for fila in cur.fetchall()]
        while len(evolucion_data) < 5:
            evolucion_data.append(evolucion_data[-1] if evolucion_data else datos[0])
            
        evolucion_semanal = [round((camas / datos[1]) * 100) if datos[1] > 0 else 0 for camas in evolucion_data]
        
        modelo = cargar_modelo_ml(hospital_id)
        prediccion_24h = 0
        
        if modelo:
            try:
                datos_prediccion = [
                    total_pacientes,
                    datos[2],
                    25,
                    datos[0],
                    datos[1],
                    0,
                    1 if datetime.now().weekday() >= 5 else 0
                ]
                
                prediccion = modelo.predict([datos_prediccion])
                prediccion_24h = min(100, max(0, round(prediccion[0])))
                print(f"Predicción ML: {prediccion_24h}%")
                
            except Exception as e:
                print(f"Error en predicción ML: {e}")
                prediccion_24h = min(100, ocupacion_uci + 5)
        else:
            prediccion_24h = min(100, ocupacion_uci + 8)
        
        metricas = {
            'ocupacion_uci': ocupacion_uci,
            'pacientes_urgencias': pacientes_urgencias,
            'insumos_criticos': max(70, 100 - ocupacion_uci),
            'prediccion_24h': prediccion_24h,
            'evolucion_semanal': evolucion_semanal,
            'ocupacion_areas': [ocupacion_uci, 65, 58]
        }
        
        print(f"Métricas calculadas: UCI={ocupacion_uci}%, Predicción={prediccion_24h}%")
        return metricas
        
    except Exception as e:
        print(f"Error obteniendo métricas: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

# Obtener ocupación de otros hospitales
def obtener_ocupacion_otros_hospitales(hospital_actual_id):
    conn = get_db_connection()
    if not conn:
        print("No se pudo conectar a BD para obtener datos de otros hospitales")
        return []
        
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT
                h.ID_HOSPITAL,
                h.NOMBRE_HOSPITAL,
                ch.CAMAS_UCI_OCUPADAS,
                ch.CAMAS_UCI_TOTALES,
                ch.FECHA
            FROM HOSPITALES h
            LEFT JOIN CAPACIDAD_HOSPITAL ch ON h.ID_HOSPITAL = ch.ID_HOSPITAL
            WHERE h.ID_HOSPITAL != ?
            AND ch.FECHA = (
                SELECT MAX(FECHA)
                FROM CAPACIDAD_HOSPITAL
                WHERE ID_HOSPITAL = h.ID_HOSPITAL
            )
            ORDER BY h.ID_HOSPITAL
        """, (hospital_actual_id,))
        
        resultados = cur.fetchall()
        otros_hospitales = []
        
        for hospital in resultados:
            id_hospital, nombre, uci_ocupadas, uci_totales, fecha = hospital
            
            if uci_totales and uci_totales > 0:
                ocupacion_porcentaje = round((uci_ocupadas / uci_totales) * 100)
            else:
                ocupacion_porcentaje = 0
                
            otros_hospitales.append({
                'id': id_hospital,
                'nombre': nombre,
                'ocupacion_uci': ocupacion_porcentaje,
                'uci_ocupadas': uci_ocupadas,
                'uci_totales': uci_totales,
                'fecha_actualizacion': fecha
            })
        
        print(f"Datos obtenidos para {len(otros_hospitales)} otros hospitales")
        return otros_hospitales
        
    except Exception as e:
        print(f"Error obteniendo datos de otros hospitales: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

# Obtener predicciones de otros hospitales
def obtener_predicciones_otros_hospitales(hospital_actual_id):
    otros_hospitales = obtener_ocupacion_otros_hospitales(hospital_actual_id)
    
    if not otros_hospitales:
        print("Usando datos de ejemplo para predicciones de otros hospitales")
        todos_hospitales = [
            {'id': 1, 'nombre': 'Hospital Regional Manuel Nunez Butron', 'ocupacion_uci': 65},
            {'id': 2, 'nombre': 'Hospital Carlos Monge Medrano', 'ocupacion_uci': 45},
            {'id': 3, 'nombre': 'Hospital de Apoyo Ilave', 'ocupacion_uci': 40},
            {'id': 4, 'nombre': 'Hospital de Apoyo Ayaviri', 'ocupacion_uci': 35},
            {'id': 5, 'nombre': 'Hospital Regional Honorio Delgado', 'ocupacion_uci': 85}
        ]
        otros_hospitales = [h for h in todos_hospitales if h['id'] != hospital_actual_id]
    
    for hospital in otros_hospitales:
        ocupacion_actual = hospital['ocupacion_uci']
        
        if ocupacion_actual >= 80:
            prediccion = min(100, ocupacion_actual + 5)
        elif ocupacion_actual >= 60:
            prediccion = min(100, ocupacion_actual + 3)
        else:
            prediccion = min(100, ocupacion_actual + 2)
        
        hospital['prediccion_24h'] = prediccion
    
    return otros_hospitales

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
        
        print(f"Intento de login: ID={id_hospital}")
        
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
                    
                    hospital_nombre = f"Hospital {hospital_id}"
                    try:
                        cur.execute("SELECT NOMBRE_HOSPITAL FROM HOSPITALES WHERE ID_HOSPITAL = ?", (hospital_id,))
                        nombre_result = cur.fetchone()
                        if nombre_result:
                            hospital_nombre = nombre_result[0]
                    except Exception as nombre_error:
                        print(f"Error obteniendo nombre: {nombre_error}")
                    
                    session['hospital_id'] = hospital_id
                    session['hospital_nombre'] = hospital_nombre
                    session['logged_in'] = True
                    conn.close()
                    print(f"Login exitoso: {hospital_nombre}")
                    return redirect(url_for('dashboard'))
                else:
                    flash('ID de hospital o contraseña incorrectos', 'error')
                    print("Login fallido: credenciales incorrectas")
                    
            except Exception as e:
                flash('Error en el sistema de autenticación', 'error')
                print(f"Error en login: {e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
        else:
            flash('Error conectando a la base de datos', 'error')
            print("No se pudo conectar a la BD")
    
    return render_template('login.html')

# Ruta de logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Dashboard principal
@app.route('/dashboard')
@login_required
def dashboard():
    hospital_id = session['hospital_id']
    
    print(f"Obteniendo métricas REALES para hospital {hospital_id}")
    
    metricas = obtener_metricas_reales(hospital_id)
    
    if not metricas:
        metricas = {
            'ocupacion_uci': 76,
            'pacientes_urgencias': 142,
            'insumos_criticos': 87,
            'prediccion_24h': 92,
            'evolucion_semanal': [72, 70, 75, 82, 78],
            'ocupacion_areas': [76, 65, 58]
        }
        flash('Usando datos de demostración - Verifique conexión a BD', 'warning')
        print("Usando datos de demostración")
    else:
        print("Mostrando datos REALES de BD")
    
    otros_hospitales = obtener_ocupacion_otros_hospitales(hospital_id)
    
    if not otros_hospitales:
        todos_hospitales = [
            {'id': 1, 'nombre': 'Hospital Regional Manuel Nunez Butron', 'ocupacion_uci': 65},
            {'id': 2, 'nombre': 'Hospital Carlos Monge Medrano', 'ocupacion_uci': 45},
            {'id': 3, 'nombre': 'Hospital de Apoyo Ilave', 'ocupacion_uci': 40},
            {'id': 4, 'nombre': 'Hospital de Apoyo Ayaviri', 'ocupacion_uci': 35},
            {'id': 5, 'nombre': 'Hospital Regional Honorio Delgado', 'ocupacion_uci': 85}
        ]
        otros_hospitales = [h for h in todos_hospitales if h['id'] != hospital_id]
        print("Usando datos de ejemplo para otros hospitales")
    
    alertas = []
    if metricas['ocupacion_uci'] >= 80:
        alertas.append({'mensaje': f'UCI al {metricas["ocupacion_uci"]}% - ALTA OCUPACION', 'tiempo': 'Actual', 'nivel_urgencia': 'ALTO'})
    if metricas['insumos_criticos'] >= 80:
        alertas.append({'mensaje': 'Insumos criticos bajos', 'tiempo': 'Hace 1 hora', 'nivel_urgencia': 'MEDIO'})
    
    if not alertas:
        alertas.append({'mensaje': 'Sistema operando normalmente', 'tiempo': 'Actual', 'nivel_urgencia': 'BAJO'})
    
    return render_template('index.html',
                          hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                          fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                          metricas=metricas,
                          alertas=alertas,
                          otros_hospitales=otros_hospitales)

# Ruta de predicciones CORREGIDA
@app.route('/predictions')
@login_required  
def predictions():
    hospital_id = session['hospital_id']
    
    print(f"Obteniendo predicciones para hospital {hospital_id}")
    
    metricas = obtener_metricas_reales(hospital_id)
    
    if not metricas:
        metricas = {
            'ocupacion_uci': 76,
            'prediccion_24h': 92
        }
        print("Usando datos de demostración para predicciones")
    
    if metricas['prediccion_24h'] >= 80:
        nivel_riesgo = 'Crítico'
    elif metricas['prediccion_24h'] >= 60:
        nivel_riesgo = 'Moderado'
    else:
        nivel_riesgo = 'Bajo'
    
    # OBTENER DATOS REALES DE OTROS HOSPITALES CON PREDICCIONES
    otros_hospitales_reales = obtener_predicciones_otros_hospitales(hospital_id)
    
    for hospital in otros_hospitales_reales:
        if hospital['prediccion_24h'] >= 80:
            hospital['nivel_riesgo'] = 'Alto'
        elif hospital['prediccion_24h'] >= 60:
            hospital['nivel_riesgo'] = 'Moderado'
        else:
            hospital['nivel_riesgo'] = 'Bajo'
    
    predicciones_principal = {
        'prediccion_modelo': metricas['prediccion_24h'],
        'tendencia': 'aumento' if metricas['prediccion_24h'] > metricas['ocupacion_uci'] else 'estable',
        'hospitales_riesgo': len([h for h in otros_hospitales_reales if h['nivel_riesgo'] == 'Alto']),
        'ocupacion_actual': metricas['ocupacion_uci'],
        'prediccion_24h': metricas['prediccion_24h'],
        'prediccion_48h': min(100, metricas['prediccion_24h'] + 3),
        'nivel_riesgo': nivel_riesgo
    }
    
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
    
    # CORRECCIÓN: Gráfica comparativa solo muestra otros hospitales (excluyendo el actual)
    nombres_hospitales = [h['nombre'] for h in otros_hospitales_reales]
    ocupacion_actual = [h['ocupacion_uci'] for h in otros_hospitales_reales]
    prediccion_24h = [h['prediccion_24h'] for h in otros_hospitales_reales]
    
    datos_comparativa = {
        'labels': nombres_hospitales,
        'actual': ocupacion_actual,
        'prediccion_24h': prediccion_24h
    }
    
    return render_template('predictions.html',
                          hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                          fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                          predicciones=predicciones_principal,
                          otros_hospitales=otros_hospitales_reales,
                          datos_grafica_prediccion=datos_grafica_prediccion,
                          datos_comparativa=datos_comparativa)

@app.route('/formulario_datos')
@login_required
def formulario_datos():
    return render_template('formulario_datos.html',
                          hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                          fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"),
                          fecha_hoy=datetime.now().strftime("%Y-%m-%d"))

@app.route('/guardar_datos', methods=['POST'])
@login_required
def guardar_datos():
    hospital_id = session['hospital_id']
    
    try:
        fecha = request.form.get('fecha')
        total_pacientes = request.form.get('total_pacientes')
        emergencia = request.form.get('emergencia')
        pediatria = request.form.get('pediatria')
        medicina_interna = request.form.get('medicina_interna')
        cirugia_general = request.form.get('cirugia_general')
        ginecologia = request.form.get('ginecologia')
        
        # NUEVOS CAMPOS PARA ASISTENCIA_DIARIA
        traumatologia = request.form.get('traumatologia', 0)
        cardiologia = request.form.get('cardiologia', 0)
        neurologia = request.form.get('neurologia', 0)
        oncologia = request.form.get('oncologia', 0)
        dermatologia = request.form.get('dermatologia', 0)
        
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
        
        # NUEVOS CAMPOS PARA PERSONAL_MEDICO
        cirugia_doctores = request.form.get('cirugia_doctores', 0)
        cirugia_enfermeras = request.form.get('cirugia_enfermeras', 0)
        ginecologia_doctores = request.form.get('ginecologia_doctores', 0)
        ginecologia_enfermeras = request.form.get('ginecologia_enfermeras', 0)
        
        es_festivo = request.form.get('es_festivo', 0)
        nombre_festivo = request.form.get('nombre_festivo', '')
        temporada_especial = request.form.get('temporada_especial', '')
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            
            # ASISTENCIA_DIARIA - COMPLETO
            cur.execute("""
                INSERT INTO ASISTENCIA_DIARIA
                (FECHA, ID_HOSPITAL, TOTAL_PACIENTES, EMERGENCIA, PEDIATRIA, MEDICINA_INTERNA, 
                 CIRUGIA_GENERAL, GINECOLOGIA, TRAUMATOLOGIA, CARDIOLOGIA, NEUROLOGIA, ONCOLOGIA, DERMATOLOGIA)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, total_pacientes, emergencia, pediatria, medicina_interna, 
                  cirugia_general, ginecologia, traumatologia, cardiologia, neurologia, oncologia, dermatologia))
            
            # CAPACIDAD_HOSPITAL - COMPLETO
            cur.execute("""
                INSERT INTO CAPACIDAD_HOSPITAL
                (FECHA, ID_HOSPITAL, CAMAS_UCI_TOTALES, CAMAS_UCI_OCUPADAS, CAMAS_EMERGENCIA_TOTALES,
                 CAMAS_EMERGENCIA_OCUPADAS, CAMAS_HOSPITALIZACION_TOTALES, CAMAS_HOSPITALIZACION_OCUPADAS,
                 PACIENTES_ESPERA, TIEMPO_ESPERA_PROMEDIO)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, camas_uci_totales, camas_uci_ocupadas, camas_emergencia_totales,
                 camas_emergencia_ocupadas, camas_hospitalizacion_totales, camas_hospitalizacion_ocupadas,
                 pacientes_espera, tiempo_espera_promedio))
            
            # PERSONAL_MEDICO - COMPLETO
            total_doctores = int(emergencia_doctores) + int(pediatria_doctores) + int(medicina_doctores) + int(cirugia_doctores) + int(ginecologia_doctores)
            total_enfermeras = int(emergencia_enfermeras) + int(pediatria_enfermeras) + int(medicina_enfermeras) + int(cirugia_enfermeras) + int(ginecologia_enfermeras)
            
            cur.execute("""
                INSERT INTO PERSONAL_MEDICO
                (FECHA, ID_HOSPITAL, EMERGENCIA_DOCTORES, EMERGENCIA_ENFERMERAS,
                 PEDIATRIA_DOCTORES, PEDIATRIA_ENFERMERAS, MEDICINA_INTERNA_DOCTORES, MEDICINA_INTERNA_ENFERMERAS,
                 CIRUGIA_DOCTORES, CIRUGIA_ENFERMERAS, GINECOLOGIA_DOCTORES, GINECOLOGIA_ENFERMERAS,
                 TOTAL_DOCTORES, TOTAL_ENFERMERAS)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, emergencia_doctores, emergencia_enfermeras,
                 pediatria_doctores, pediatria_enfermeras, medicina_doctores, medicina_enfermeras,
                 cirugia_doctores, cirugia_enfermeras, ginecologia_doctores, ginecologia_enfermeras,
                 total_doctores, total_enfermeras))
            
            # FACTORES_EXTERNOS - COMPLETO
            es_fin_semana = datetime.strptime(fecha, '%Y-%m-%d').weekday() >= 5
            dia_semana = datetime.strptime(fecha, '%Y-%m-%d').strftime('%A')
            
            cur.execute("""
                INSERT INTO FACTORES_EXTERNOS
                (FECHA, ID_HOSPITAL, ES_FESTIVO, NOMBRE_FESTIVO, ES_FIN_SEMANA, DIA_SEMANA, TEMPORADA_ESPECIAL)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fecha, hospital_id, es_festivo, nombre_festivo, es_fin_semana, dia_semana, temporada_especial))
            
            conn.commit()
            conn.close()
            
            flash('Datos guardados exitosamente', 'success')
            print(f"Datos guardados para hospital {hospital_id}, fecha {fecha}")
            
        else:
            flash('Error conectando a la base de datos', 'error')
            
    except Exception as e:
        flash(f'Error guardando datos: {str(e)}', 'error')
        print(f"Error guardando datos: {e}")
    
    return redirect(url_for('formulario_datos'))

@app.route('/gestion_operativa')
@login_required
def gestion_operativa():
    return render_template('gestion_operativa.html',
                          hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                          fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"))

@app.route('/acerca_de')
@login_required
def acerca_de():
    return render_template('acerca_de.html',
                          hospital_nombre=session.get('hospital_nombre', 'Hospital'),
                          fecha_actual=datetime.now().strftime("%A, %d de %B de %Y"))

if __name__ == '__main__':
    app.run(debug=True, port=5000)