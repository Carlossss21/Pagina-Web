from flask import Flask, request, jsonify, render_template
import psycopg2
import os
from datetime import date

app = Flask(__name__)

print("Pelican House iniciado...")

# 🔌 CONEXIÓN (local o Render)
conn = psycopg2.connect(
    dbname=os.environ.get("DB_NAME", "hotel_db"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "12345"),
    host=os.environ.get("DB_HOST", "localhost"),
    port=os.environ.get("DB_PORT", "5432")
)

cursor = conn.cursor()

# 🔄 ACTUALIZAR ESTADOS
def actualizar_estados():
    cursor.execute("""
        UPDATE reservas
        SET estado = 'finalizada'
        WHERE estado = 'confirmada'
        AND fecha_fin < CURRENT_DATE;
    """)
    conn.commit()

# 🏠 HOME
@app.route("/")
def home():
    return render_template("index.html")

# 🟢 HABITACIONES DISPONIBLES
@app.route("/disponibles")
def disponibles():
    actualizar_estados()
    hoy = date.today()

    cursor.execute("""
    SELECT numero FROM habitaciones h
    WHERE NOT EXISTS (
        SELECT 1 FROM reservas r
        WHERE r.habitacion_id = h.id
        AND r.estado = 'confirmada'
        AND %s >= r.fecha_inicio
        AND %s < r.fecha_fin
    )
    ORDER BY numero;
    """, (hoy, hoy))

    return jsonify([h[0] for h in cursor.fetchall()])

# 🏨 CREAR RESERVA
@app.route("/reservar")
def reservar():
    numero = request.args.get("habitacion")
    cliente = request.args.get("cliente")
    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    try:
        if not numero or not cliente or not inicio or not fin:
            return "Completa todos los campos ❌"

        cursor.execute("SELECT id FROM habitaciones WHERE numero=%s;", (numero,))
        resultado = cursor.fetchone()

        if not resultado:
            return "Habitación no existe ❌"

        habitacion_id = resultado[0]

        cursor.execute("""
        SELECT 1 FROM reservas
        WHERE habitacion_id = %s
        AND estado='confirmada'
        AND NOT (%s >= fecha_fin OR %s <= fecha_inicio)
        """, (habitacion_id, inicio, fin))

        if cursor.fetchone():
            return "Ya está reservada en esas fechas ❌"

        cursor.execute("""
        INSERT INTO reservas (habitacion_id, cliente, fecha_inicio, fecha_fin, estado)
        VALUES (%s,%s,%s,%s,'confirmada');
        """, (habitacion_id, cliente, inicio, fin))

        conn.commit()
        return "Reserva creada ✅"

    except Exception as e:
        conn.rollback()
        return f"Error: {e}"

# 📋 VER RESERVAS
@app.route("/reservas")
def ver_reservas():
    actualizar_estados()
    hoy = date.today()

    cursor.execute("""
    SELECT r.id, h.numero, r.cliente, r.fecha_inicio, r.fecha_fin
    FROM reservas r
    JOIN habitaciones h ON r.habitacion_id = h.id
    WHERE r.estado='confirmada'
    AND %s >= r.fecha_inicio
    AND %s < r.fecha_fin
    ORDER BY r.fecha_inicio;
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

# ❌ CANCELAR
@app.route("/cancelar")
def cancelar():
    reserva_id = request.args.get("id")

    cursor.execute("""
    UPDATE reservas
    SET estado='cancelada'
    WHERE id=%s;
    """, (reserva_id,))

    conn.commit()
    return "Cancelada"

# ▶️ RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)