import os
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
# ✅ Linha de importação unificada
from models import db, User, Culture, PlantedCulture, HistoryEvent, EventType 

app = Flask(__name__)

# --- Configuração ---
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-fallback')

# --- Inicialização das Extensões ---
db.init_app(app)
jwt = JWTManager(app)

# --- ROTAS ---
# ... (Suas outras rotas de login, registo, etc. permanecem aqui) ...
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
        
        # =============================================
        # ▼▼▼ A CORREÇÃO É APLICADA AQUI ▼▼▼
        # Converte o ID do usuário (que é um número) para uma string
        access_token = create_access_token(identity=str(user.id))
        # =============================================
        
        has_cultures = len(user.cultures) > 0
        
        return jsonify({
            "message": "Login bem-sucedido!",
            "token": access_token,
            "has_cultures": has_cultures
        }), 200
    else:
        return jsonify({"message": "Credenciais inválidas."}), 401

@app.route("/api/cultures", methods=["GET"])
@jwt_required()
def get_cultures():
    try:
        all_cultures = Culture.query.order_by(Culture.name).all()
        return jsonify([culture.to_dict() for culture in all_cultures]), 200
    except Exception as e:
        app.logger.error(f"Erro ao buscar culturas: {e}")
        return jsonify({"message": "Erro interno ao buscar culturas."}), 500

# Em app.py

@app.route("/api/user/cultures", methods=["POST"])
@jwt_required()
def save_user_cultures():
    # Extrai o ID do utilizador do token (que é uma string)
    user_id_from_token = get_jwt_identity()

    # =============================================
    # ▼▼▼ A CORREÇÃO É APLICADA AQUI ▼▼▼
    # Converte o ID de string para um número inteiro
    try:
        user_id = int(user_id_from_token)
    except ValueError:
        return jsonify({"message": "ID de utilizador inválido no token."}), 400
    # =============================================

    # Procura o utilizador na base de dados usando o ID numérico
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404

    data = request.get_json()
    culture_ids = data.get('culture_ids')

    if not isinstance(culture_ids, list):
        return jsonify({"message": "Dados inválidos. 'culture_ids' deve ser uma lista de IDs."}), 400
    
    # Limpa as culturas antigas e adiciona as novas
    user.cultures.clear()
    for culture_id in culture_ids:
        culture = Culture.query.get(culture_id)
        if culture:
            user.cultures.append(culture)
            
    db.session.commit()
    return jsonify({"message": "Culturas guardadas com sucesso!"}), 200

# Em app.py

# Em app.py

@app.route("/api/user/my-cultures", methods=["GET"])
@jwt_required()
def get_my_cultures():
    # Extrai o ID do token (string)
    user_id_from_token = get_jwt_identity()
    
    # Converte para número inteiro (esta é a correção)
    try:
        user_id = int(user_id_from_token)
    except ValueError:
        return jsonify({"message": "ID de utilizador inválido no token."}), 400

    # Agora procura com o ID numérico
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
    
    return jsonify([culture.to_dict() for culture in user.cultures]), 200

# --- FUNÇÃO PARA POPULAR O BANCO DE DADOS ---
def seed_data():
    # Restaure esta verificação
    if Culture.query.first() is None:
        print(">>> Base de dados vazia. A popular com culturas...")
        cultures_to_add = [
        Culture(name="Milho", image_url="https://marketplace.canva.com/Z5ct4/MAFCw6Z5ct4/1/tl/canva-corn-cobs-isolated-png-MAFCw6Z5ct4.png"),
        Culture(name="Café", image_url="https://static.vecteezy.com/system/resources/previews/012/986/668/non_2x/coffee-bean-logo-icon-free-png.png"),
        Culture(name="Soja", image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQJ4kcZy-KdR8mAkIWlxhYmND5CsvN5WwG-pQ&s"),
        Culture(name="Cana de Açúcar", image_url="https://i.pinimg.com/736x/d5/d0/ea/d5d0eaaa6a08dfee042f98e265ea7f87.jpg"),
        Culture(name="Trigo", image_url="https://img.freepik.com/vetores-premium/ilustracao-de-icone-de-vetor-de-logotipo-de-trigo_833786-135.jpg"),
        Culture(name="Algodão", image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRjmTW5RRENEI3nrlt8Ry1nsTzrGVpfx0oj-Q&s"),
        Culture(name="Arroz", image_url="https://img.freepik.com/vetores-premium/icone-de-arroz_609277-3890.jpg"),
        Culture(name="Feijão", image_url="https://img.freepik.com/vetores-premium/ilustracao-vetorial-de-feijao-preto-de-alta-qualidade-vetor-de-icone-de-feijao-preto-isolado-design-plano-moderno_830337-39.jpg"),
        Culture(name="Mandioca", image_url="https://media.istockphoto.com/id/1353955911/pt/vetorial/cassava-root.jpg?s=612x612&w=0&k=20&c=obWmGbXBnj46d4KbNNKW7DYMfWkAngFs9gRKh4E3OBg="),
        Culture(name="Cacau", image_url="https://previews.123rf.com/images/pchvector/pchvector2211/pchvector221102749/194589566-chocolate-cocoa-bean-on-branch-with-leaves-cartoon-illustration-cacao-beans-with-leaves-on-tree.jpg"),
        Culture(name="Banana", image_url="https://png.pngtree.com/png-clipart/20230928/original/pngtree-banana-logo-icon-design-fruit-tropical-yellow-vector-png-image_12898187.png"),
        Culture(name="Laranja", image_url="https://cdn-icons-png.flaticon.com/512/5858/5858316.png")
   ]
        db.session.bulk_save_objects(cultures_to_add)
        db.session.commit()
        print(f">>> {len(cultures_to_add)} culturas adicionadas.")
    else:
        print(">>> Base de dados já populada. Nenhuma ação necessária.")

if __name__ == '__main__':
    with app.app_context():
        # Cria todas as tabelas do banco de dados (caso não existam)
        db.create_all()
        
        # Chama a função para popular com os dados iniciais
        seed_data()
        
    # Inicia o servidor de desenvolvimento
    app.run(debug=True)
# --- ROTAS DE GESTÃO DE PLANTIOS ---

@app.route("/api/planted-cultures", methods=["POST"])
@jwt_required()
def add_planted_culture():
    """ Cria um novo registo de plantio para o usuário logado. """
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    culture_id = data.get('culture_id')
    planting_date_str = data.get('planting_date') # Espera formato "YYYY-MM-DD"
    notes = data.get('notes')

    if not culture_id or not planting_date_str:
        return jsonify({"message": "culture_id e planting_date são obrigatórios."}), 400

    try:
        planting_date = datetime.strptime(planting_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    # Lógica de previsão de colheita (exemplo simples, pode ser movida para um helper)
    # No futuro, o app pode enviar a previsão, ou o backend pode calcular
    predicted_harvest_date = planting_date + timedelta(days=90) # Exemplo: 90 dias

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
    """ Retorna todos os plantios do usuário logado. """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilizador não encontrado."}), 404
        
    return jsonify([planting.to_dict() for planting in user.planted_cultures]), 200

@app.route("/api/planted-cultures/<int:planted_culture_id>/history", methods=["POST"])
@jwt_required()
def add_history_event(planted_culture_id):
    """ Adiciona um evento de histórico a um plantio específico. """
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
        # Converte a string do JSON para o nosso Enum
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

