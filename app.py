import os
import cv2
import sqlite3
import datetime
import threading
import base64
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response

# Configuración
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuración de la base de datos
def init_db():
    conn = sqlite3.connect('visitas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='visitas'")
    if not cursor.fetchone():
        cursor.execute('''
        CREATE TABLE visitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            fecha TEXT,
            hora TEXT,
            imagen_ine_path TEXT,
            imagen_selfie_path TEXT
        )
        ''')
    conn.commit()
    conn.close()

init_db()

# Enfoque simple: capturar imagen directamente sin hilo persistente
def capturar_imagen_simple():
    try:
        # Crear una nueva instancia de cámara para cada captura
        cap = cv2.VideoCapture(0,cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("No se pudo abrir la cámara")
            return False, None
        
        # Configurar parámetros de la cámara para mayor velocidad
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Leer algunos frames para "calentar" la cámara
        for _ in range(2):
            cap.read()
            time.sleep(0.02)
            
        # Leer el frame final
        ret, frame = cap.read()
        
        # Liberar la cámara inmediatamente
        cap.release()
        
        return ret, frame
    
    except:
        
        if 'cap' in locals() and cap is not None:
            cap.release()
        return False, None

# Función para convertir imagen OpenCV a base64 para vista previa instantánea
def frame_to_base64(frame, quality=40):
    try:
        # Reducir tamaño para mejorar velocidad
        frame_resized = cv2.resize(frame, (240, 180))
        
        # Comprimir como JPEG con baja calidad para velocidad
        _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, quality])
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{jpg_as_text}"
    except:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/capturar_ine', methods=['POST'])
def capturar_ine():
    exito, frame = capturar_imagen_simple()
    
    if exito:
        # Obtener fecha y hora actuales
        ahora = datetime.datetime.now()
        fecha = ahora.strftime('%Y-%m-%d')
        hora = ahora.strftime('%H:%M:%S')
        
        # Generar base64 para vista previa inmediata
        base64_preview = frame_to_base64(frame)
        
        # Guardar la imagen en disco con menor prioridad (en segundo plano)
        timestamp = ahora.strftime('%Y%m%d%H%M%S')
        imagen_filename = f'ine_{timestamp}.jpg'
        imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
        
        threading.Thread(target=lambda: cv2.imwrite(imagen_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 50])).start()
        return jsonify({'success': True, 'fecha': fecha, 'hora': hora, 'imagen_ine': imagen_path, 'preview_base64': base64_preview})
    return jsonify({'success': False})

@app.route('/capturar_selfie', methods=['POST'])
def capturar_selfie():
    exito, frame = capturar_imagen_simple()
    
    if exito:
        # Generar base64 para vista previa inmediata
        base64_preview = frame_to_base64(frame)
        
        # Guardar la imagen con calidad reducida (en segundo plano)
        ahora = datetime.datetime.now()
        timestamp = ahora.strftime('%Y%m%d%H%M%S')
        imagen_filename = f'selfie_{timestamp}.jpg'
        imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], imagen_filename)
        
        threading.Thread(target=lambda: cv2.imwrite(imagen_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 50])).start()
        return jsonify({'success': True, 'imagen_selfie': imagen_path, 'preview_base64': base64_preview})
    return jsonify({'success': False})

@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form.get('nombre')
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    imagen_ine_path = request.form.get('imagen_ine_path')
    imagen_selfie_path = request.form.get('imagen_selfie_path', '')  # Opcional
    
    conn = sqlite3.connect('visitas.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO visitas (nombre, fecha, hora, imagen_ine_path, imagen_selfie_path) VALUES (?, ?, ?, ?, ?)',
        (nombre, fecha, hora, imagen_ine_path, imagen_selfie_path)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

@app.route('/consultar')
def consultar():
    conn = sqlite3.connect('visitas.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM visitas ORDER BY id DESC')
    visitas = cursor.fetchall()
    conn.close()
    
    return render_template('consulta.html', visitas=visitas)

@app.route('/buscar', methods=['POST'])
def buscar():
    busqueda = request.form.get('busqueda')
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')
    
    query = 'SELECT * FROM visitas WHERE 1=1'
    params = []
    
    if busqueda:
        query += ' AND nombre LIKE ?'
        params.append(f'%{busqueda}%')
    
    if fecha_inicio:
        query += ' AND fecha >= ?'
        params.append(fecha_inicio)
    

    # CODIGO DE DIEGO ARTURO HERNANDEZ REYES - DAOSTEK
    if fecha_fin:
        query += ' AND fecha <= ?'
        params.append(fecha_fin)
    
    query += ' ORDER BY id DESC'
    
    conn = sqlite3.connect('visitas.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    visitas = cursor.fetchall()
    conn.close()
    
    return render_template('consulta.html', visitas=visitas)




@app.route('/descargar_respaldo')
def descargar_respaldo():

    meses = [
        "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
        "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
    ]
    mes_actual = meses[datetime.datetime.now().month - 1]


    conn = sqlite3.connect('visitas.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM visitas')
    data = cursor.fetchall()
    conn.close()

    respaldo = "ID,Nombre,Fecha,Hora,INE,Selfie\n"
    for row in data:
        respaldo += ",".join(str(col) for col in row) + "\n"
    
    filename = f"respaldo_visitas_{mes_actual}.csv"

    return Response(
        respaldo,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def borrar_visitas_y_fotos():
    conn = sqlite3.connect('visitas.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM visitas')
    
    conn.commit()
    conn.close()
  
    
    folder_path = os.path.join('static', 'uploads')
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error eliminando {file_path}: {e}")
    
   

@app.route('/borrar_visitas', methods=['POST'])
def borrar_visitas():
    borrar_visitas_y_fotos()
    return jsonify({'success': True})





if __name__ == '__main__':
    app.run(debug=True)