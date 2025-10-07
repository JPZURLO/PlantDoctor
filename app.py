import os
import threading
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps

# --- INÍCIO: BLOCO CORRIGIDO PARA USAR SOMENTE SENDGRID ---

# REMOVIDO: from flask_mail import Mail, Message

# ✅ NOVO: Importa a biblioteca SendGrid
from sendgrid import SendGridAPIClient 


# --- FIM: BLOCO CORRIGIDO ---

# Importa todos os modelos necessários
from models import (
    db, User, Culture, PlantedCulture, HistoryEvent,
    EventType, Doubt, Suggestion, UserType, UserEditHistory
)

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL') 

# CORREÇÃO CRUCIAL: Substitui o formato 'postgres://' (antigo/Render) pelo 'postgresql://' (exigido pelo driver)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Se a variável de ambiente não estiver definida, você pode querer gerar um erro
if not database_url:
    raise RuntimeError("DATABASE_URL não está definida no ambiente.")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

# 🔴 REMOVIDO: app.config['SQLALCHEMY_DATABASE_URI'] = database_url (DUPLICADO)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')

# ❌ REMOVIDAS TODAS AS CONFIGURAÇÕES ANTIGAS DO FLASK-MAIL A PARTIR DAQUI ❌

# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)
# ❌ REMOVIDO: mail = Mail(app) # Remove a inicialização do Flask-Mail

# ----------------------------------------------------
# 📧 FUNÇÕES AUXILIARES DE E-MAIL (AGORA COM SENDGRID) 📧
# ----------------------------------------------------

def send_email_async(app, mail_message):
    """ Envia o e-mail usando a API do SendGrid em um contexto de aplicação. """
    with app.app_context():
        try:
            # 1. Obtém a chave da variável de ambiente
            api_key = os.environ.get('SENDGRID_API_KEY')
            if not api_key:
                app.logger.error("ERRO: SENDGRID_API_KEY não encontrada nas variáveis de ambiente.")
                return

            # 2. Configura o cliente e envia
            sg = SendGridAPIClient(api_key)
            response = sg.send(mail_message)
            
            # 3. Verifica o status da resposta da API do SendGrid
            if response.status_code == 202:
                print("E-mail de boas-vindas enviado com sucesso via SendGrid! Status 202.")
            else:
                # Loga a resposta para diagnóstico em caso de falha (ex: domínio não verificado)
                app.logger.error(f"Falha no envio SendGrid. Status: {response.status_code}, Body: {response.body.decode('utf-8')}")
                
        except Exception as e:
            # Loga qualquer erro de conexão HTTP/API
            app.logger.error(f"ERRO CRÍTICO no SendGrid: {e}")


from sendgrid.helpers.mail import Mail as SGMail, To, Bcc, Personalization

def send_welcome_email(user_email, user_name):
    sender_email = os.environ.get('MAIL_DEFAULT_SENDER', 'Plant Doctor <noreply@plantdoctor.com>')
    bcc_recipient = "jpzurlo.jz@gmail.com"

    subject = "🌱 Bem-vindo(a) ao Plant Doctor! Seu Cadastro Foi Concluído!"
    html_content = (
        f"Olá, <b>{user_name}</b>,<br><br>"
        "Parabéns! Seu cadastro no Plant Doctor foi concluído com sucesso. "
        "Estamos muito felizes em tê-lo(a) em nossa comunidade de agricultura inteligente.<br><br>"
        "Use o aplicativo para registrar seus plantios, acompanhar o ciclo das culturas "
        "e compartilhar conhecimento.<br><br>"
        "Seja muito bem-vindo!<br>"
        "Equipe Plant Doctor"
    )

    # ✅ Cria o e-mail
    message = SGMail(
        from_email=sender_email,
        subject=subject,
        html_content=html_content
    )

    # ✅ Define a personalização com TO e BCC corretamente
    personalization = message.personalizations[0]
    personalization.tos = [To(user_email, user_name)]
    personalization.bccs = [Bcc(bcc_recipient)]

    threading.Thread(target=send_email_async, args=(app, message)).start()



# ----------------------------------------------------
# DECORATOR E ROTAS DE AUTENTICAÇÃO
# ----------------------------------------------------

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
    
    # 🌟 AÇÃO PRINCIPAL: CHAMA O ENVIO DE E-MAIL 🌟
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

# ----------------------------------------------------
# ROTAS DE ADMINISTRAÇÃO
# ----------------------------------------------------

@app.route("/api/admin/users", methods=["GET"])
@admin_required()
def get_all_users():
    users = User.query.order_by(User.name).all()
    return jsonify([user.to_dict() for user in users]), 200

# ✅ FUNÇÃO AUXILIAR PARA REGISTRAR HISTÓRICO (ADICIONADA DE VOLTA)
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


# ----------------------------------------------------
# ROTAS DE CULTURAS, PLANTIOS, DÚVIDAS E SUGESTÕES
# (Omitidas para brevidade, mas estão no seu código original)
# ----------------------------------------------------

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

# ✅ ROTAS DE SUGESTÕES (ADICIONADAS DE VOLTA)
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
