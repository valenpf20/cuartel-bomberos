import psycopg2
import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'tu_clave_secreta'  # Cambiala por algo seguro

# 📌 CONEXIÓN A POSTGRESQL
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL)

# 📌 INICIALIZAR DB (solo crea tabla de usuarios si no existe)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('SELECT * FROM usuarios WHERE username = %s', ('admin',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO usuarios (username, password) VALUES (%s, %s)', ('admin', 'admin123'))
    conn.commit()
    cursor.close()
    conn.close()

# 📌 RUTA PRINCIPAL
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bomberos')
    bomberos = cursor.fetchall()
    cursor.execute('SELECT DISTINCT nombre FROM cursos')
    cursos_existentes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', bomberos=bomberos, cursos_existentes=cursos_existentes)

# 📌 DETALLE DE BOMBERO
@app.route('/detalle/<int:id>')
def detalle(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bomberos WHERE id = %s', (id,))
    bombero = cursor.fetchone()
    cursor.execute('SELECT * FROM cursos WHERE bombero_id = %s', (id,))
    cursos = cursor.fetchall()
    cursor.execute('SELECT DISTINCT nombre FROM cursos')
    cursos_existentes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('detalle.html', bombero=bombero, cursos=cursos, cursos_existentes=cursos_existentes)

# 📌 GUARDAR NUEVO BOMBERO
@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    apellido = request.form['apellido']
    cursos = request.form.getlist('curso[]')
    archivos = request.files.getlist('archivo[]')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bomberos (nombre, apellido) VALUES (%s, %s)', (nombre, apellido))
    bombero_id = cursor.fetchone()[0] if cursor.statusmessage.startswith('INSERT') else None
    conn.commit()

    for i in range(len(cursos)):
        curso_nombre = cursos[i]
        archivo = archivos[i]
        archivo_path = None

        if archivo and archivo.filename:
            archivo_path = os.path.join(app.config['UPLOAD_FOLDER'], archivo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            archivo.save(archivo_path)

        cursor.execute(
            'INSERT INTO cursos (bombero_id, nombre, archivo) VALUES (%s, %s, %s)',
            (bombero_id, curso_nombre, archivo_path)
        )

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# 📌 ELIMINAR CURSO
@app.route('/eliminar_curso/<int:curso_id>/<int:bombero_id>')
def eliminar_curso(curso_id, bombero_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cursos WHERE id = %s', (curso_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('detalle', id=bombero_id))

# 📌 ARCHIVOS SUBIDOS
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 📌 AGREGAR CURSO A BOMBERO
@app.route('/guardar_curso/<int:bombero_id>', methods=['POST'])
def guardar_curso(bombero_id):
    nombre = request.form['nombre']
    archivo = request.files.get('archivo')
    archivo_path = None
    if archivo and archivo.filename:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        archivo_path = archivo.filename
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], archivo_path))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO cursos (bombero_id, nombre, archivo) VALUES (%s, %s, %s)', (bombero_id, nombre, archivo_path))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('detalle', id=bombero_id))

# 📌 EDITAR CURSO
@app.route('/editar_curso/<int:curso_id>', methods=['GET', 'POST'])
def editar_curso(curso_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cursos WHERE id = %s', (curso_id,))
    curso = cursor.fetchone()

    if request.method == 'POST':
        nombre = request.form['nombre']
        archivo = request.files.get('archivo')
        archivo_path = curso[3]  # Asumimos que archivo está en la posición 3

        if archivo and archivo.filename:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            archivo_path = archivo.filename
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], archivo_path))

        cursor.execute('UPDATE cursos SET nombre = %s, archivo = %s WHERE id = %s', (nombre, archivo_path, curso_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('detalle', id=curso[1]))  # Asumimos que bombero_id está en la posición 1

    cursor.close()
    conn.close()
    return render_template('editar_curso.html', curso=curso)

# 📌 ELIMINAR BOMBERO Y SUS CURSOS
@app.route('/eliminar_bombero/<int:bombero_id>', methods=['POST'])
def eliminar_bombero(bombero_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cursos WHERE bombero_id = %s', (bombero_id,))
    cursor.execute('DELETE FROM bomberos WHERE id = %s', (bombero_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# 📌 BUSCADOR DE CURSOS
@app.route('/buscar_cursos', methods=['GET', 'POST'])
def buscar_cursos():
    resultados = []
    consulta = ''
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT nombre FROM cursos')
    cursos_existentes = cursor.fetchall()

    if request.method == 'POST':
        consulta = request.form['consulta']
        query = '''
            SELECT DISTINCT b.id, b.nombre, b.apellido 
            FROM bomberos b
            JOIN cursos c ON b.id = c.bombero_id
            WHERE c.nombre ILIKE %s
        '''
        like_pattern = f'%{consulta}%'
        cursor.execute(query, (like_pattern,))
        resultados = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('buscar_cursos.html', resultados=resultados, consulta=consulta, cursos_existentes=cursos_existentes)

# 📌 LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['usuario'] = username
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

# 📌 INICIO DE APP
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    print("Iniciando servidor Flask...")
    app.run(debug=True)
