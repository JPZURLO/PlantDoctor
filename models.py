from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()

# Tabela de associação para a relação muitos-para-muitos entre User e Culture
user_cultures = db.Table('user_cultures',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('culture_id', db.Integer, db.ForeignKey('culture.id'), primary_key=True)
)

class User(db.Model):
    """
    Modelo ORM que representa a tabela 'users' no banco de dados.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # ✅ RELAÇÃO ADICIONADA: Liga o utilizador às suas culturas selecionadas.
    cultures = db.relationship('Culture', secondary=user_cultures, lazy='subquery',
                               backref=db.backref('users', lazy=True))

    def __repr__(self):
        return f'<User {self.email}>'

class Culture(db.Model):
    """
    Modelo ORM que representa a tabela 'culture' no banco de dados.
    """
    __tablename__ = 'culture'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        """Converte o objeto Culture para um dicionário, útil para respostas JSON."""
        return {
            'id': self.id,
            'name': self.name,
            'image_url': self.image_url
        }

