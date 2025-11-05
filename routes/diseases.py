# routes/diseases.py
from flask import Blueprint, jsonify

diseases_bp = Blueprint('disease_info', __name__)

# 🧩 Dicionário completo de doenças e pragas
disease_explanations = {
    "Algodao_lagarta_do_cartucho": {
        "identificacao": "A lagarta-do-cartucho é uma praga que ataca as folhas e brotos do algodão, deixando furos e restos de tecido vegetal.",
        "prevencao": "Realizar monitoramento constante e usar armadilhas luminosas para detectar adultos.",
        "tratamento": "Aplicar inseticidas biológicos à base de Bacillus thuringiensis ou produtos químicos seletivos em caso de infestação severa."
    },
    "Algodao_Mancha_Bacteriana": {
        "identificacao": "A mancha bacteriana causa pequenas lesões escuras nas folhas e pode afetar maçãs e ramos.",
        "prevencao": "Evitar irrigação por aspersão e utilizar sementes certificadas.",
        "tratamento": "Aplicar produtos cúpricos e eliminar restos culturais após a colheita."
    },
    "Algodao_pulgao_do_algodoeiro": {
        "identificacao": "O pulgão suga a seiva das folhas jovens, causando encarquilhamento e excreção de mela.",
        "prevencao": "Evitar adubação excessiva com nitrogênio e monitorar semanalmente as lavouras.",
        "tratamento": "Utilizar inimigos naturais como joaninhas ou aplicar inseticidas seletivos se necessário."
    },
    "Algodao_saudavel": {
        "identificacao": "Planta de algodão saudável, sem sintomas visíveis de pragas ou doenças.",
        "prevencao": "Manter práticas agrícolas adequadas e rotação de culturas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Arroz_Mancha_parda": {
        "identificacao": "Manchas pardas nas folhas e grãos causadas pelo fungo Bipolaris oryzae.",
        "prevencao": "Evitar excesso de nitrogênio e usar sementes tratadas.",
        "tratamento": "Aplicar fungicidas específicos e realizar rotação de culturas."
    },
    "Arroz_Mancha_Bacteriana_das_Folhas": {
        "identificacao": "Manchas aquosas que evoluem para áreas amareladas e secas.",
        "prevencao": "Usar variedades resistentes e evitar irrigação excessiva.",
        "tratamento": "Aplicar produtos à base de cobre e eliminar plantas infectadas."
    },
    "Arroz_Carvão_das_Folhas": {
        "identificacao": "Provoca manchas escuras e enrugamento nas folhas.",
        "prevencao": "Usar sementes sadias e evitar umidade alta.",
        "tratamento": "Tratar sementes e pulverizar fungicidas triazóis conforme recomendação técnica."
    },
    "Arroz_saudavel": {
        "identificacao": "Planta de arroz saudável, sem sinais de doença.",
        "prevencao": "Manter adubação equilibrada e monitorar a umidade do solo.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Banana_sigatoka": {
        "identificacao": "Doença fúngica que provoca listras amarelas e depois manchas escuras nas folhas.",
        "prevencao": "Manter espaçamento adequado e eliminar folhas infectadas.",
        "tratamento": "Aplicar fungicidas sistêmicos e realizar podas sanitárias."
    },
    "Banana_Black_Sigatoka_Disease": {
        "identificacao": "Variante severa da sigatoka, causando necrose nas folhas e redução drástica da produção.",
        "prevencao": "Usar variedades resistentes e boa drenagem no solo.",
        "tratamento": "Aplicar fungicidas sistêmicos em rotação para evitar resistência."
    },
    "Banana_saudavel": {
        "identificacao": "Bananeira saudável e vigorosa, sem presença de manchas ou pragas.",
        "prevencao": "Manter controle fitossanitário e nutrição equilibrada.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Banana_Moko_Disease": {
        "identificacao": "Doença bacteriana que causa murcha e escurecimento interno do pseudocaule.",
        "prevencao": "Usar mudas sadias e evitar ferramentas contaminadas.",
        "tratamento": "Erradicar plantas infectadas e desinfetar equipamentos."
    },
    "Cafe_Ferrugem": {
        "identificacao": "Doença causada pelo fungo Hemileia vastatrix, com manchas alaranjadas na face inferior das folhas.",
        "prevencao": "Usar cultivares resistentes e realizar podas de aeração.",
        "tratamento": "Aplicar fungicidas cúpricos preventivamente e manter manejo equilibrado."
    },
    "Cafe_bicho_mineiro": {
        "identificacao": "Inseto que perfura as folhas, deixando galerias secas e esbranquiçadas.",
        "prevencao": "Monitorar a lavoura e incentivar inimigos naturais.",
        "tratamento": "Aplicar inseticidas seletivos quando houver alta infestação."
    },
    "Cafe_saudavel": {
        "identificacao": "Planta de café saudável e produtiva, sem sinais de pragas ou doenças.",
        "prevencao": "Manter poda, adubação e irrigação adequadas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Milho_Blight": {
        "identificacao": "Causa manchas alongadas e necrose nas folhas.",
        "prevencao": "Evitar alta densidade de plantio e usar sementes tratadas.",
        "tratamento": "Aplicar fungicidas e fazer rotação de culturas."
    },
    "Milho_Common_Rust": {
        "identificacao": "Fungos que formam pústulas avermelhadas nas folhas.",
        "prevencao": "Usar variedades resistentes e evitar plantios fora de época.",
        "tratamento": "Aplicar fungicidas preventivos quando houver condições favoráveis."
    },
    "Milho_Healthy": {
        "identificacao": "Milho saudável, com folhas verdes e sem sinais de infecção.",
        "prevencao": "Práticas agrícolas equilibradas e controle preventivo.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Soja_Caterpillar": {
        "identificacao": "Lagartas que se alimentam das folhas e vagens da soja.",
        "prevencao": "Monitorar semanalmente e manter controle biológico ativo.",
        "tratamento": "Usar inseticidas biológicos ou químicos seletivos conforme infestação."
    },
    "Soja_Healthy": {
        "identificacao": "Soja saudável, sem sintomas de pragas ou doenças.",
        "prevencao": "Manter bom manejo de solo e rotação de culturas.",
        "tratamento": "Não há necessidade de tratamento."
    },
    "Natural Images": {
        "mensagem": "A imagem enviada não representa nenhuma cultura agrícola. Por favor, tire uma nova foto da planta."
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
