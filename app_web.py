from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from datetime import date, datetime

app = Flask(__name__)

print("Pelican House iniciado...")

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        dbname="hotel_db",
        user="postgres",
        password="12345",
        host="localhost",
        port="5432"
    )


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

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
    cursor.close()
    conn.close()


def actualizar_estados():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE reservas
        SET estado = 'finalizada'
        WHERE estado = 'confirmada'
          AND fecha_fin < CURRENT_DATE;
    """)

    conn.commit()
    cursor.close()
    conn.close()


init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return "OK", 200
    except Exception as e:
        return f"DB error: {e}", 500


@app.route("/disponibles")
def disponibles():
    try:
        actualizar_estados()
        hoy = date.today()

        conn = get_connection()
        cursor = conn.cursor()

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

        data = [h[0] for h in cursor.fetchall()]
        cursor.close()
        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/reservar")
def reservar():
    numero = request.args.get("habitacion")
    cliente = request.args.get("cliente")
    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    if not numero or not cliente or not inicio or not fin:
        return "Completa todos los campos ❌"

    try:
        fecha_inicio = datetime.strptime(inicio, "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(fin, "%Y-%m-%d").date()
    except ValueError:
        return "Formato de fecha inválido ❌"

    if fecha_fin <= fecha_inicio:
        return "La fecha de salida debe ser mayor que la de entrada ❌"

    try:
        actualizar_estados()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM habitaciones WHERE numero = %s;",
            (numero,)
        )
        resultado = cursor.fetchone()

        if not resultado:
            cursor.close()
            conn.close()
            return "Habitación no existe ❌"

        habitacion_id = resultado[0]

        cursor.execute("""
            SELECT 1
            FROM reservas
            WHERE habitacion_id = %s
              AND estado = 'confirmada'
              AND NOT (%s >= fecha_fin OR %s <= fecha_inicio)
        """, (habitacion_id, fecha_inicio, fecha_fin))

        if cursor.fetchone():
            cursor.close()
            conn.close()
            return "Ya está reservada en esas fechas ❌"

        cursor.execute("""
            INSERT INTO reservas (habitacion_id, cliente, fecha_inicio, fecha_fin, estado)
            VALUES (%s, %s, %s, %s, 'confirmada');
        """, (habitacion_id, cliente, fecha_inicio, fecha_fin))

        conn.commit()
        cursor.close()
        conn.close()

        return "Reserva creada ✅"

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        try:
            cursor.close()
            conn.close()
        except:
            pass
        return f"Error: {e}"


@app.route("/reservas")
def ver_reservas():
    try:
        actualizar_estados()
        hoy = date.today()

        conn = get_connection()
        cursor = conn.cursor()

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
        cursor.close()
        conn.close()

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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cancelar")
def cancelar():
    reserva_id = request.args.get("id")

    if not reserva_id:
        return "Falta el id ❌"

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE reservas
            SET estado = 'cancelada'
            WHERE id = %s;
        """, (reserva_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return "Reserva cancelada ✅"

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        try:
            cursor.close()
            conn.close()
        except:
            pass
        return f"Error: {e}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
