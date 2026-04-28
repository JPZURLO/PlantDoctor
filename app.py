import os
from flask import Flask, request, jsonify, url_for, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func, Enum as SQLAlchemyEnum, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import threading
import requests  # Para a API do Brevo
import enum

# ===================================================================
# 1. DEFINIÇÃO DOS MODELOS (models.py)
# ===================================================================

db = SQLAlchemy()

# Tabela de associação
user_cultures = db.Table('user_cultures',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('culture_id', db.Integer, db.ForeignKey('culture.id'), primary_key=True)
)

class UserType(enum.Enum):
    COMMON = "COMMON"
    ADMIN = "ADMIN"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    user_type = db.Column(SQLAlchemyEnum(UserType), nullable=False, default=UserType.COMMON)

    cultures = db.relationship('Culture', secondary=user_cultures, lazy='subquery',
                                backref=db.backref('interested_users', lazy=True))
    
    planted_cultures = db.relationship('PlantedCulture', backref='user', lazy=True, cascade="all, delete-orphan")
    
    diagnosis_history = db.relationship('DiagnosisHistory', backref='user', lazy=True)
    doubts = db.relationship('Doubt', backref='author', lazy=True)
    suggestions = db.relationship('Suggestion', backref='author', lazy=True)
    edit_history = db.relationship('UserEditHistory', foreign_keys='UserEditHistory.edited_user_id', backref='edited_user')
    reset_tokens = db.relationship('PasswordResetToken', backref='user', lazy=True)
    alerts = db.relationship('Alert', backref='user', lazy=True) # Relacionamento de alertas

    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'user_type': self.user_type.name
        }

class Culture(db.Model):
    __tablename__ = 'culture'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    cycle_days = db.Column(db.Integer, nullable=False, default=90)
    
    planted_instances = db.relationship('PlantedCulture', backref='culture')
    diagnosis_history = db.relationship('DiagnosisHistory', backref='culture')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_url': self.image_url,
            'cycle_days': self.cycle_days 
        }

class PlantedCulture(db.Model):
    __tablename__ = 'planted_culture'
    
    id = db.Column(db.Integer, primary_key=True)
    planting_date = db.Column(db.Date, nullable=False)
    predicted_harvest_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    culture_id = db.Column(db.Integer, db.ForeignKey('culture.id'), nullable=False)
    
    history_events = db.relationship('HistoryEvent', backref='planted_culture', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'planting_date': self.planting_date.isoformat(),
            'predicted_harvest_date': self.predicted_harvest_date.isoformat() if self.predicted_harvest_date else None,
            'notes': self.notes,
            'user_id': self.user_id,
            'culture': self.culture.to_dict(),
            'history_events': [event.to_dict() for event in self.history_events]
        }

class EventType(enum.Enum):
    PLANTIO = "PLANTIO"
    ADUBAGEM = "ADUBAGEM"
    AGROTOXICO = "AGROTOXICO"
    VENENO = "VENENO"
    COLHEITA = "COLHEITA"
    OUTRO = "OUTRO"

class HistoryEvent(db.Model):
    __tablename__ = 'history_event'

    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.DateTime, nullable=False, default=func.now())
    event_type = db.Column(SQLAlchemyEnum(EventType), nullable=False)
    observation = db.Column(db.Text, nullable=True)
    
    planted_culture_id = db.Column(db.Integer, db.ForeignKey('planted_culture.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'event_date': self.event_date.isoformat(),
            'event_type': self.event_type.name,
            'observation': self.observation
        }

class DiagnosisHistory(db.Model):
    __tablename__ = 'diagnosis_history'
    
    id = db.Column(db.Integer, primary_key=True)
    diagnosis_name = db.Column(db.String(255), nullable=False)
    observation = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(512), nullable=False)
    analysis_date = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    culture_id = db.Column(db.Integer, db.ForeignKey('culture.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'diagnosis_name': self.diagnosis_name,
            'observation': self.observation,
            'photo_path': self.photo_path,
            'analysis_date': self.analysis_date.isoformat(),
            'culture_name': self.culture.name,
            'culture_id': self.culture_id,
            'user_id': self.user_id
        }

class Doubt(db.Model):
    __tablename__ = 'doubts'

    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    
    reply_text = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'question_text': self.question_text,
            'created_at': self.created_at.isoformat(),
            'author_name': 'Anônimo' if self.is_anonymous else self.author.name,
            'reply_text': self.reply_text,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None
        }

