from flask import Blueprint, request, jsonify
from models import db, DiagnosisHistory
from datetime import datetime

diagnosis_bp = Blueprint('diagnosis', __name__)

# ✅ Salva o diagnóstico no banco
@diagnosis_bp.route('/diagnosis', methods=['POST'])
def save_diagnosis():
    data = request.get_json()

    try:
        new_diagnosis = DiagnosisHistory(
            diagnosis_name=data.get('diagnosis_name'),
            observation=data.get('observation'),
            photo_path=data.get('photo_path'),
            analysis_date=datetime.utcnow(),
            user_id=data.get('user_id'),
            culture_id=data.get('culture_id')
        )

        db.session.add(new_diagnosis)
        db.session.commit()

        return jsonify({'message': 'Diagnóstico salvo com sucesso!'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ✅ Lista o histórico de diagnósticos do usuário
@diagnosis_bp.route('/diagnosis/history/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    history = DiagnosisHistory.query.filter_by(user_id=user_id).order_by(DiagnosisHistory.analysis_date.desc()).all()
    return jsonify([h.to_dict() for h in history])
