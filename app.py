from flask import Flask, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import create_access_token, JWTManager
from models import db, User  # Importa o banco de dados e o modelo User
import os

app = Flask(__name__)

# --- Configuração ---
# Configura o caminho absoluto para o banco de dados SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "sua-chave-secreta-super-segura"  # Mude isso!

# --- Inicialização ---
db.init_app(app)  # Inicializa o banco de dados com a aplicação Flask
jwt = JWTManager(app)

# --- Criação das Tabelas ---
# Garante que as tabelas do banco de dados sejam criadas antes da primeira requisição
with app.app_context():
    db.create_all()

@app.route("/api/auth/register", methods=["POST"])
def register():
    """
    Registra um novo usuário no banco de dados com uma senha criptografada.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email ou senha ausentes."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Este e-mail já está em uso."}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": f"Usuário {email} registrado com sucesso."}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    """
    Processa a tentativa de login de um usuário, verificando as credenciais no banco de dados
    e retornando um token JWT se for bem-sucedido.
    """
    data = request.get_json()
    print(f"Dados de login recebidos: {data}")

    if not data:
        return jsonify({"message": "Nenhum dado recebido."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email ou senha ausentes."}), 400

    # --- LÓGICA CORRIGIDA E CONECTADA AO BANCO DE DADOS ---

    # 1. Encontre o usuário no banco de dados pelo e-mail usando SQLAlchemy.
    user = User.query.filter_by(email=email).first()

    # 2. Verifique se o usuário existe E se a senha está correta.
    if user and check_password_hash(user.password_hash, password):
        # 3. Se as credenciais estiverem corretas, crie um token de acesso JWT.
        access_token = create_access_token(identity=user.email)
        print(f"Login bem-sucedido para {user.email}.")
        return jsonify({
            "message": "Login bem-sucedido!",
            "token": access_token
        }), 200
    else:
        # 4. Se o usuário não existir ou a senha estiver incorreta, retorne um erro 401.
        print(f"Credenciais inválidas para a tentativa de login com o email: {email}.")
        return jsonify({"message": "Credenciais inválidas."}), 401


if __name__ == '__main__':
    # A porta pode ser 5000, 8000, etc.
    app.run(debug=True, port=5000)

