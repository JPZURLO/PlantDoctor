import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from models import db, User # Importa a partir do models.py

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')

# --- Configuração do Flask-Mail ---
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


# --- ROTAS PARA RECUPERAÇÃO DE SENHA ---

@app.route("/api/auth/request-password-reset", methods=["GET"])
def request_password_reset():
    email = request.args.get('email')
    
    if not email:
        return jsonify({"message": "Email em falta."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        # Resposta genérica para não revelar se um e-mail existe ou não
        return jsonify({"message": "Se o e-mail estiver registado, receberá um link para redefinir a senha."}), 200

    token = serializer.dumps(user.email, salt='password-reset-salt')
    
    # ✅✅✅ CORREÇÃO APLICADA AQUI ✅✅✅
    # Adicionamos o parâmetro '&email=' ao final da URL
    reset_url = f"plantdoctor://reset-password?token={token}&email={user.email}"

    html_body = render_template_string("""
        <p>Olá {{ name }},</p>
        <p>Recebemos um pedido para redefinir a sua senha. Por favor, clique no botão abaixo para continuar:</p>
        <p style="margin-top: 20px; margin-bottom: 20px;">
            <a href="{{ link }}" style="padding: 12px 25px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; font-size: 16px;">Redefinir Senha</a>
        </p>
        <p>Se não pediu esta alteração, pode ignorar este e-mail.</p>
        <p>O link expira em 1 hora.</p>
    """, name=user.name, link=reset_url)

    msg = Message("Redefinição de Senha - Plant Doctor", recipients=[user.email], html=html_body)
    
    try:
        mail.send(msg)
        return jsonify({"message": "Se o e-mail estiver registado, receberá um link para redefinir a senha."}), 200
    except Exception as e:
        app.logger.error(f"Erro ao enviar e-mail: {e}")
        return jsonify({"message": "Erro ao enviar e-mail de recuperação."}), 500

@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password') # No Android, o campo é 'newPassword', mas o @SerializedName cuida disso.
    
    if not token or not new_password:
        return jsonify({"message": "Token ou nova senha em falta."}), 400
    try:
        # O link expira em 1 hora (3600 segundos)
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        return jsonify({"message": "Token inválido ou expirado."}), 401
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
    
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Senha atualizada com sucesso!"}), 200


# --- Bloco de Execução ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # A porta 10000 é a padrão que o Render espera.
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
