# create_db.py
from app import app, db, seed_data

print("--- INICIANDO SETUP DA BASE DE DADOS ---")
with app.app_context():
    print("Criando todas as tabelas...")
    db.create_all()
    print("Populando a base de dados com dados iniciais...")
    seed_data()
    print("--- SETUP DA BASE DE DADOS CONCLUÍDO ---")
