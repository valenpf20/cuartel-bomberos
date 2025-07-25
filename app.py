import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE'] = 'data/bomberos.db'

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
     CREATE TABLE IF NOT EXISTS usuarios (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT NOT NULL UNIQUE,
         password TEXT NOT NULL
     )
 ''')

  # Solo si no existe ya un admin
    cursor.execute('SELECT * FROM usuarios WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO usuarios (username, password) VALUES (?, ?)', ('admin', 'admin123'))

    conn.commit()
    conn.close()

from flask import session, flash

app.secret_key = 'tu_clave_secreta'  # Cambiala por algo más seguro


@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    bomberos = conn.execute('SELECT * FROM bomberos').fetchall()
    cursos_existentes = conn.execute('SELECT DISTINCT nombre FROM cursos').fetchall()
    conn.close()
    return render_template('index.html', bomberos=bomberos, cursos_existentes=cursos_existentes)



@app.route('/detalle/<int:id>')
def detalle(id):
    conn = get_db_connection()
    bombero = conn.execute('SELECT * FROM bomberos WHERE id = ?', (id,)).fetchone()
    cursos = conn.execute('SELECT * FROM cursos WHERE bombero_id = ?', (id,)).fetchall()
    cursos_existentes = conn.execute('SELECT DISTINCT nombre FROM cursos').fetchall()
    conn.close()
    return render_template('detalle.html', bombero=bombero, cursos=cursos, cursos_existentes=cursos_existentes)


@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    apellido = request.form['apellido']
    cursos = request.form.getlist('curso[]')
    archivos = request.files.getlist('archivo[]')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO bomberos (nombre, apellido) VALUES (?, ?)', (nombre, apellido))
    bombero_id = cursor.lastrowid

    for i in range(len(cursos)):
        curso_nombre = cursos[i]
        archivo = archivos[i]
        archivo_path = None

        if archivo and archivo.filename:
            archivo_path = os.path.join(app.config['UPLOAD_FOLDER'], archivo.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            archivo.save(archivo_path)

        cursor.execute(
            'INSERT INTO cursos (bombero_id, nombre, archivo) VALUES (?, ?, ?)',
            (bombero_id, curso_nombre, archivo_path)
        )

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/eliminar_curso/<int:curso_id>/<int:bombero_id>')
def eliminar_curso(curso_id, bombero_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cursos WHERE id = ?', (curso_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('detalle', id=bombero_id))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
    conn.execute('INSERT INTO cursos (bombero_id, nombre, archivo) VALUES (?, ?, ?)', (bombero_id, nombre, archivo_path))
    conn.commit()
    conn.close()
    return redirect(url_for('detalle', id=bombero_id))

@app.route('/editar_curso/<int:curso_id>', methods=['GET', 'POST'])
def editar_curso(curso_id):
    conn = get_db_connection()
    curso = conn.execute('SELECT * FROM cursos WHERE id = ?', (curso_id,)).fetchone()

    if request.method == 'POST':
        nombre = request.form['nombre']
        archivo = request.files.get('archivo')
        archivo_path = curso['archivo']  # mantener el anterior por defecto

        if archivo and archivo.filename:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            archivo_path = archivo.filename
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], archivo_path))

        conn.execute('UPDATE cursos SET nombre = ?, archivo = ? WHERE id = ?', (nombre, archivo_path, curso_id))
        conn.commit()
        conn.close()
        return redirect(url_for('detalle', id=curso['bombero_id']))

    conn.close()
    return render_template('editar_curso.html', curso=curso)

@app.route('/eliminar_bombero/<int:bombero_id>', methods=['POST'])
def eliminar_bombero(bombero_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cursos WHERE bombero_id = ?', (bombero_id,))
    conn.execute('DELETE FROM bomberos WHERE id = ?', (bombero_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/buscar_cursos', methods=['GET', 'POST'])
def buscar_cursos():
    resultados = []
    consulta = ''
    conn = get_db_connection()
    cursos_existentes = conn.execute('SELECT DISTINCT nombre FROM cursos').fetchall()
    conn.close()

    if request.method == 'POST':
        consulta = request.form['consulta']
        conn = get_db_connection()
        query = '''
            SELECT DISTINCT b.id, b.nombre, b.apellido 
            FROM bomberos b
            JOIN cursos c ON b.id = c.bombero_id
            WHERE c.nombre LIKE ?
        '''
        like_pattern = f'%{consulta}%'
        resultados = conn.execute(query, (like_pattern,)).fetchall()
        conn.close()

    return render_template('buscar_cursos.html', resultados=resultados, consulta=consulta, cursos_existentes=cursos_existentes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (username, password)).fetchone()
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


if __name__ == '__main__':
     os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
     os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
     init_db()
     print("Iniciando servidor Flask...")
     app.run(debug=True)
