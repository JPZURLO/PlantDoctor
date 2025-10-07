from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLAlchemyEnum, Column, Integer, String, DateTime, ForeignKey # Importações adicionais para o novo modelo
from sqlalchemy.orm import relationship # Importações adicionais para o novo modelo
import enum

db = SQLAlchemy()

# Tabela de associação
user_cultures = db.Table('user_cultures',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('culture_id', db.Integer, db.ForeignKey('culture.id'), primary_key=True)
)

# ▼▼▼ ENUM PARA O TIPO DE USUÁRIO ▼▼▼
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

    # ▼▼▼ COLUNA DO TIPO DE USUÁRIO ▼▼▼
    user_type = db.Column(SQLAlchemyEnum(UserType), nullable=False, default=UserType.COMMON)

    cultures = db.relationship('Culture', secondary=user_cultures, lazy='subquery',
                                backref=db.backref('interested_users', lazy=True))
    
    planted_cultures = db.relationship('PlantedCulture', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.email}>'
    
    # ▼▼▼ FUNÇÃO to_dict PARA RETORNAR DADOS DO USUÁRIO ▼▼▼
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
    
    culture = db.relationship('Culture', backref='planted_instances')
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

class Doubt(db.Model):
    __tablename__ = 'doubts'

    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship('User', backref='doubts')

    def to_dict(self):
        return {
            'id': self.id,
            'question_text': self.question_text,
            'created_at': self.created_at.isoformat(),
            'author_name': 'Anônimo' if self.is_anonymous else self.author.name
        }

class Suggestion(db.Model):
    __tablename__ = 'suggestions'

    id = db.Column(db.Integer, primary_key=True)
    suggestion_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship('User', backref='suggestions')

    def to_dict(self):
        return {
            'id': self.id,
            'suggestion_text': self.suggestion_text,
            'created_at': self.created_at.isoformat(),
            'author_name': 'Anônimo' if self.is_anonymous else self.author.name
        }

class UserEditHistory(db.Model):
    """ Registra as alterações feitas nos perfis de usuário. """
    __tablename__ = 'user_edit_history'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Qual usuário foi editado
    edited_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Quem fez a edição (o admin logado)
    edited_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    field_changed = db.Column(db.String(50), nullable=False) # Ex: 'name', 'email', 'user_type'
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relações para podermos buscar os nomes
    edited_user = db.relationship('User', foreign_keys=[edited_user_id], backref='edit_history')
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

# ▼▼▼ NOVO: MODELO PARA RASTREAR TOKENS DE RECUPERAÇÃO DE SENHA ▼▼▼
class PasswordResetToken(db.Model):
    """ Armazena tokens temporários para redefinição de senha. """
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Chave estrangeira para o usuário
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # O token de redefinição real (JWT)
    token = db.Column(db.String(255), unique=True, nullable=False)
    
    # Data e hora de expiração do token
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Relacionamento com o usuário
    user = db.relationship('User', backref='reset_tokens')
    
    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id}>"
