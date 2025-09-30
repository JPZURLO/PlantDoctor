from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLAlchemyEnum # Importação necessária
import enum # Importação necessária

db = SQLAlchemy()

# Tabela de associação para a relação muitos-para-muitos entre User e Culture (INTERESSES)
user_cultures = db.Table('user_cultures',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('culture_id', db.Integer, db.ForeignKey('culture.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relação para as culturas de INTERESSE do usuário
    cultures = db.relationship('Culture', secondary=user_cultures, lazy='subquery',
                               backref=db.backref('interested_users', lazy=True))

    # ✅ NOVA RELAÇÃO: Um usuário pode ter vários plantios.
    planted_cultures = db.relationship('PlantedCulture', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'

class Culture(db.Model):
    __tablename__ = 'culture'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_url': self.image_url
        }

# ==========================================================
# ▼▼▼ NOVOS MODELOS ADICIONADOS AQUI ▼▼▼
# ==========================================================

class PlantedCulture(db.Model):
    """ Representa uma instância específica de uma cultura plantada por um usuário. """
    __tablename__ = 'planted_culture'
    
    id = db.Column(db.Integer, primary_key=True)
    planting_date = db.Column(db.Date, nullable=False)
    predicted_harvest_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True) # Um campo para anotações gerais
    
    # Chaves Estrangeiras
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    culture_id = db.Column(db.Integer, db.ForeignKey('culture.id'), nullable=False)
    
    # Relações
    culture = db.relationship('Culture', backref='planted_instances')
    history_events = db.relationship('HistoryEvent', backref='planted_culture', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'planting_date': self.planting_date.isoformat(),
            'predicted_harvest_date': self.predicted_harvest_date.isoformat() if self.predicted_harvest_date else None,
            'notes': self.notes,
            'user_id': self.user_id,
            'culture': self.culture.to_dict(), # Inclui os dados da cultura (nome, imagem)
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
    """ Representa um evento no histórico de uma cultura plantada. """
    __tablename__ = 'history_event'

    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.DateTime, nullable=False, default=func.now())
    event_type = db.Column(SQLAlchemyEnum(EventType), nullable=False)
    observation = db.Column(db.Text, nullable=True)
    
    # Chave Estrangeira
    planted_culture_id = db.Column(db.Integer, db.ForeignKey('planted_culture.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'event_date': self.event_date.isoformat(),
            'event_type': self.event_type.name, # Retorna o nome do enum (ex: "ADUBAGEM")
            'observation': self.observation
        }
