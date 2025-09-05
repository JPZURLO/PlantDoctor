from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

# Cria uma instância do SQLAlchemy. A sua aplicação principal irá inicializá-la.
db = SQLAlchemy()

class User(db.Model):
    """
    Modelo ORM (Mapeamento Objeto-Relacional) que representa a tabela 'users'
    no banco de dados.
    """
    __tablename__ = 'users'

    # Mapeia as colunas da tabela para atributos da classe Python.
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(400), nullable=False) # Aumentado para acomodar hashes mais longos

    # Define um valor padrão para a data de criação no lado do servidor.
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    def __repr__(self):
        """
        Representação em string do objeto User, útil para depuração.
        """
        return f'<User {self.email}>'