class Suggestion(db.Model):
    __tablename__ = 'suggestions'

    id = db.Column(db.Integer, primary_key=True)
    suggestion_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    
    reply_text = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'suggestion_text': self.suggestion_text,
            'created_at': self.created_at.isoformat(),
            'author_name': 'Anônimo' if self.is_anonymous else self.author.name,
            'reply_text': self.reply_text,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None
        }

class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id
        }

class UserEditHistory(db.Model):
    __tablename__ = 'user_edit_history'
    
    id = db.Column(db.Integer, primary_key=True)
    edited_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    edited_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_changed = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    editor = db.relationship('User', foreign_keys=[edited_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'field_changed': self.field_changed,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_at': self.changed_at.isoformat(),
            'editor_name': self.editor.name
        }

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(512), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id}>"

# ===================================================================
# 2. INÍCIO DA CONFIGURAÇÃO DO APP (app.py)
# ===================================================================

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')
app.config['RESET_TOKEN_EXPIRES'] = timedelta(hours=1)

# --- CONFIGURAÇÃO BREVO/E-MAIL (API HTTP) ---
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
SENDER_EMAIL = os.environ.get('MAIL_SENDER_EMAIL')
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
# --- FIM DA CONFIGURAÇÃO DE E-MAIL ---


# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)


# --- FUNÇÕES AUXILIARES DE E-MAIL (BREVO ASSÍNCRONO) ---
def send_brevo_email_async(recipient_email, subject, html_content):
    """Função que envia o e-mail via API do Brevo (HTTPS), rodando em uma thread."""
    brevo_api_key = os.environ.get('BREVO_API_KEY')
    sender_email = os.environ.get('MAIL_SENDER_EMAIL')
    bcc_email = "jpzurlo.jz@gmail.com" 
    
    if not brevo_api_key or not sender_email:
        # Use app.logger se o contexto do app estiver disponível, senão print
        print("ERRO: Configuração Brevo (API Key ou SENDER_EMAIL) ausente.")
        return

    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    
    data = {
        "sender": {"name": "Plant Doctor", "email": sender_email},
        "to": [{"email": recipient_email}],
        "subject": subject,
        "htmlContent": html_content,
        "bcc": [{"email": bcc_email}] 
    }

    try:
        response = requests.post(BREVO_API_URL, headers=headers, json=data)
        response.raise_for_status() 
        print(f">>> Brevo E-mail enviado (c/ BCC). Status: {response.status_code}")

    except requests.exceptions.HTTPError as e:
        error_details = e.response.text
        print(f"ERRO DE ENVIO BREVO: {e.response.status_code}. Detalhe: {error_details}")
    except Exception as e:
        print(f"Erro inesperado no envio Brevo: {e}")


def send_welcome_email(recipient_email, name): 
    """Lógica do e-mail de Boas-Vindas."""
    subject = "🌱 Bem-vindo(a) ao Plant Doctor!"
    html_content = f"""
        <html><body>
            <h1>Bem-vindo(a) ao Plant Doctor, {name}!</h1>
            <p>Seu registro foi concluído com sucesso. Estamos felizes por você se juntar à nossa comunidade.</p>
            <hr>
            <h2>Detalhes de Acesso:</h2>
            <p><strong>Seu E-mail de Acesso:</strong> {recipient_email}</p>
            <p>Use este e-mail e a senha que você acabou de criar para fazer login no aplicativo.</p>
            <hr>
        </body></html>
    """
    threading.Thread(target=send_brevo_email_async, args=[recipient_email, subject, html_content]).start()


def send_reset_email(recipient_email, token):
    """Lógica do e-mail de Recuperação de Senha (com Deep Link)."""
    
    APP_RESET_URL = f"plantdoctor://reset-password?token={token}"   

    subject = "Recuperação de Senha - Plant Doctor"
    html_content = f"""
        <html><body>
            <h1>Recuperação de Senha</h1>
            <p>Você solicitou uma redefinição de senha para o e-mail: <strong>{recipient_email}</strong></p>
            <p>Clique no link abaixo para redefinir sua senha no aplicativo:</p>
            <p><a href="{APP_RESET_URL}">Redefinir Senha</a></p>
            <p>Se você não solicitou esta redefinição, ignore este e-mail.</p>
            <p>Este link expira em 1 hora.</p>
        </body></html>
    """
    threading.Thread(target=send_brevo_email_async, args=[recipient_email, subject, html_content]).start()

# --- FIM DAS FUNÇÕES DE E-MAIL ---


