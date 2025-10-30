import os
from flask import Flask, request, jsonify, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps
import threading

# NOVO: Usamos requests para a API HTTP do Brevo
import requests

# Importa todos os modelos necessários
from models import (
    db, User, Culture, PlantedCulture, HistoryEvent,
    EventType, Doubt, Suggestion, UserType, UserEditHistory,
    # Presumindo que este modelo existe para rastrear tokens de reset
    PasswordResetToken 
)

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')
# IMPORTANTE: Definir a expiração do token de reset (1 hora)
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
    # Leitura das Variáveis de Ambiente
    brevo_api_key = os.environ.get('BREVO_API_KEY')
    sender_email = os.environ.get('MAIL_SENDER_EMAIL')
    bcc_email = "jpzurlo.jz@gmail.com" # Seu e-mail fixo para BCC
    
    if not brevo_api_key or not sender_email:
        app.logger.error("Configuração Brevo (API Key ou SENDER_EMAIL) ausente. E-mail não enviado.")
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
        app.logger.error(f"ERRO DE ENVIO BREVO: {e.response.status_code}. Detalhe: {error_details}")
    except Exception as e:
        app.logger.error(f"Erro inesperado no envio Brevo: {e}")


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


# app.py (Na seção de FUNÇÕES AUXILIARES DE E-MAIL)

def send_reset_email(recipient_email, token):
    """Lógica do e-mail de Recuperação de Senha (com Deep Link)."""
    
    # ESTA É A URL QUE O SEU APP ANDROID VAI INTERCEPTAR
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
    
# ✅ ROTA DE RECUPERAÇÃO DE SENHA CORRIGIDA
# app.py (Na seção de ROTAS DE AUTENTICAÇÃO)

@app.route("/api/auth/request-password-reset", methods=["GET"])
def request_password_reset():
    # LER DO QUERY PARAMS (GET)
    email = request.args.get('email')
    
    if not email:
        return jsonify({"message": "Email em falta."}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # Retorna sucesso por segurança (evita enumerar usuários)
        return jsonify({"message": "Se o e-mail estiver registado, receberá um link."}), 200

    # 1. Cria um token JWT de acesso (que usaremos como token de reset)
    token = create_access_token(
        identity=str(user.id), 
        expires_delta=app.config['RESET_TOKEN_EXPIRES']
    )
    expiration = datetime.utcnow() + app.config['RESET_TOKEN_EXPIRES']
    
    # 2. Salva o token no banco de dados para validá-lo
    new_token_entry = PasswordResetToken(user_id=user.id, token=token, expires_at=expiration)
    
    try:
        db.session.add(new_token_entry)
        db.session.commit()
        
        # 3. CHAMA a nova função de envio (Brevo API + Deep Link)
        # O envio do e-mail é feito de forma assíncrona por send_reset_email
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
        # Retorna erro se o Android não enviou os dados JSON
        return jsonify({"message": "Token e nova senha são obrigatórios."}), 400

    # ✅ CORREÇÃO 1: Limpar tokens expirados antes de procurar (opcional, mas bom)
    # Isso ajuda a manter o banco de dados limpo
    PasswordResetToken.query.filter(
        PasswordResetToken.expires_at < datetime.utcnow()
    ).delete(synchronize_session='fetch')
    
    # 1. Valida o token e a expiração (busca o token NOVO)
    token_entry = PasswordResetToken.query.filter_by(token=token).first()

    if not token_entry:
        # Se o token não foi encontrado (porque expirou e foi deletado, ou nunca existiu)
        return jsonify({"message": "Link inválido. Tente novamente."}), 401
    
    # Se o token for encontrado, mas o timestamp de expiração já passou:
    if token_entry.expires_at < datetime.utcnow():
        db.session.delete(token_entry)
        db.session.commit()
        return jsonify({"message": "Link expirado. Tente novamente."}), 401

    # 2. Busca o usuário
    user = User.query.get(token_entry.user_id)
    if not user:
        return jsonify({"message": "Usuário não encontrado."}), 404
        
    # 3. Atualiza a senha e remove o token
    user.password_hash = generate_password_hash(new_password)
    db.session.delete(token_entry) # Remove o token para que não possa ser reutilizado
    db.session.commit()

    return jsonify({"message": "Senha redefinida com sucesso!"}), 200

# --- ROTAS DE ADMINISTRAÇÃO ---
@app.route("/api/admin/users", methods=["GET"])
@admin_required()
def get_all_users():
    users = User.query.order_by(User.name).all()
    return jsonify([user.to_dict() for user in users]), 200

# FUNÇÃO AUXILIAR PARA REGISTRAR HISTÓRICO
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
    db.session.commit()
    return jsonify(new_suggestion.to_dict()), 201

@app.route("/api/suggestions", methods=["GET"])
@jwt_required()
def get_suggestions():
    all_suggestions = Suggestion.query.order_by(Suggestion.created_at.desc()).all()
    return jsonify([suggestion.to_dict() for suggestion in all_suggestions]), 200

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
            Culture(name="Feijão", image_url="https://img.freepik.com/vetores-premium/ilustracao-vetorial-de-feijao-preto-de-alta-qualidade-vetor-de-icone-de-feijao-preto-isolado-design-plano-moderno_830337-39.jpg", cycle_days=90),
            Culture(name="Mandioca", image_url="https://media.istockphoto.com/id/1353955911/pt/vetorial/cassava-root.jpg?s=612x612&w=0&k=20&c=obWmGbXBnj46d4KbNNKW7DYMfWkAngFs9gRKh4E3OBg=", cycle_days=270),
            Culture(name="Cacau", image_url="https://previews.123rf.com/images/pchvector/pchvector2211/pchvector221102749/194589566-chocolate-cocoa-bean-on-branch-with-leaves-cartoon-illustration-cacao-beans-with-leaves-on-tree.jpg", cycle_days=1825),
            Culture(name="Banana", image_url="https://png.pngtree.com/png-clipart/20230928/original/pngtree-banana-logo-icon-design-fruit-tropical-yellow-vector-png-image_12898187.png", cycle_days=365),
            Culture(name="Laranja", image_url="https://cdn-icons-png.flaticon.com/512/5858/5858316.png", cycle_days=1095)
        ]
        db.session.bulk_save_objects(cultures_to_add)
        db.session.commit()
        print(f">>> {len(cultures_to_add)} culturas adicionadas.")
    else:
        print(">>> Base de dados já populada. Nenhuma ação necessária.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
