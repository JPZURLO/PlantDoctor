# routes/disease_info.py
from flask import Blueprint, jsonify

disease_info_bp = Blueprint('disease_info', __name__)

# 🧩 Dicionário completo de doenças e pragas
disease_explanations = {
    "Algodao_lagarta_do_cartucho": {
        "identificacao": "A lagarta-do-cartucho é uma praga que se alimenta das folhas jovens do algodoeiro, causando grandes danos.",
        "prevencao": "Evitar plantio próximo a áreas infestadas e realizar monitoramento constante.",
        "tratamento": "Aplicar inseticidas biológicos à base de Bacillus thuringiensis e manter controle integrado de pragas."
    },
    "Algodao_Mancha_Bacteriana": {
        "identificacao": "Doença bacteriana que causa manchas escuras e angulares nas folhas e cápsulas do algodão.",
        "prevencao": "Usar sementes tratadas e resistentes; evitar irrigação por aspersão.",
        "tratamento": "Eliminar plantas infectadas e aplicar produtos cúpricos preventivamente."
    },
    "Algodao_pulgao_do_algodoeiro": {
        "identificacao": "Inseto sugador que enfraquece a planta e transmite viroses.",
        "prevencao": "Manter equilíbrio biológico e eliminar plantas voluntárias.",
        "tratamento": "Aplicar óleo mineral ou inseticida seletivo apenas quando houver alta infestação."
    },
    "Arroz_Mancha_parda": {
        "identificacao": "Manchas pardo-escuras nas folhas e grãos, reduzindo produtividade.",
        "prevencao": "Evitar adubação nitrogenada excessiva e realizar rotação de culturas.",
        "tratamento": "Usar fungicidas à base de triazóis no início da infecção."
    },
    "Arroz_Mancha_Bacteriana_das_Folhas": {
        "identificacao": "Manchas aquosas nas folhas que evoluem para necroses.",
        "prevencao": "Evitar irrigação por aspersão e usar sementes certificadas.",
        "tratamento": "Aplicar calda bordalesa e realizar controle preventivo."
    },
    "Banana_Black_Sigatoka_Disease": {
        "identificacao": "Fungos causam manchas negras nas folhas, reduzindo fotossíntese.",
        "prevencao": "Podar folhas doentes e garantir espaçamento adequado.",
        "tratamento": "Aplicar fungicidas sistêmicos e promover controle biológico com Trichoderma."
    },
    "Cafe_Ferrugem": {
        "identificacao": "Manchas alaranjadas na face inferior das folhas, causadas por fungo Hemileia vastatrix.",
        "prevencao": "Usar variedades resistentes e manter adubação equilibrada.",
        "tratamento": "Aplicar fungicidas preventivos e eliminar restos de poda infectados."
    },
    "Cana_RedRot": {
        "identificacao": "Fungos causam podridão vermelha no interior dos colmos.",
        "prevencao": "Usar mudas sadias e realizar rotação de culturas.",
        "tratamento": "Eliminar plantas afetadas e aplicar fungicidas protetores."
    },
    "Laranja_canker": {
        "identificacao": "Doença bacteriana que causa lesões elevadas nas folhas e frutos.",
        "prevencao": "Usar mudas certificadas e eliminar plantas infectadas.",
        "tratamento": "Aplicar calda bordalesa e controlar insetos vetores."
    },
    "Milho_Common_Rust": {
        "identificacao": "Fungo causa pústulas alaranjadas nas folhas, reduzindo área fotossintética.",
        "prevencao": "Usar híbridos resistentes e evitar monocultivo prolongado.",
        "tratamento": "Aplicar fungicidas triazóis quando a doença atingir 5% das folhas."
    },
    "Soja_Caterpillar": {
        "identificacao": "Lagartas consomem folhas e vagens, podendo causar perdas severas.",
        "prevencao": "Monitorar lavouras semanalmente e conservar inimigos naturais.",
        "tratamento": "Aplicar inseticidas seletivos apenas quando atingir nível de dano econômico."
    },
    "Trigo_septoria": {
        "identificacao": "Doença fúngica que forma manchas alongadas nas folhas, com pontuações negras.",
        "prevencao": "Usar sementes tratadas e rotação de culturas.",
        "tratamento": "Aplicar fungicidas no início da infecção e evitar plantios densos."
    },
    "Cacau_black_pod_rot": {
        "identificacao": "Podridão-negra do cacau causada por Phytophthora spp.",
        "prevencao": "Colher frutos maduros rapidamente e podar árvores infectadas.",
        "tratamento": "Aplicar fungicidas cúpricos preventivos e melhorar drenagem do solo."
    },
    "Feijao_bean_rust": {
        "identificacao": "Manchas ferruginosas nas folhas, principalmente na face inferior.",
        "prevencao": "Usar sementes certificadas e variedades resistentes.",
        "tratamento": "Aplicar fungicidas cúpricos e promover rotação de culturas."
    }
}

# 🔹 Rota para retornar as informações
@disease_info_bp.route('/api/disease-info/<disease_name>', methods=['GET'])
def get_disease_info(disease_name):
    info = disease_explanations.get(disease_name)
    if info:
        return jsonify({"success": True, "disease": disease_name, "info": info})
    else:
        return jsonify({
            "success": False,
            "message": "Doença não encontrada. Por favor, envie uma nova imagem ou tente novamente."
        }), 404