# --- DECORATOR PARA PROTEGER ROTAS DE ADMIN ---
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            current_user_id = int(get_jwt_identity())
            user = User.query.get(current_user_id)
            if user and user.user_type == UserType.ADMIN:
                return fn(*args, **kwargs)
            else:
                return jsonify(message="Acesso restrito a administradores."), 403
        return decorator
    return wrapper

# --- FUNÇÃO AUXILIAR PARA REGISTRAR HISTÓRICO DE ADMIN ---
def log_user_change(edited_user, admin_user_id, field, old_value, new_value):
    if str(old_value) != str(new_value):
        history_entry = UserEditHistory(
            edited_user_id=edited_user.id,
            edited_by_user_id=admin_user_id,
            field_changed=field,
            old_value=str(old_value),
            new_value=str(new_value)
        )
        db.session.add(history_entry)

# --- FUNÇÃO PARA POPULAR O BANCO DE DADOS ---
def seed_data():
    if Culture.query.first() is None:
        print(">>> Base de dados vazia. A popular com culturas...")
        cultures_to_add = [
            Culture(name="Milho", image_url="https://marketplace.canva.com/Z5ct4/MAFCw6Z5ct4/1/tl/canva-corn-cobs-isolated-png-MAFCw6Z5ct4.png", cycle_days=120),
            Culture(name="Café", image_url="https://static.vecteezy.com/system/resources/previews/012/986/668/non_2x/coffee-bean-logo-icon-free-png.png", cycle_days=1095),
            Culture(name="Soja", image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQJ4kcZy-KdR8mAkIWlxhYmND5CsvN5WwG-pQ&s", cycle_days=110),
            Culture(name="Cana de Açúcar", image_url="https://i.pinimg.com/736x/d5/d0/ea/d5d0eaaa6a08dfee042f98e265ea7f87.jpg", cycle_days=365),
            Culture(name="Trigo", image_url="https://img.freepik.com/vetores-premium/ilustracao-de-icone-de-vetor-de-logotipo-de-trigo_833786-135.jpg", cycle_days=150),
            Culture(name="Algodão", image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRjmTW5RRENEI3nrlt8Ry1nsTzrGVpfx0oj-Q&s", cycle_days=180),
            Culture(name="Arroz", image_url="https://img.freepik.com/vetores-premium/icone-de-arroz_609277-3890.jpg", cycle_days=130),
            Culture(name="Feijão", image_url="httpsS://img.freepik.com/vetores-premium/ilustracao-vetorial-de-feijao-preto-de-alta-qualidade-vetor-de-icone-de-feijao-preto-isolado-design-plano-moderno_830337-39.jpg", cycle_days=90),
            Culture(name="Mandioca", image_url="https://media.istockphoto.com/id/1353955911/pt/vetorial/cassava-root.jpg?s=612x612&w=0&k=20&c=obWmGbXBnj46d4KbNNKW7DYMfWkAngFs9gRKh4E3OBg=", cycle_days=270),
            Culture(name="Cacau", image_url="https://previews.123rf.com/images/pchvector/pchvector2211/pchvector221102749/194589566-chocolate-cocoa-bean-on-branch-with-leaves-cartoon-illustration-cacao-beans-with-leaves-on-tree.jpg", cycle_days=1825),
            Culture(name="Banana", image_url="httpsa://png.pngtree.com/png-clipart/20230928/original/pngtree-banana-logo-icon-design-fruit-tropical-yellow-vector-png-image_12898187.png", cycle_days=365),
            Culture(name="Laranja", image_url="https://cdn-icons-png.flaticon.com/512/5858/5858316.png", cycle_days=1095)
        ]
        db.session.bulk_save_objects(cultures_to_add)
        db.session.commit()
        print(f">>> {len(cultures_to_add)} culturas adicionadas.")
    else:
        print(">>> Base de dados já populada. Nenhuma ação necessária.")


# ===================================================================
# 3. DEFINIÇÃO DAS ROTAS (endpoints da API)
# ===================================================================

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({"message": "Nome, email ou senha em falta."}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Este e-mail já está registado."}), 409
    
    hashed_password = generate_password_hash(password)
    
    new_user = User(name=name, email=email, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    
    send_welcome_email(email, name)
    
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
        access_token = create_access_token(identity=str(user.id))
        has_cultures = len(user.cultures) > 0
        
        return jsonify({
            "message": "Login bem-sucedido!",
            "token": access_token,
            "has_cultures": has_cultures,
            "user_role": user.user_type.name
        }), 200
    else:
        return jsonify({"message": "Credenciais inválidas."}), 401

@app.route("/api/auth/request-password-reset", methods=["GET"])
def request_password_reset():
    email = request.args.get('email')
    
    if not email:
        return jsonify({"message": "Email em falta."}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({"message": "Se o e-mail estiver registado, receberá um link."}), 200

    token = create_access_token(
        identity=str(user.id), 
        expires_delta=app.config['RESET_TOKEN_EXPIRES']
    )
    expiration = datetime.utcnow() + app.config['RESET_TOKEN_EXPIRES']
    
    new_token_entry = PasswordResetToken(user_id=user.id, token=token, expires_at=expiration)
    
    try:
        db.session.add(new_token_entry)
        db.session.commit()
        send_reset_email(user.email, token)
        return jsonify({"message": "Se o e-mail estiver registado, receberá um link."}), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao gerar token de reset para {user.email}: {e}")
        return jsonify({"message": "Erro interno do servidor ao processar o pedido."}), 500

@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')
    
    if not token or not new_password:
        return jsonify({"message": "Token e nova senha são obrigatórios."}), 400

    PasswordResetToken.query.filter(
        PasswordResetToken.expires_at < datetime.utcnow()
    ).delete(synchronize_session='fetch')
    
    token_entry = PasswordResetToken.query.filter_by(token=token).first()

    if not token_entry:
        return jsonify({"message": "Link inválido. Tente novamente."}), 401
    
    if token_entry.expires_at < datetime.utcnow():
        db.session.delete(token_entry)
        db.session.commit()
        return jsonify({"message": "Link expirado. Tente novamente."}), 401

    user = User.query.get(token_entry.user_id)
    if not user:
        return jsonify({"message": "Usuário não encontrado."}), 404
        
    user.password_hash = generate_password_hash(new_password)
    db.session.delete(token_entry) 
    db.session.commit()

    return jsonify({"message": "Senha redefinida com sucesso!"}), 200

# --- ROTAS DE ADMINISTRAÇÃO ---
@app.route("/api/admin/users", methods=["GET"])
@admin_required()
def get_all_users():
    users = User.query.order_by(User.name).all()
    return jsonify([user.to_dict() for user in users]), 200

@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_required()
def update_user(user_id):
    admin_id = int(get_jwt_identity())
    user_to_update = User.query.get(user_id)
    if not user_to_update:
        return jsonify(message="Usuário não encontrado."), 404
    
    data = request.get_json()

    if 'name' in data:
        log_user_change(user_to_update, admin_id, 'name', user_to_update.name, data['name'])
        user_to_update.name = data['name']
    
    if 'email' in data:
        log_user_change(user_to_update, admin_id, 'email', user_to_update.email, data['email'])
        user_to_update.email = data['email']
        
    if 'password' in data and data['password']:
        log_user_change(user_to_update, admin_id, 'password', 'N/A', 'Atualizada')
        user_to_update.password_hash = generate_password_hash(data['password'])

    if 'user_type' in data:
        new_role_str = data.get('user_type', '').upper()
        try:
            new_role = UserType[new_role_str]
            log_user_change(user_to_update, admin_id, 'user_type', user_to_update.user_type.name, new_role.name)
            user_to_update.user_type = new_role
        except KeyError:
            return jsonify(message="Tipo de usuário inválido."), 400
            
    db.session.commit()
    return jsonify(user_to_update.to_dict()), 200

@app.route("/api/admin/users/<int:user_id>/history", methods=["GET"])
@admin_required()
def get_user_history(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify(message="Usuário não encontrado."), 404
    
    history = UserEditHistory.query.filter_by(edited_user_id=user_id).order_by(UserEditHistory.changed_at.desc()).all()
    return jsonify([entry.to_dict() for entry in history]), 200


# --- ROTAS DE CULTURAS (GERAL) ---
@app.route("/api/cultures", methods=["GET"])
@jwt_required()
def get_cultures():
    try:
        all_cultures = Culture.query.order_by(Culture.name).all()
        return jsonify([culture.to_dict() for culture in all_cultures]), 200
    except Exception as e:
        app.logger.error(f"Erro ao buscar culturas: {e}")
        return jsonify({"message": "Erro interno ao buscar culturas."}), 500

# --- ROTAS DE CULTURAS DO USUÁRIO (INTERESSES) ---
@app.route("/api/user/cultures", methods=["POST"])
@jwt_required()
def save_user_cultures():
    try:
        user_id = int(get_jwt_identity())
    except ValueError:
        return jsonify({"message": "ID de utilizador inválido no token."}), 400

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
    try:
        user_id = int(get_jwt_identity())
    except ValueError:
        return jsonify({"message": "ID de utilizador inválido no token."}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
    
    return jsonify([culture.to_dict() for culture in user.cultures]), 200

# --- ROTAS DE GESTÃO DE PLANTIOS ---
@app.route("/api/planted-cultures", methods=["POST"])
@jwt_required()
def add_planted_culture():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    culture_id = data.get('culture_id')
    planting_date_str = data.get('planting_date')
    notes = data.get('notes')

    if not culture_id or not planting_date_str:
        return jsonify({"message": "culture_id e planting_date são obrigatórios."}), 400

    try:
        planting_date = datetime.strptime(planting_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    culture = Culture.query.get(culture_id)
    if not culture:
        return jsonify({"message": "Cultura não encontrada."}), 404
    
    predicted_harvest_date = planting_date + timedelta(days=culture.cycle_days)
    
    new_planting = PlantedCulture(
        user_id=user_id,
        culture_id=culture_id,
        planting_date=planting_date,
        predicted_harvest_date=predicted_harvest_date,
        notes=notes
    )
    db.session.add(new_planting)
    db.session.commit()

    return jsonify(new_planting.to_dict()), 201

@app.route("/api/planted-cultures", methods=["GET"])
@jwt_required()
def get_user_planted_cultures():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
        
    return jsonify([planting.to_dict() for planting in user.planted_cultures]), 200

@app.route("/api/planted-cultures/<int:planted_culture_id>/history", methods=["POST"])
@jwt_required()
def add_history_event(planted_culture_id):
    user_id = int(get_jwt_identity())
    
    planting = PlantedCulture.query.filter_by(id=planted_culture_id, user_id=user_id).first()
    if not planting:
        return jsonify({"message": "Plantio não encontrado ou não pertence a este utilizador."}), 404

    data = request.get_json()
    event_type_str = data.get('event_type')
    observation = data.get('observation')

    if not event_type_str:
        return jsonify({"message": "event_type é obrigatório."}), 400

    try:
        event_type = EventType[event_type_str.upper()]
    except KeyError:
        return jsonify({"message": f"Tipo de evento inválido: {event_type_str}"}), 400

    new_event = HistoryEvent(
        planted_culture_id=planted_culture_id,
        event_type=event_type,
        observation=observation
    )
    db.session.add(new_event)
    db.session.commit()
    
    return jsonify(new_event.to_dict()), 201

# --- ROTAS DE DIAGNÓSTICO (IA) ---
@app.route("/api/diagnosis-history", methods=["POST"])
@jwt_required()
def save_diagnosis():
    """Salva um novo resultado de diagnóstico da IA."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    culture_id = data.get('culture_id')
    diagnosis_name = data.get('diagnosis_name')
    observation = data.get('observation')
    photo_path = data.get('photo_path')

    if not culture_id or not diagnosis_name or not photo_path:
        return jsonify({"message": "culture_id, diagnosis_name e photo_path são obrigatórios."}), 400

    culture = Culture.query.get(culture_id)
    if not culture:
        return jsonify({"message": "Cultura não encontrada."}), 404
        
    try:
        new_diagnosis = DiagnosisHistory(
            user_id=user_id,
            culture_id=culture_id,
            diagnosis_name=diagnosis_name,
            observation=observation,
            photo_path=photo_path
        )
        db.session.add(new_diagnosis)
        db.session.commit()
        
        return jsonify(new_diagnosis.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        # Use app.logger para registrar o erro no servidor
        app.logger.error(f"Erro ao salvar diagnóstico: {e}")
        return jsonify({"message": "Erro interno ao salvar o diagnóstico."}), 500

@app.route("/api/cultures/<int:culture_id>/diagnosis-history", methods=["GET"])
@jwt_required()
def get_diagnosis_history(culture_id):
    """Busca o histórico de diagnósticos de um usuário para uma cultura específica."""
    user_id = int(get_jwt_identity())
    
    try:
        history = DiagnosisHistory.query.filter_by(
            user_id=user_id,
            culture_id=culture_id
        ).order_by(DiagnosisHistory.analysis_date.desc()).all()
        
        return jsonify([item.to_dict() for item in history]), 200
    except Exception as e:
        app.logger.error(f"Erro ao buscar histórico de diagnóstico: {e}")
        return jsonify({"message": "Erro interno ao buscar histórico."}), 500


# --- ROTAS DE DÚVIDAS ---
@app.route("/api/doubts", methods=["POST"])
@jwt_required()
def post_doubt():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    question_text = data.get('question_text')
    is_anonymous = data.get('is_anonymous', False)

    if not question_text:
        return jsonify({"message": "O texto da pergunta é obrigatório."}), 400

    new_doubt = Doubt(
        question_text=question_text,
        user_id=user_id,
        is_anonymous=is_anonymous
    )
    db.session.add(new_doubt)
    
    # --- LOGICA DE NOTIFICAÇÃO PARA ADMIN ---
    # Busca todos os administradores no banco
    admins = User.query.filter_by(user_type=UserType.ADMIN).all()
    for admin in admins:
        new_alert = Alert(
            title="Nova Dúvida",
            message=f"Uma nova dúvida foi postada: {question_text[:20]}...",
            user_id=admin.id
        )
        db.session.add(new_alert)
    # ----------------------------------------

    db.session.commit()
    return jsonify(new_doubt.to_dict()), 201

@app.route("/api/doubts", methods=["GET"])
@jwt_required()
def get_doubts():
    all_doubts = Doubt.query.order_by(Doubt.created_at.desc()).all()
    return jsonify([doubt.to_dict() for doubt in all_doubts]), 200

# --- ROTA DE RANKING ---
@app.route("/api/cultures/ranking", methods=["GET"])
@jwt_required()
def get_culture_ranking():
    try:
        ranking_data = db.session.query(
            Culture.name,
            func.count(PlantedCulture.id).label('count')
        ).join(Culture, PlantedCulture.culture_id == Culture.id).group_by(Culture.name).order_by(func.count(PlantedCulture.id).desc()).all()
        result = [{"name": name, "count": count} for name, count in ranking_data]
        return jsonify(result), 200
    except Exception as e:
        app.logger.error(f"Erro ao calcular ranking: {e}")
        return jsonify({"message": "Erro interno ao gerar o ranking."}), 500

# ROTAS DE SUGESTÕES
@app.route("/api/suggestions", methods=["POST"])
@jwt_required()
def post_suggestion():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    suggestion_text = data.get('suggestion_text')
    is_anonymous = data.get('is_anonymous', False)

    if not suggestion_text:
        return jsonify({"message": "O texto da sugestão é obrigatório."}), 400

    new_suggestion = Suggestion(
        suggestion_text=suggestion_text,
        user_id=user_id,
        is_anonymous=is_anonymous
    )
    db.session.add(new_suggestion)
    
    # --- NOVO: Notificar todos os Admins sobre a nova sugestão ---
    admins = User.query.filter_by(user_type=UserType.ADMIN).all()
    for admin in admins:
        resumo_sugestao = suggestion_text[:30] + "..." if len(suggestion_text) > 30 else suggestion_text
        new_alert = Alert(
            title="Nova Melhoria/Sugestão",
            message=f"Um usuário enviou uma sugestão: '{resumo_sugestao}'",
            user_id=admin.id
        )
        db.session.add(new_alert)

    db.session.commit()
    return jsonify(new_suggestion.to_dict()), 201

@app.route("/api/suggestions", methods=["GET"])
def get_suggestions():
    all_suggestions = Suggestion.query.order_by(Suggestion.created_at.desc()).all()
    return jsonify([suggestion.to_dict() for suggestion in all_suggestions]), 200

# ===================================================================
# 4. ROTAS DE EXPLICAÇÃO DE DOENÇAS
# ===================================================================

disease_explanations = {
    "Algodao_lagarta_do_cartucho": {
        "identificacao": "A lagarta-do-cartucho é uma praga que ataca as folhas e brotos do algodão, deixando furos e restos de tecido vegetal.",
        "prevencao": "Realizar monitoramento constante e usar armadilhas luminosas para detectar adultos.",
        "tratamento": "Aplicar inseticidas biológicos à base de Bacillus thuringiensis ou produtos químicos seletivos em caso de infestação severa."
    },
    "Algodao_Mancha_Bacteriana": {
        "identificacao": "A mancha bacteriana causa pequenas lesões escuras nas folhas e pode afetar maçãs e ramos.",
        "prevencao": "Evitar irrigação por aspersão e utilizar sementes certificadas.",
        "tratamento": "Aplicar produtos cúpricos e eliminar restos culturais após a colheita."
    },
    "Algodao_pulgao_do_algodoeiro": {
        "identificacao": "O pulgão suga a seiva das folhas jovens, causando encarquilhamento e excreção de mela.",
        "prevencao": "Evitar adubação excessiva com nitrogênio e monitorar semanalmente as lavouras.",
        "tratamento": "Utilizar inimigos naturais como joaninhas ou aplicar inseticidas seletivos se necessário."
    },
    "Algodao_saudavel": {
        "identificacao": "Planta de algodão saudável, sem sintomas visíveis de pragas ou doenças.",
        "prevencao": "Manter práticas agrícolas adequadas e rotação de culturas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Arroz_Mancha_parda": {
        "identificacao": "Manchas pardas nas folhas e grãos causadas pelo fungo Bipolaris oryzae.",
        "prevencao": "Evitar excesso de nitrogênio e usar sementes tratadas.",
        "tratamento": "Aplicar fungicidas específicos e realizar rotação de culturas."
    },
    "Arroz_Mancha_Bacteriana_das_Folhas": {
        "identificacao": "Manchas aquosas que evoluem para áreas amareladas e secas.",
        "prevencao": "Usar variedades resistentes e evitar irrigação excessiva.",
        "tratamento": "Aplicar produtos à base de cobre e eliminar plantas infectadas."
    },
    "Arroz_Carvão_das_Folhas": {
        "identificacao": "Provoca manchas escuras e enrugamento nas folhas.",
        "prevencao": "Usar sementes sadias e evitar umidade alta.",
        "tratamento": "Tratar sementes e pulverizar fungicidas triazóis conforme recomendação técnica."
    },
    "Arroz_saudavel": {
        "identificacao": "Planta de arroz saudável, sem sinais de doença.",
        "prevencao": "Manter adubação equilibrada e monitorar a umidade do solo.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Banana_sigatoka": {
        "identificacao": "Doença fúngica que provoca listras amarelas e depois manchas escuras nas folhas.",
        "prevencao": "Manter espaçamento adequado e eliminar folhas infectadas.",
        "tratamento": "Aplicar fungicidas sistêmicos e realizar podas sanitárias."
    },
    "Banana_Black_Sigatoka_Disease": {
        "identificacao": "Variante severa da sigatoka, causando necrose nas folhas e redução drástica da produção.",
        "prevencao": "Usar variedades resistentes e boa drenagem no solo.",
        "tratamento": "Aplicar fungicidas sistêmicos em rotação para evitar resistência."
    },
    "Banana_saudavel": {
        "identificacao": "Bananeira saudável e vigorosa, sem presença de manchas ou pragas.",
        "prevencao": "Manter controle fitossanitário e nutrição equilibrada.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Banana_Moko_Disease": {
        "identificacao": "Doença bacteriana que causa murcha e escurecimento interno do pseudocaule.",
        "prevencao": "Usar mudas sadias e evitar ferramentas contaminadas.",
        "tratamento": "Erradicar plantas infectadas e desinfetar equipamentos."
    },
    "Cafe_Ferrugem": {
        "identificacao": "Doença causada pelo fungo Hemileia vastatrix, com manchas alaranjadas na face inferior das folhas.",
        "prevencao": "Usar cultivares resistentes e realizar podas de aeração.",
        "tratamento": "Aplicar fungicidas cúpricos preventivamente e manter manejo equilibrado."
    },
    "Cafe_bicho_mineiro": {
        "identificacao": "Inseto que perfura as folhas, deixando galerias secas e esbranquiçadas.",
        "prevencao": "Monitorar a lavoura e incentivar inimigos naturais.",
        "tratamento": "Aplicar inseticidas seletivos quando houver alta infestação."
    },
    "Cafe_saudavel": {
        "identificacao": "Planta de café saudável e produtiva, sem sinais de pragas ou doenças.",
        "prevencao": "Manter poda, adubação e irrigação adequadas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Milho_Blight": {
        "identificacao": "Causa manchas alongadas e necrose nas folhas.",
        "prevencao": "Evitar alta densidade de plantio e usar sementes tratadas.",
        "tratamento": "Aplicar fungicidas e fazer rotação de culturas."
    },
    "Milho_Common_Rust": {
        "identificacao": "Fungos que formam pústulas avermelhadas nas folhas.",
        "prevencao": "Usar variedades resistentes e evitar plantios fora de época.",
        "tratamento": "Aplicar fungicidas preventivos quando houver condições favoráveis."
    },
    "Milho_Healthy": {
        "identificacao": "Milho saudável, com folhas verdes e sem sinais de infecção.",
        "prevencao": "Práticas agrícolas equilibradas e controle preventivo.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Soja_Caterpillar": {
        "identificacao": "Lagartas que se alimentam das folhas e vagens da soja.",
        "prevencao": "Monitorar semanalmente e manter controle biológico ativo.",
        "tratamento": "Usar inseticidas biológicos ou químicos seletivos conforme infestação."
    },
    "Soja_Healthy": {
        "identificacao": "Soja saudável, sem sintomas de pragas ou doenças.",
        "prevencao": "Manter bom manejo de solo e rotação de culturas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Natural Images": {
        "mensagem": "A imagem enviada não representa nenhuma cultura agrícola. Por favor, tire uma nova foto da planta."
    }
}

@app.route('/api/disease-info/<disease_name>', methods=['GET'])
def get_disease_info(disease_name):
    info = disease_explanations.get(disease_name)
    if info:
        return jsonify({"success": True, "disease": disease_name, "info": info})
    else:
        return jsonify({
            "success": False,
            "message": "Doença não encontrada. Por favor, envie uma nova imagem ou tente novamente."
        }), 404

@app.route('/api/explanations/<disease_name>', methods=['GET'])
def get_explanation(disease_name):
    explanation = disease_explanations.get(disease_name)

    if not explanation:
        return jsonify({
            "mensagem": "A imagem enviada não representa nenhuma cultura agrícola. Por favor, tire uma nova foto da planta."
        }), 200

    return jsonify(explanation), 200

# ===================================================================
# ROTAS DE RESPOSTAS E AVISOS (ADMIN E USUÁRIO)
# ===================================================================

@app.route("/api/admin/doubts/<int:doubt_id>/reply", methods=["POST"])
@admin_required()
def reply_to_doubt(doubt_id):
    doubt = Doubt.query.get(doubt_id)
    if not doubt:
        return jsonify({"message": "Dúvida não encontrada."}), 404

    data = request.get_json()
    reply_text = data.get('reply_text')
    
    if not reply_text:
        return jsonify({"message": "O texto da resposta é obrigatório."}), 400

    # Atualiza a dúvida
    doubt.reply_text = reply_text
    doubt.replied_at = func.now()

    # Cria um aviso para o usuário que fez a pergunta
    alert = Alert(
        title="Dúvida Respondida",
        message="Um administrador respondeu à sua dúvida recentemente.",
        user_id=doubt.user_id
    )
    db.session.add(alert)
    db.session.commit()

    return jsonify(doubt.to_dict()), 200

@app.route("/api/admin/suggestions/<int:suggestion_id>/reply", methods=["POST"])
@admin_required()
def reply_to_suggestion(suggestion_id):
    suggestion = Suggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({"message": "Sugestão não encontrada."}), 404

    data = request.get_json()
    reply_text = data.get('reply_text')
    
    if not reply_text:
        return jsonify({"message": "O texto da resposta é obrigatório."}), 400

    # Atualiza a sugestão
    suggestion.reply_text = reply_text
    suggestion.replied_at = func.now()

    # Cria um aviso para o usuário
    alert = Alert(
        title="Sugestão Avaliada",
        message="Um administrador deixou um feedback na sua sugestão.",
        user_id=suggestion.user_id
    )
    db.session.add(alert)
    db.session.commit()

    return jsonify(suggestion.to_dict()), 200

@app.route("/api/alerts", methods=["GET"])
@jwt_required()
def get_user_alerts():
    user_id = int(get_jwt_identity())
    # Busca os avisos do usuário logado, do mais recente pro mais antigo
    alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).all()
    
    return jsonify([alert.to_dict() for alert in alerts]), 200

# --- ROTA SECRETA (Apague depois de usar!) ---
@app.route("/api/hack-admin/<email>")
def hack_admin(email):
    user = User.query.filter_by(email=email).first()
    if user:
        user.user_type = UserType.ADMIN
        db.session.commit()
        return f"Hack ativado com sucesso! {user.name} agora é ADMIN Supremo. 😎"
    return "Falhou: Usuário não encontrado."

# ===================================================================
# 5. INICIALIZADOR PRINCIPAL
# ===================================================================

if __name__ == '__main__':
    with app.app_context():
        # CUIDADO: Isso apaga os dados de todas as tabelas!
        # Use apenas para sincronizar a estrutura agora
        db.drop_all() 
        db.create_all()
        seed_data()
    app.run(debug=True)
    app.run(debug=True)
