from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from datetime import date

app = Flask(__name__)

print("Pelican House iniciado...")

# Conexión a PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    conn = psycopg2.connect(DATABASE_URL)
else:
    conn = psycopg2.connect(
        dbname="hotel_db",
        user="postgres",
        password="12345",
        host="localhost",
        port="5432"
    )

cursor = conn.cursor()

# Crear tablas automáticamente
cursor.execute("""
CREATE TABLE IF NOT EXISTS habitaciones (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(10) UNIQUE,
    tipo VARCHAR(50),
    estado VARCHAR(20) DEFAULT 'activa'
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    habitacion_id INT REFERENCES habitaciones(id),
    cliente VARCHAR(100),
    fecha_inicio DATE,
    fecha_fin DATE,
    estado VARCHAR(20) DEFAULT 'confirmada'
);
""")

# Insertar habitaciones solo si no existen
cursor.execute("""
INSERT INTO habitaciones (numero, tipo, estado)
SELECT '01', 'simple', 'activa'
WHERE NOT EXISTS (SELECT 1 FROM habitaciones WHERE numero = '01');
""")

cursor.execute("""
INSERT INTO habitaciones (numero, tipo, estado)
SELECT '02', 'doble', 'activa'
WHERE NOT EXISTS (SELECT 1 FROM habitaciones WHERE numero = '02');
""")

cursor.execute("""
INSERT INTO habitaciones (numero, tipo, estado)
SELECT '03', 'doble', 'activa'
WHERE NOT EXISTS (SELECT 1 FROM habitaciones WHERE numero = '03');
""")

cursor.execute("""
INSERT INTO habitaciones (numero, tipo, estado)
SELECT '04', 'suite', 'activa'
WHERE NOT EXISTS (SELECT 1 FROM habitaciones WHERE numero = '04');
""")

conn.commit()


def actualizar_estados():
    cursor.execute("""
        UPDATE reservas
        SET estado = 'finalizada'
        WHERE estado = 'confirmada'
          AND fecha_fin < CURRENT_DATE;
    """)
    conn.commit()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/disponibles")
def disponibles():
    actualizar_estados()
    hoy = date.today()

    cursor.execute("""
        SELECT numero
        FROM habitaciones h
        WHERE NOT EXISTS (
            SELECT 1
            FROM reservas r
            WHERE r.habitacion_id = h.id
              AND r.estado = 'confirmada'
              AND %s >= r.fecha_inicio
              AND %s < r.fecha_fin
        )
        ORDER BY numero;
    """, (hoy, hoy))

    return jsonify([h[0] for h in cursor.fetchall()])


@app.route("/reservar")
def reservar():
    numero = request.args.get("habitacion")
    cliente = request.args.get("cliente")
    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    try:
        if not numero or not cliente or not inicio or not fin:
            return "Completa todos los campos ❌"

        if fin <= inicio:
            return "La fecha de salida debe ser mayor que la de entrada ❌"

        cursor.execute(
            "SELECT id FROM habitaciones WHERE numero = %s;",
            (numero,)
        )
        resultado = cursor.fetchone()

        if not resultado:
            return "Habitación no existe ❌"

        habitacion_id = resultado[0]

        cursor.execute("""
            SELECT 1
            FROM reservas
            WHERE habitacion_id = %s
              AND estado = 'confirmada'
              AND NOT (%s >= fecha_fin OR %s <= fecha_inicio)
        """, (habitacion_id, inicio, fin))

        if cursor.fetchone():
            return "Ya está reservada en esas fechas ❌"

        cursor.execute("""
            INSERT INTO reservas (habitacion_id, cliente, fecha_inicio, fecha_fin, estado)
            VALUES (%s, %s, %s, %s, 'confirmada');
        """, (habitacion_id, cliente, inicio, fin))

        conn.commit()
        return "Reserva creada ✅"

    except Exception as e:
        conn.rollback()
        return f"Error: {e}"


@app.route("/reservas")
def ver_reservas():
    actualizar_estados()
    hoy = date.today()

    cursor.execute("""
        SELECT r.id, h.numero, r.cliente, r.fecha_inicio, r.fecha_fin
        FROM reservas r
        JOIN habitaciones h ON r.habitacion_id = h.id
        WHERE r.estado = 'confirmada'
          AND %s >= r.fecha_inicio
          AND %s < r.fecha_fin
        ORDER BY r.fecha_inicio, h.numero;
    """, (hoy, hoy))

    datos = cursor.fetchall()

    reservas = []
    for r in datos:
        reservas.append({
            "id": r[0],
            "habitacion": r[1],
            "cliente": r[2],
            "inicio": str(r[3]),
            "fin": str(r[4])
        })

    return jsonify(reservas)


@app.route("/cancelar")
def cancelar():
    reserva_id = request.args.get("id")

    try:
        cursor.execute("""
            UPDATE reservas
            SET estado = 'cancelada'
            WHERE id = %s;
        """, (reserva_id,))

        conn.commit()
        return "Reserva cancelada ✅"

    except Exception as e:
        conn.rollback()
        return f"Error: {e}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
