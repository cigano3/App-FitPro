from flask import Flask, request, jsonify, send_file, render_template_string, redirect
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import io, os, uuid, json, datetime, csv
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'devsecret')

RULES = {
    "objetivos": {"emagrecer": -0.15, "manter": 0.0, "ganhar": 0.10},
    "atividade": {"sedentario": 1.2, "iniciante": 1.375, "intermediario": 1.55, "avancado": 1.725}
}

def load_foods_data():
    try:
        with open('data/foods.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"foods": {}, "alternatives": {}}

def calcular_peso_porcao(alimento: str, calorias: int) -> str:
    densidades = {
        "Pão integral": 280, "Pão francês": 300, "Arroz": 130, "Feijão": 90,
        "Frango": 165, "Carne bovina": 250, "Peixe": 180, "Ovo": 155,
        "Batata-doce": 86, "Mandioca": 160, "Abóbora": 26, "Salada": 20,
        "Iogurte": 60, "Fruta": 50, "Tapioca": 98, "Cuscuz": 112,
        "Macarrão": 131, "Pizza": 266, "Hambúrguer": 295, "Frituras": 365
    }
    
    densidade = 150
    for key, val in densidades.items():
        if key.lower() in alimento.lower():
            densidade = val
            break
    
    gramas = (calorias * 100) / densidade
    
    if gramas <= 20:
        return f"{round(gramas)}g (1 colher sopa)"
    elif gramas <= 50:
        return f"{round(gramas)}g (1/2 xícara)"
    elif gramas <= 100:
        return f"{round(gramas)}g (1 xícara)"
    elif gramas <= 150:
        return f"{round(gramas)}g (1 prato sobremesa)"
    elif gramas <= 250:
        return f"{round(gramas)}g (1 prato raso)"
    else:
        return f"{round(gramas)}g (1 prato fundo)"

def calcular_calorias_consumidas(alimentos_selecionados: dict) -> dict:
    foods_data = load_foods_data()
    foods = foods_data.get('foods', {})
    
    total_consumido = 0
    recomendacoes = []
    
    refeicoes_nomes = {
        "cafe": "Café da Manhã",
        "almoco": "Almoço", 
        "lanche": "Lanche da Tarde",
        "jantar": "Jantar"
    }
    
    for refeicao, alimentos in alimentos_selecionados.items():
        for alimento in alimentos:
            food_info = foods.get(alimento, {"calories": 300, "category": "medium"})
            total_consumido += food_info["calories"]
            
            if food_info["category"] in ["bad", "medium"]:
                alternativas = foods_data.get('alternatives', {}).get(alimento, [])
                if alternativas:
                    alt_principal = alternativas[0]
                    alt_info = foods.get(alt_principal, {"calories": 200, "category": "good"})
                    
                    peso_original = calcular_peso_porcao(alimento, food_info["calories"])
                    peso_alternativa = calcular_peso_porcao(alt_principal, alt_info["calories"])
                    
                    economia_calorias = food_info["calories"] - alt_info["calories"]
                    
                    recomendacoes.append({
                        "refeicao": refeicoes_nomes.get(refeicao, refeicao.title()),
                        "original": alimento,
                        "original_calorias": food_info["calories"],
                        "original_peso": peso_original,
                        "alternativa": alt_principal,
                        "alternativa_calorias": alt_info["calories"],
                        "alternativa_peso": peso_alternativa,
                        "economia_calorias": economia_calorias,
                        "categoria_original": food_info["category"]
                    })
    
    return {"total_consumido": total_consumido, "recomendacoes": recomendacoes}

def salvar_lead(respostas: dict):
    try:
        os.makedirs('data', exist_ok=True)
        csv_path = 'data/leads.csv'
        file_exists = os.path.exists(csv_path)
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'nome', 'email', 'whatsapp', 'objetivo', 'atividade', 'peso', 'altura', 'idade'])
            writer.writerow([
                datetime.datetime.now().isoformat(),
                respostas.get('nome', ''), respostas.get('email', ''), respostas.get('whatsapp', ''),
                respostas.get('objetivo', ''), respostas.get('atividade', ''),
                respostas.get('peso', ''), respostas.get('altura', ''), respostas.get('idade', '')
            ])
    except: pass

def calcular_peso_ideal(altura_cm: float, sexo: str) -> float:
    return (50 if sexo == 'masculino' else 45.5) + 2.3 * ((altura_cm - 152.4) / 2.54)

def calcular_agua_diaria(peso_kg: float) -> float:
    return peso_kg * 35

def mifflin_st_jeor(sexo: str, peso_kg: float, altura_cm: float, idade: int) -> float:
    s = 5 if sexo == 'masculino' else -161
    return 10 * peso_kg + 6.25 * altura_cm - 5 * idade + s

def calcular_imc(peso: float, altura_cm: float) -> dict:
    imc = peso / ((altura_cm / 100) ** 2)
    
    if imc < 18.5: return {"valor": round(imc, 1), "categoria": "abaixo", "status": "Abaixo do Peso", "cor": "#3498db", "posicao": 15}
    elif imc < 25: return {"valor": round(imc, 1), "categoria": "normal", "status": "Normal", "cor": "#27ae60", "posicao": 40}
    elif imc < 30: return {"valor": round(imc, 1), "categoria": "sobrepeso", "status": "Sobrepeso", "cor": "#f39c12", "posicao": 70}
    else: return {"valor": round(imc, 1), "categoria": "obeso", "status": "Obeso", "cor": "#e74c3c", "posicao": 90}

