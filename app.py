import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager
from models import db, User # Importa a partir do models.py

app = Flask(__name__)

# --- Configuração ---
# Usa a DATABASE_URL do Render, ou um ficheiro local para testes
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback') # Use uma variável de ambiente para isto

# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)

# --- Rotas da API ---

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Nenhum dado recebido."}), 400

    # ✅ CORRIGIDO: Agora lê o campo 'name' do JSON recebido.
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Nome, email ou senha em falta."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Este email já está registado."}), 409

    hashed_password = generate_password_hash(password)
    
    # ✅ CORRIGIDO: Passa o 'name' ao criar o novo utilizador.
    new_user = User(name=name, email=email, password_hash=hashed_password)

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": f"Utilizador {name} registado com sucesso!"}), 201
    except Exception as e:
        db.session.rollback()
        # Log do erro para depuração no servidor
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
# (Este bloco não é executado no Render, mas é útil para testes locais)
if __name__ == '__main__':
    with app.app_context():
        # Cria as tabelas se não existirem
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

