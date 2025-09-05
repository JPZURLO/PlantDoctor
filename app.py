import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager
from models import db, User # Importa a partir do models.py

app = Flask(__name__)

# --- Configuração ---
# Usa a DATABASE_URL do Render, ou um ficheiro local para testes
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

# ✅ PASSO DE DEPURAÇÃO: Imprime a URL original recebida do Render.
# O 'flush=True' garante que o log aparece imediatamente.
print(f"📌 [DEBUG] DATABASE_URL Original: {database_url}", flush=True)

# ✅ CORRIGIDO: Garante que a URL do PostgreSQL é compatível com SQLAlchemy 1.4+
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# ✅ PASSO DE DEPURAÇÃO: Imprime a URL final que será usada pelo SQLAlchemy.
print(f"📌 [DEBUG] DATABASE_URL Final para SQLAlchemy: {database_url}", flush=True)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')

# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)

# --- Rotas da API ---

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Nenhum dado recebido."}), 400

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Nome, email ou senha em falta."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Este email já está registado."}), 409

    hashed_password = generate_password_hash(password)
    
    new_user = User(name=name, email=email, password_hash=hashed_password)

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": f"Utilizador {name} registado com sucesso!"}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao registar utilizador: {e}")
        return jsonify({"message": "Erro interno ao registar utilizador."}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Nenhum dado recebido."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email ou senha em falta."}), 400

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(identity=user.id)
        return jsonify({
            "message": "Login bem-sucedido!",
            "token": access_token
        }), 200
    else:
        return jsonify({"message": "Credenciais inválidas."}), 401

# --- Bloco de Execução ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

