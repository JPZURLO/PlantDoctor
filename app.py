# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import psycopg2
import os
from psycopg2 import Error

app = Flask(__name__)

# Configurações do banco de dados PostgreSQL do Render
# As credenciais são lidas das variáveis de ambiente
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")
DB_PORT = os.environ.get("DB_PORT")

def create_db_connection():
    """
    Função para criar uma conexão com o banco de dados PostgreSQL.
    """
    connection = None
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        print("Conexão com o banco de dados PostgreSQL bem-sucedida")
    except Error as e:
        print(f"Ocorreu um erro ao conectar ao PostgreSQL: {e}")
    return connection

@app.route("/register", methods=["POST"])
def register_user():
    """
    Endpoint para registrar um novo usuário no banco de dados.
    Recebe um JSON com 'name', 'email' e 'password'.
    """
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not all([name, email, password]):
        return jsonify({"message": "Nome, e-mail e senha são obrigatórios"}), 400

    password_hash = password.__hash__()

    connection = create_db_connection()
    if connection is None:
        return jsonify({"message": "Erro no servidor. Tente novamente mais tarde."}), 500

    try:
        cursor = connection.cursor()
        
        # Verifique se o e-mail já existe
        check_query = "SELECT email FROM users WHERE email = %s"
        cursor.execute(check_query, (email,))
        if cursor.fetchone():
            return jsonify({"message": "Este e-mail já está em uso"}), 409

        # Insere o novo usuário
        insert_query = "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (name, email, password_hash))
        connection.commit()
        
        return jsonify({"message": "Cadastro realizado com sucesso!"}), 200

    except Error as e:
        print(f"Erro ao inserir dados: {e}")
        return jsonify({"message": "Erro no servidor. Tente novamente mais tarde."}), 500
    finally:
        if 'cursor' in locals() and cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