def gerar_frase_motivacional(objetivo: str, imc_info: dict) -> str:
    frases = {
        "emagrecer": "Seu corpo pode se transformar e definir ao mesmo tempo",
        "manter": "Seu corpo pode se manter equilibrado e saudável", 
        "ganhar": "Seu corpo pode definir e crescer ao mesmo tempo"
    }
    return frases[objetivo]

def calcular_alvo_kcal(respostas: dict) -> dict:
    bmr = mifflin_st_jeor(respostas['sexo'], respostas['peso'], respostas['altura'], respostas['idade'])
    tdee = bmr * RULES['atividade'].get(respostas['atividade'], 1.2)
    alvo = int(round(tdee * (1 + RULES['objetivos'][respostas['objetivo']])))
    imc_info = calcular_imc(respostas['peso'], respostas['altura'])
    
    return {
        "bmr": int(bmr), 
        "tdee": int(tdee), 
        "alvo": alvo,
        "imc": imc_info,
        "frase_motivacional": gerar_frase_motivacional(respostas['objetivo'], imc_info)
    }

def calcular_quantidade_alimento(alimento: str, kcal_desejadas: int, foods_data: dict) -> dict:
    food_info = foods_data.get('foods', {}).get(alimento, {"calories": 300, "category": "medium"})
    kcal_por_100g = food_info["calories"]
    gramas_necessarias = (kcal_desejadas * 100) / kcal_por_100g
    
    if gramas_necessarias <= 15:
        quantidade = f"{round(gramas_necessarias)} g (1 colher sopa)"
    elif gramas_necessarias <= 30:
        quantidade = f"{round(gramas_necessarias)} g (2 colheres sopa)"
    elif gramas_necessarias <= 50:
        quantidade = f"{round(gramas_necessarias)} g (1/2 xícara)"
    elif gramas_necessarias <= 100:
        quantidade = f"{round(gramas_necessarias)} g (1 xícara)"
    elif gramas_necessarias <= 150:
        quantidade = f"{round(gramas_necessarias)} g (1 prato sobremesa)"
    elif gramas_necessarias <= 200:
        quantidade = f"{round(gramas_necessarias)} g (1 prato raso)"
    else:
        quantidade = f"{round(gramas_necessarias)} g (1 prato fundo)"
    
    return {
        "gramas": round(gramas_necessarias),
        "quantidade": quantidade,
        "kcal_real": round((gramas_necessarias * kcal_por_100g) / 100)
    }

def montar_refeicoes(alvo_kcal: int, alimentos_selecionados: dict = None) -> dict:
    distribuicao = {"cafe": 0.25, "almoco": 0.35, "lanche": 0.15, "jantar": 0.25}
    foods_data = load_foods_data()
    
    plano = {}
    for bloco, pct in distribuicao.items():
        meta = int(alvo_kcal * pct)
        opcoes = []
        
        if alimentos_selecionados and bloco in alimentos_selecionados:
            alimentos = alimentos_selecionados[bloco]
            if alimentos:
                kcal_por_alimento = meta // len(alimentos)
                
                for alimento in alimentos:
                    food_info = foods_data.get('foods', {}).get(alimento, {"calories": 300, "category": "medium"})
                    quantidade_info = calcular_quantidade_alimento(alimento, kcal_por_alimento, foods_data)
                    
                    opcoes.append({
                        "descricao": alimento,
                        "kcal": quantidade_info["kcal_real"],
                        "quantidade": quantidade_info["quantidade"],
                        "gramas": quantidade_info["gramas"],
                        "category": food_info["category"]
                    })
        
        plano[bloco] = {"meta_kcal": meta, "opcoes": opcoes}
    return plano

def gerar_pdf(plano: dict, respostas: dict, metas: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, "Plano Personalizado")

    # Dados principais
    c.setFont("Helvetica", 11)
    y = height - 3*cm
    c.drawString(2*cm, y, f"Nome: {respostas.get('nome','-')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Objetivo: {respostas['objetivo'].title()} | Alvo: {metas['alvo']} kcal")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Peso: {respostas['peso']} kg | Altura: {respostas['altura']} cm | Idade: {respostas['idade']}")

    # Refeições
    titulos = {"cafe": "Café da Manhã", "almoco": "Almoço", "lanche": "Lanche", "jantar": "Jantar"}
    for bloco in ["cafe", "almoco", "lanche", "jantar"]:
        y -= 1*cm
        if y < 4*cm: c.showPage(); y = height - 2*cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, y, f"{titulos[bloco]} ({plano[bloco]['meta_kcal']} kcal)")
        y -= 0.5*cm
        c.setFont("Helvetica", 10)
        for op in plano[bloco]['opcoes']:
            c.drawString(2.2*cm, y, f"{op['descricao']} - {op['quantidade']} ({op['kcal']} kcal)")
            y -= 0.4*cm

    c.save()
    return buffer.getvalue()

# Aplicação Flask com todas as rotas
last_user_data = {}

if __name__ == '__main__':
    app.run(debug=True)