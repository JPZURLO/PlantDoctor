import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from models import db, User, Culture

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['JWT_SECRET_KEY'])


# --- ROTAS DE AUTENTICAÇÃO E REGISTO ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    if not name or not email or not password:
        return jsonify({"message": "Nome, email ou senha em falta."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Este e-mail já está registado. Por favor, tente fazer login."}), 409
    hashed_password = generate_password_hash(password)
    new_user = User(name=name, email=email, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": f"Utilizador {name} registado com sucesso!"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"message": "Email ou senha em falta."}), 400
    
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(identity=user.id)
        has_cultures = len(user.cultures) > 0
        
        return jsonify({
            "message": "Login bem-sucedido!",
            "token": access_token,
            "has_cultures": has_cultures
        }), 200
    else:
        return jsonify({"message": "Credenciais inválidas."}), 401

# --- ROTAS DE CULTURAS ---
@app.route("/api/cultures", methods=["GET"])
@jwt_required()
def get_cultures():
    try:
        all_cultures = Culture.query.order_by(Culture.name).all()
        return jsonify([culture.to_dict() for culture in all_cultures]), 200
    except Exception as e:
        app.logger.error(f"Erro ao buscar culturas: {e}")
        return jsonify({"message": "Erro interno ao buscar culturas."}), 500

@app.route("/api/user/cultures", methods=["POST"])
@jwt_required()
def save_user_cultures():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
    data = request.get_json()
    culture_ids = data.get('culture_ids')
    if not isinstance(culture_ids, list):
        return jsonify({"message": "Dados inválidos. 'culture_ids' deve ser uma lista de IDs."}), 400
    user.cultures.clear()
    for culture_id in culture_ids:
        culture = Culture.query.get(culture_id)
        if culture:
            user.cultures.append(culture)
    db.session.commit()
    return jsonify({"message": "Culturas guardadas com sucesso!"}), 200

@app.route("/api/user/my-cultures", methods=["GET"])
@jwt_required()
def get_my_cultures():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
    
    return jsonify([culture.to_dict() for culture in user.cultures]), 200

# --- FUNÇÃO PARA POPULAR O BANCO DE DADOS ---
def seed_data():
    if Culture.query.first() is None:
        cultures_to_add = [
            Culture(name="Milho", image_url="https://placehold.co/128x128/FBC02D/FFFFFF?text=Milho"),
            Culture(name="Café", image_url="https://placehold.co/128x128/5D4037/FFFFFF?text=Caf%C3%A9"),
            Culture(name="Soja", image_url="https://placehold.co/128x128/689F38/FFFFFF?text=Soja"),
            Culture(name="Cana de Açúcar", image_url="https://placehold.co/128x128/7CB342/FFFFFF?text=Cana"),
            Culture(name="Trigo", image_url="https://placehold.co/128x128/F57C00/FFFFFF?text=Trigo"),
            Culture(name="Algodão", image_url="https://placehold.co/128x128/ECEFF1/000000?text=Algod%C3%A3o"),
            Culture(name="Arroz", image_url="https://placehold.co/128x128/E0E0E0/000000?text=Arroz"),
            Culture(name="Feijão", image_url="https://placehold.co/128x128/3E2723/FFFFFF?text=Feij%C3%A3o"),
            Culture(name="Mandioca", image_url="https://placehold.co/128x128/8D6E63/FFFFFF?text=Mandioca"),
            Culture(name="Cacau", image_url="https://placehold.co/128x128/4E342E/FFFFFF?text=Cacau"),
            Culture(name="Banana", image_url="https://placehold.co/128x128/FFEE58/000000?text=Banana"),
            Culture(name="Laranja", image_url="https://placehold.co/128x128/FB8C00/FFFFFF?text=Laranja")
        ]
        db.session.bulk_save_objects(cultures_to_add)
        db.session.commit()

# --- BLOCO DE EXECUÇÃO PRINCIPAL ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

