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


# -------------------------
# Rotas
# -------------------------

FINAL_PLAN_HTML = """
<!doctype html>
<html lang=pt-br>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Seu Plano Completo</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #f6f7f9 0%, #f1f3f6 100%);
      margin: 0; padding: 20px; line-height: 1.6; color: #2c3e50;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    .card {
      background: #fff; border-radius: 16px;
      box-shadow: 0 8px 25px rgba(0,0,0,.1);
      padding: 32px; margin-bottom: 24px;
    }
    .header {
      text-align: center; margin-bottom: 32px;
      padding: 24px; background: linear-gradient(135deg, #ff8c00, #ffa500);
      border-radius: 16px; color: white;
    }
    .metrics {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px; margin-bottom: 32px;
    }
    .metric {
      text-align: center; padding: 20px;
      background: linear-gradient(135deg, #f8f9fa, #e9ecef);
      border-radius: 12px; border: 2px solid #ff8c00;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #ff8c00; }
    .metric-label { font-size: 14px; color: #666; margin-top: 8px; }
    .analysis-card {
      background: linear-gradient(135deg, #fff6ea, #fef9f0);
      border: 2px solid #ff8c00; border-radius: 16px;
      padding: 24px; margin-bottom: 24px;
    }
    .meal-analysis {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 20px; margin-bottom: 32px;
    }
    .meal-card {
      background: #f8f9fa; border-radius: 12px;
      padding: 20px; border-left: 4px solid #ff8c00;
    }
    .meal-title { font-weight: 600; color: #2c3e50; margin-bottom: 12px; }
    .food-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 8px 12px; margin: 6px 0;
      background: white; border-radius: 6px;
    }
    .food-item.good { border-left: 3px solid #28a745; }
    .food-item.medium { border-left: 3px solid #ffc107; }
    .food-item.bad { border-left: 3px solid #dc3545; }
    .btn {
      background: linear-gradient(135deg, #ff8c00, #ffa500);
      color: white; padding: 16px 32px; border: none;
      border-radius: 12px; font-size: 16px; font-weight: 600;
      cursor: pointer; text-decoration: none; display: inline-block;
      text-align: center; margin: 16px 8px;
    }
    .btn:hover { transform: translateY(-2px); }
    .progress-bar {
      background: #e9ecef; border-radius: 10px; height: 20px;
      overflow: hidden; margin: 16px 0;
    }
    .progress-fill {
      height: 100%; border-radius: 10px;
      transition: width 0.3s ease;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎯 Seu Plano Nutricional Completo</h1>
      <p>Análise detalhada baseada nas suas escolhas alimentares</p>
    </div>
    
    <div class="card">
      <h2>👤 Seu Perfil</h2>
      <div class="metrics">
        <div class="metric">
          <div class="metric-value">{{ respostas.idade }}</div>
          <div class="metric-label">Anos</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ respostas.peso }} kg</div>
          <div class="metric-label">Peso Atual</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ "%.1f"|format(peso_ideal) }} kg</div>
          <div class="metric-label">Peso Ideal</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ respostas.altura }} cm</div>
          <div class="metric-label">Altura</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ metas.imc.valor }}</div>
          <div class="metric-label">IMC - {{ metas.imc.status }}</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ respostas.atividade.title() }}</div>
          <div class="metric-label">Nível de Atividade</div>
        </div>
      </div>
    </div>
    
    <div class="analysis-card">
      <h2>📊 Análise Calórica Diária</h2>
      <div class="metrics">
        <div class="metric">
          <div class="metric-value">{{ metas.alvo }}</div>
          <div class="metric-label">Meta Diária (kcal)</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ analise_calorias.total_consumido }}</div>
          <div class="metric-label">Consumo Atual (kcal)</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ porcentagem_consumo }}%</div>
          <div class="metric-label">% do Alvo Diário</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ "%.0f"|format(agua_diaria) }} ml</div>
          <div class="metric-label">Água Diária</div>
        </div>
      </div>
      
      <div class="progress-bar">
        <div class="progress-fill" style="width: {{ porcentagem_consumo if porcentagem_consumo <= 100 else 100 }}%; background: {% if porcentagem_consumo > 120 %}#dc3545{% elif porcentagem_consumo > 100 %}#ffc107{% else %}#28a745{% endif %};"></div>
      </div>
      
      {% if calorias_para_queimar > 0 %}
        <div style="text-align: center; padding: 16px; background: #fff3cd; border-radius: 12px; margin-top: 16px;">
          <p style="margin: 0 0 12px; color: #dc3545; font-weight: 600;">
            ⚠️ Para manter o déficit, você precisa queimar {{ calorias_para_queimar }} kcal hoje
          </p>
          <p style="margin: 0 0 16px; color: #2c3e50; font-size: 14px;">Uma dieta bem estruturada pode gerar um déficit de até <strong>500-700 kcal/dia</strong>, equivalente a <strong>1 hora de corrida intensa</strong>.</p>
          <div style="background: rgba(255, 255, 255, 0.7); border-radius: 12px; padding: 16px;">
            <h4 style="color: #2c3e50; margin: 0 0 12px; font-size: 14px;">🏃 Calorias Queimadas em 30 Minutos (pessoa de 70kg):</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; font-size: 12px; color: #555;">
              <div><strong>🚶 Caminhada:</strong> 150 kcal</div>
              <div><strong>🏃 Corrida leve:</strong> 300 kcal</div>
              <div><strong>🤸 Polichinelos:</strong> 200 kcal</div>
              <div><strong>🏋️ Agachamentos:</strong> 180 kcal</div>
              <div><strong>💪 Flexões:</strong> 160 kcal</div>
              <div><strong>🚴 Bicicleta:</strong> 250 kcal</div>
            </div>
            <p style="margin: 12px 0 0; font-size: 12px; color: #666; font-style: italic;">Compare: 1 biscoito recheado = 450 kcal = 1h30 de caminhada!</p>
          </div>
        </div>
      {% else %}
        <p style="text-align: center; color: #28a745; font-weight: 600;">
          ✅ Você está consumindo {{ porcentagem_consumo }}% da sua meta diária
        </p>
      {% endif %}
    </div>
    
    <div class="card">
      <h2>🍽️ Análise por Refeição</h2>
      <div class="meal-analysis">
        {% for refeicao, dados in plano.items() %}
        <div class="meal-card">
          <div class="meal-title">
            {% if refeicao == 'cafe' %}☕ Café da Manhã
            {% elif refeicao == 'almoco' %}🍽️ Almoço
            {% elif refeicao == 'lanche' %}🥪 Lanche
            {% else %}🌙 Jantar{% endif %}
            ({{ dados.meta_kcal }} kcal)
          </div>
          {% for opcao in dados.opcoes %}
          <div class="food-item {{ opcao.get('category', 'medium') }}">
            <div>
              <span>{{ opcao.descricao }}</span>
              <small style="display: block; color: #666; font-size: 12px;">{{ opcao.gramas }}g</small>
            </div>
            <span>{{ opcao.kcal }} kcal</span>
          </div>
          {% endfor %}
        </div>
        {% endfor %}
      </div>
    </div>
    
    {% if analise_calorias.recomendacoes %}
    <div class="card">
      <h2>💡 Recomendações Inteligentes</h2>
      <p style="text-align: center; color: #666; margin-bottom: 24px;">Baseado em dados nutricionais reais, sugerimos estas trocas para otimizar sua dieta:</p>
      {% for rec in analise_calorias.recomendacoes %}
      <div style="background: {% if rec.categoria_original == 'bad' %}#fff0f0{% else %}#fff8f0{% endif %}; border: 2px solid {% if rec.categoria_original == 'bad' %}#dc3545{% else %}#ffc107{% endif %}; border-radius: 12px; padding: 16px; margin: 12px 0;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
          <span style="background: {% if rec.categoria_original == 'bad' %}#dc3545{% else %}#ffc107{% endif %}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;">{{ rec.refeicao }}</span>
          <strong style="color: #2c3e50;">🔄 Troca Recomendada</strong>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 16px; align-items: center; margin: 12px 0;">
          <div style="text-align: center; padding: 12px; background: rgba(220, 53, 69, 0.1); border-radius: 8px;">
            <div style="font-weight: 600; color: #dc3545; margin-bottom: 4px;">❌ Evitar</div>
            <div style="font-size: 14px; color: #2c3e50;">{{ rec.original }}</div>
            <div style="font-size: 12px; color: #666; margin-top: 4px;">{{ rec.original_peso }}</div>
            <div style="font-weight: 600; color: #dc3545;">{{ rec.original_calorias }} kcal</div>
          </div>
          
          <div style="font-size: 24px; color: #ff8c00;">→</div>
          
          <div style="text-align: center; padding: 12px; background: rgba(40, 167, 69, 0.1); border-radius: 8px;">
            <div style="font-weight: 600; color: #28a745; margin-bottom: 4px;">✅ Preferir</div>
            <div style="font-size: 14px; color: #2c3e50;">{{ rec.alternativa }}</div>
            <div style="font-size: 12px; color: #666; margin-top: 4px;">{{ rec.alternativa_peso }}</div>
            <div style="font-weight: 600; color: #28a745;">{{ rec.alternativa_calorias }} kcal</div>
          </div>
        </div>
        
        <div style="text-align: center; padding: 8px; background: rgba(255, 140, 0, 0.1); border-radius: 6px; margin-top: 8px;">
          <small style="color: #ff8c00; font-weight: 600;">💰 Economia: {{ rec.economia_calorias }} kcal por porção</small>
        </div>
      </div>
      {% endfor %}
      
      <div style="background: linear-gradient(135deg, #e8f5e8, #f0fff0); border: 2px solid #28a745; border-radius: 12px; padding: 16px; margin-top: 20px; text-align: center;">
        <h4 style="color: #28a745; margin: 0 0 8px;">🎯 Dica Importante</h4>
        <p style="margin: 0; color: #2c3e50; font-size: 14px; line-height: 1.5;">Fazendo essas trocas simples, você pode economizar até <strong>{{ analise_calorias.recomendacoes|sum(attribute='economia_calorias') }} kcal por dia</strong>, facilitando o alcance dos seus objetivos!</p>
      </div>
    </div>
    {% endif %}
    
    <div class="analysis-card">
      <h2>💪 Sua Jornada</h2>
      <p style="font-size: 16px; line-height: 1.6; text-align: center;">
        {{ metas.frase_motivacional }}
      </p>
    </div>
    
    <div class="card" style="text-align: center;">
      <h2>📄 Baixe seu Plano</h2>
      <p>Tenha sempre em mãos seu plano personalizado</p>
      <a href="/gerar-pdf/current" class="btn">📄 Baixar PDF Completo</a>
      <a href="/" class="btn" style="background: #6c757d;">🏠 Criar Novo Plano</a>
    </div>
  </div>
</body>
</html>
"""

INDEX_HTML = """
<!doctype html>
<html lang=pt-br>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quiz → Plano → PDF</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: linear-gradient(135deg, #f6f7f9 0%, #f1f3f6 100%);
      margin: 0;
      padding: 0;
      line-height: 1.6;
      color: #2c3e50;
    }
    .wrap {
      max-width: 800px;
      margin: 0 auto;
      padding: 32px 24px;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card {
      background: #fff;
      border-radius: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,.08), 0 8px 25px rgba(0,0,0,.06);
      padding: 40px;
      margin-bottom: 16px;
      width: 100%;
      position: relative;
      overflow: hidden;
      transition: all 0.3s ease;
    }
    .card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, #ff8c00, #ffa500);
    }
    .row { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }
    .col { flex: 1 1 200px; min-width: 200px; }
    .btn {
      background: linear-gradient(135deg, #ff8c00, #ffa500);
      border: none;
      color: #fff;
      padding: 16px 24px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(255, 140, 0, 0.3);
      position: relative;
      overflow: hidden;
    }
    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(255, 140, 0, 0.4);
    }
    .btn:active { transform: translateY(0); }
    .btn.outline {
      background: transparent;
      color: #ff8c00;
      border: 2px solid #ff8c00;
      box-shadow: none;
    }
    .btn.outline:hover {
      background: rgba(255, 140, 0, 0.05);
      transform: translateY(-1px);
    }
    .hidden { display: none; }
    input, select {
      width: 100%;
      padding: 16px 20px;
      border-radius: 12px;
      border: 2px solid #e3e6ec;
      font-size: 16px;
      transition: all 0.3s ease;
      background: #fafbfc;
      -webkit-appearance: none;
      -moz-appearance: none;
      appearance: none;
      background-image: url('data:image/svg+xml;charset=US-ASCII,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 5"><path fill="%23666" d="M2 0L0 2h4zm0 5L0 3h4z"/></svg>');
      background-repeat: no-repeat;
      background-position: right 16px center;
      background-size: 12px;
      padding-right: 40px;
    }
    input:focus, select:focus {
      outline: none;
      border-color: #ff8c00;
      background-color: #fff;
      box-shadow: 0 0 0 3px rgba(255, 140, 0, 0.1);
    }
    select:focus {
      background-image: url('data:image/svg+xml;charset=US-ASCII,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 5"><path fill="%23ff8c00" d="M2 0L0 2h4zm0 5L0 3h4z"/></svg>');
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      color: #34495e;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    h1 {
      margin: 0 0 32px;
      font-size: 32px;
      font-weight: 700;
      text-align: center;
      background: linear-gradient(135deg, #2c3e50, #34495e);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    h3 {
      margin: 0 0 24px;
      font-size: 24px;
      font-weight: 600;
      text-align: center;
      color: #2c3e50;
    }
    small { color: #707786; font-size: 14px; }
    .steps {
      display: flex;
      justify-content: center;
      gap: 12px;
      margin-bottom: 32px;
      padding: 0 20px;
    }
    .dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #e3e6ec;
      transition: all 0.3s ease;
      position: relative;
    }
    .dot.active {
      background: #ff8c00;
      transform: scale(1.2);
      box-shadow: 0 0 0 4px rgba(255, 140, 0, 0.2);
    }
    .dot.active::after {
      content: '';
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 6px;
      height: 6px;
      background: #fff;
      border-radius: 50%;
    }
    .grid2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .option {
      padding: 20px 24px;
      border: 2px solid #e3e6ec;
      border-radius: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      text-align: center;
      font-weight: 500;
      font-size: 16px;
      background: #fafbfc;
      position: relative;
      overflow: hidden;
    }
    .option:hover {
      border-color: #ff8c00;
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    .option.active {
      border-color: #ff8c00;
      background: #fff6ea;
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(255, 140, 0, 0.2);
    }
    .option.active::before {
      content: '✓';
      position: absolute;
      top: 8px;
      right: 12px;
      color: #ff8c00;
      font-weight: bold;
      font-size: 18px;
    }
    .btn-group {
      display: flex;
      gap: 16px;
      justify-content: center;
      flex-wrap: wrap;
      margin-top: 32px;
    }
    .fade-in {
      animation: fadeIn 0.5s ease-in;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .preview-card {
      background: linear-gradient(135deg, #fff6ea, #fef9f0);
      border: 2px solid #ff8c00;
      border-radius: 16px;
      padding: 24px;
      margin: 20px 0;
    }
    .preview-card h4 {
      color: #ff8c00;
      margin: 0 0 16px;
      font-size: 18px;
      font-weight: 600;
    }
    .meal-section {
      margin-bottom: 20px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.7);
      border-radius: 12px;
    }
    .meal-title {
      font-weight: 600;
      color: #2c3e50;
      margin-bottom: 8px;
      font-size: 16px;
    }
    .meal-options {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    .meal-options li {
      padding: 4px 0;
      color: #555;
      font-size: 14px;
    }
    .meal-selection {
      margin-bottom: 32px;
      padding: 20px;
      background: #f8f9fa;
      border-radius: 16px;
    }
    .meal-selection h4 {
      margin: 0 0 16px;
      color: #2c3e50;
      font-size: 18px;
    }
    .food-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }
    .food-item {
      display: flex;
      align-items: center;
      padding: 12px 16px;
      background: #fff;
      border: 2px solid #e3e6ec;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.3s ease;
      font-weight: 500;
      text-transform: none;
      letter-spacing: normal;
    }
    .food-item:hover {
      border-color: #ff8c00;
      background: #fff6ea;
    }
    .food-item input {
      margin-right: 12px;
      width: auto;
      padding: 0;
    }
    .food-item input:checked + span,
    .food-item:has(input:checked) {
      border-color: #ff8c00;
      background: #fff6ea;
      color: #ff8c00;
    }
    .food-categories {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .category {
      padding: 16px;
      border-radius: 12px;
      border: 2px solid;
    }
    .category.good {
      border-color: #28a745;
      background: linear-gradient(135deg, #f8fff9, #f0fff4);
    }
    .category.medium {
      border-color: #ffc107;
      background: linear-gradient(135deg, #fffef8, #fffbf0);
    }
    .category.bad {
      border-color: #dc3545;
      background: linear-gradient(135deg, #fff8f8, #fff0f0);
    }
    .category h5 {
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 600;
    }
    .category.good h5 { color: #28a745; }
    .category.medium h5 { color: #e67e22; }
    .category.bad h5 { color: #dc3545; }
    .food-item.good:hover {
      border-color: #28a745;
      background: #f0fff4;
    }
    .food-item.medium:hover {
      border-color: #ffc107;
      background: #fffbf0;
    }
    .food-item.bad:hover {
      border-color: #dc3545;
      background: #fff0f0;
    }
    .food-item.bad {
      position: relative;
    }
    .food-item.bad::after {
      content: '⚠️';
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 16px;
    }
    .alert {
      position: fixed;
      top: 20px;
      right: 20px;
      background: #dc3545;
      color: white;
      padding: 16px 20px;
      border-radius: 12px;
      box-shadow: 0 8px 25px rgba(220, 53, 69, 0.3);
      z-index: 1000;
      animation: slideIn 0.3s ease;
      max-width: 300px;
    }
    .alert.warning {
      background: #ffc107;
      color: #333;
    }
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    .calorie-calculator {
      background: linear-gradient(135deg, #f8f9fa, #e9ecef);
      border: 2px solid #ff8c00;
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 32px;
      position: sticky;
      top: 20px;
      z-index: 100;
    }
    .calorie-calculator h4 {
      margin: 0 0 16px;
      color: #ff8c00;
      text-align: center;
      font-size: 18px;
    }
    .calorie-summary {
      display: grid;
      gap: 8px;
    }
    .calorie-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: rgba(255, 255, 255, 0.7);
      border-radius: 8px;
      font-size: 14px;
    }
    .calorie-total {
      border-top: 2px solid #ff8c00;
      margin-top: 8px;
      padding-top: 12px;
      font-weight: 600;
      font-size: 16px;
    }
    .calorie-count {
      font-weight: 600;
      color: #2c3e50;
    }
    .calorie-count.total {
      color: #ff8c00;
      font-size: 18px;
    }
    .meal-name {
      color: #555;
    }
    .motivation-section {
      text-align: center;
      margin-bottom: 32px;
      padding: 24px;
      background: linear-gradient(135deg, #fff6ea, #fef9f0);
      border-radius: 16px;
      border: 2px solid #ff8c00;
    }
    .motivation-text {
      font-size: 16px;
      line-height: 1.6;
      color: #2c3e50;
      margin: 16px 0 0;
    }
    .health-analysis {
      background: #f8f9fa;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 24px;
      border: 2px solid #e9ecef;
    }
    .health-analysis h4 {
      margin: 0 0 16px;
      color: #2c3e50;
      text-align: center;
    }
    .imc-info {
      text-align: center;
      margin-bottom: 20px;
      font-size: 18px;
    }
    .health-bar {
      margin: 20px 0;
    }
    .health-scale {
      position: relative;
      height: 12px;
      border-radius: 6px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      background: linear-gradient(to right, #3498db 25%, #27ae60 25% 50%, #f39c12 50% 75%, #e74c3c 75%);
    }
    .health-indicator {
      position: absolute;
      top: -4px;
      width: 20px;
      height: 20px;
      background: #2c3e50;
      border-radius: 50%;
      border: 3px solid #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      transition: left 0.5s ease;
      transform: translateX(-50%);
    }
    .scale-labels {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr 1fr;
      gap: 8px;
      margin-top: 12px;
      text-align: center;
    }
    .scale-label {
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 8px;
      color: white;
      text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    .scale-label.abaixo { background: #3498db; }
    .scale-label.normal { background: #27ae60; }
    .scale-label.sobrepeso { background: #f39c12; }
    .scale-label.obeso { background: #e74c3c; }
    .profile-summary {
      background: #fff;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 24px;
      border: 2px solid #e9ecef;
    }
    .profile-summary h4 {
      margin: 0 0 20px;
      color: #2c3e50;
      text-align: center;
    }
    .profile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
    }
    .profile-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: #f8f9fa;
      border-radius: 12px;
      border: 1px solid #e9ecef;
    }
    .profile-label {
      font-weight: 600;
      color: #555;
    }
    .profile-value {
      font-weight: 700;
      color: #2c3e50;
    }
    .exclusive-plan {
      background: linear-gradient(135deg, #fff6ea, #fef9f0);
      border: 2px solid #ff8c00;
      border-radius: 16px;
      padding: 32px 24px;
      margin: 24px 0;
      text-align: center;
    }
    .plan-header h4 {
      margin: 0 0 8px;
      color: #ff8c00;
      font-size: 24px;
      font-weight: 700;
    }
    .plan-subtitle {
      color: #666;
      font-size: 16px;
      margin: 0 0 32px;
      line-height: 1.5;
    }
    .benefits-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .benefit-item {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 20px;
      background: rgba(255, 255, 255, 0.8);
      border-radius: 12px;
      text-align: left;
      border: 1px solid rgba(255, 140, 0, 0.2);
    }
    .benefit-icon {
      font-size: 32px;
      flex-shrink: 0;
    }
    .benefit-content h5 {
      margin: 0 0 8px;
      color: #2c3e50;
      font-size: 16px;
      font-weight: 600;
    }
    .benefit-content p {
      margin: 0;
      color: #666;
      font-size: 14px;
      line-height: 1.4;
    }
    .plan-highlight {
      background: linear-gradient(135deg, #ff8c00, #ffa500);
      color: white;
      padding: 16px 24px;
      border-radius: 12px;
      font-size: 18px;
      box-shadow: 0 4px 15px rgba(255, 140, 0, 0.3);
    }
    @media (max-width: 768px) {
      .benefits-grid {
        grid-template-columns: 1fr;
        gap: 16px;
      }
      .benefit-item {
        padding: 16px;
      }
      .exclusive-plan {
        padding: 24px 16px;
      }
    }
    .food-calories {
      font-size: 12px;
      color: #666;
      font-weight: normal;
      margin-left: auto;
    }
    .food-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      background: #fff;
      border: 2px solid #e3e6ec;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.3s ease;
      font-weight: 500;
      text-transform: none;
      letter-spacing: normal;
    }
    @media (max-width: 768px) {
      .wrap { padding: 20px 16px; }
      .card { padding: 24px 20px; }
      .row { gap: 16px; }
      .col { min-width: 100%; }
      .btn-group { flex-direction: column; }
      .btn { width: 100%; }
      h1 { font-size: 28px; }
    }
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="steps">
      <div class="dot active" id="d1"></div>
      <div class="dot" id="d2"></div>
      <div class="dot" id="d3"></div>
      <div class="dot" id="d4"></div>
      <div class="dot" id="d5"></div>
      <div class="dot" id="d6"></div>
    </div>
    <div style="background: linear-gradient(135deg, #fff6ea, #fef9f0); border: 2px solid #ff8c00; border-radius: 16px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <h3 style="color: #ff8c00; margin: 0 0 12px;">🎯 Dados Científicos Sobre Emagrecimento</h3>
      <p style="margin: 0; color: #2c3e50; font-size: 14px; line-height: 1.5;">Estudos mostram que <strong>80% do emagrecimento</strong> vem da alimentação e apenas <strong>20% dos exercícios</strong>. Nosso sistema analisa suas escolhas alimentares e mostra exatamente quantos % você precisa melhorar para atingir seus objetivos.</p>
    </div>
    <h1>Monte seu plano personalizado</h1>
    <div id="s1">
      <div class="row">
        <div class="col"><label>Seu nome</label><input id="nome" placeholder="Digite seu nome" /></div>
        <div class="col"><label>E-mail</label><input id="email" type="email" placeholder="seu@email.com" /></div>
        <div class="col"><label>WhatsApp</label><input id="whatsapp" type="tel" placeholder="(11) 99999-9999" /></div>
      </div>
      <div class="row">
        <div class="col"><label>Idade</label><input id="idade" type="number" min="10" max="100" placeholder="Ex: 25"/></div>
        <div class="col"><label>Peso (kg)</label><input id="peso" type="number" step="0.1" placeholder="Ex: 70.5" /></div>
        <div class="col"><label>Altura (cm)</label><input id="altura" type="number" placeholder="Ex: 175" /></div>
      </div>
      <div style="margin-top:12px" class="grid2">
        <div class="option" data-sexo="masculino">Masculino</div>
        <div class="option" data-sexo="feminino">Feminino</div>
      </div>
      <div class="btn-group">
        <button class="btn" onclick="next(2)">Continuar →</button>
      </div>
    </div>

    <div id="s2" class="hidden">
      <div style="background: linear-gradient(135deg, #e8f5e8, #f0fff0); border: 2px solid #28a745; border-radius: 16px; padding: 20px; margin-bottom: 24px; text-align: center;">
        <h3 style="color: #28a745; margin: 0 0 12px;">💡 Fato Científico</h3>
        <p style="margin: 0; color: #2c3e50; font-size: 14px; line-height: 1.5;">Pesquisas mostram que pessoas que definem <strong>objetivos específicos</strong> têm <strong>42% mais chances</strong> de alcançá-los. Definir se você quer emagrecer, manter ou ganhar peso é o primeiro passo para o sucesso!</p>
      </div>
      <h3>Qual é o seu objetivo?</h3>
      <div class="grid2">
        <div class="option" data-objetivo="emagrecer">🎯 Emagrecer</div>
        <div class="option" data-objetivo="manter">⚖️ Manter Peso</div>
        <div class="option" data-objetivo="ganhar">💪 Ganhar Massa</div>
      </div>
      <div class="btn-group">
        <button class="btn outline" onclick="back(1)">← Voltar</button>
        <button class="btn" onclick="next(3)">Continuar →</button>
      </div>
    </div>

    <div id="s3" class="hidden">
      <div style="background: linear-gradient(135deg, #fff3e0, #fef7f0); border: 2px solid #ff9800; border-radius: 16px; padding: 20px; margin-bottom: 24px; text-align: center;">
        <h3 style="color: #ff9800; margin: 0 0 12px;">🔥 Metabolismo em Ação</h3>
        <p style="margin: 0; color: #2c3e50; font-size: 14px; line-height: 1.5;">Seu <strong>metabolismo basal</strong> representa <strong>60-75%</strong> do gasto calórico diário, mesmo em repouso! Exercícios regulares podem aumentar esse gasto em até <strong>15%</strong> por até 48 horas após o treino.</p>
      </div>
      <h3>Nível de atividade física</h3>
      <select id="atividade">
        <option value="sedentario">🛋️ Sedentário (pouco ou nenhum exercício)</option>
        <option value="iniciante">🚶 Iniciante (1-2x por semana)</option>
        <option value="intermediario">🏃 Intermediário (3-4x por semana)</option>
        <option value="avancado">🏋️ Avançado (5+ vezes por semana)</option>
      </select>
      <div class="btn-group">
        <button class="btn outline" onclick="back(2)">← Voltar</button>
        <button class="btn" onclick="next(4)">Continuar →</button>
      </div>
    </div>

    <div id="s4" class="hidden">
      <h3>Escolha seus alimentos preferidos</h3>
      <p style="text-align:center;color:#666;margin-bottom:24px">Selecione os alimentos que você gosta de comer em cada refeição</p>
      
      <!-- Calculadora de Calorias -->
      <div class="calorie-calculator">
        <h4>📈 Análise Nutricional</h4>
        <div class="calorie-summary">
          <div class="calorie-item">
            <span class="meal-name">☕ Café da Manhã:</span>
            <span class="calorie-count" id="cal-cafe">0 kcal</span>
          </div>
          <div class="calorie-item">
            <span class="meal-name">🍽️ Almoço:</span>
            <span class="calorie-count" id="cal-almoco">0 kcal</span>
          </div>
          <div class="calorie-item">
            <span class="meal-name">🥪 Lanche:</span>
            <span class="calorie-count" id="cal-lanche">0 kcal</span>
          </div>
          <div class="calorie-item">
            <span class="meal-name">🌙 Jantar:</span>
            <span class="calorie-count" id="cal-jantar">0 kcal</span>
          </div>
          <div class="calorie-total">
            <span class="meal-name">Total do Dia:</span>
            <span class="calorie-count total" id="cal-total">0 kcal</span>
          </div>
          <div class="calorie-item" style="border-top: 1px solid #ff8c00; margin-top: 8px; padding-top: 8px;">
            <span class="meal-name" id="cal-percentage">0% do alvo diário</span>
          </div>
          <div class="calorie-item">
            <span class="meal-name" id="cal-burn" style="font-size: 12px;">Defina seu objetivo primeiro</span>
          </div>
        </div>
        <div id="recommendations" style="display:none; margin-top: 12px; padding: 12px; background: #fff3cd; border-radius: 8px;"></div>
      </div>
      
      <div class="meal-selection">
        <h4>☕ Café da Manhã</h4>
        <div class="food-categories">
          <div class="category good">
            <h5>✅ Opções Saudáveis</h5>
            <div class="food-grid">
              <label class="food-item good"><input type="checkbox" name="cafe" value="Pão integral" data-category="good"> Pão integral <span class="food-calories">(280 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="cafe" value="Cuscuz com ovo" data-category="good"> Cuscuz com ovo <span class="food-calories">(320 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="cafe" value="Tapioca simples" data-category="good"> Tapioca simples <span class="food-calories">(200 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="cafe" value="Iogurte natural" data-category="good"> Iogurte natural <span class="food-calories">(150 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="cafe" value="Fruta (banana, maçã, mamão)" data-category="good"> Fruta (banana, maçã, mamão) <span class="food-calories">(100 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="cafe" value="Café preto sem açúcar" data-category="good"> Café preto sem açúcar <span class="food-calories">(5 kcal)</span></label>
            </div>
          </div>
          <div class="category medium">
            <h5>⚖️ Opções Medianas</h5>
            <div class="food-grid">
              <label class="food-item medium"><input type="checkbox" name="cafe" value="Pão francês com margarina" data-category="medium"> Pão francês com margarina <span class="food-calories">(350 kcal)</span></label>
              <label class="food-item medium"><input type="checkbox" name="cafe" value="Café com leite adoçado" data-category="medium"> Café com leite adoçado <span class="food-calories">(180 kcal)</span></label>
            </div>
          </div>
          <div class="category bad">
            <h5>❌ Evite Estes</h5>
            <div class="food-grid">
              <label class="food-item bad"><input type="checkbox" name="cafe" value="Biscoito recheado" data-category="bad"> Biscoito recheado <span class="food-calories">(450 kcal)</span></label>
              <label class="food-item bad"><input type="checkbox" name="cafe" value="Achocolatado com açúcar" data-category="bad"> Achocolatado com açúcar <span class="food-calories">(250 kcal)</span></label>
            </div>
          </div>
        </div>
      </div>

      <div class="meal-selection">
        <h4>🍽️ Almoço</h4>
        <div class="food-categories">
          <div class="category good">
            <h5>✅ Opções Saudáveis</h5>
            <div class="food-grid">
              <label class="food-item good"><input type="checkbox" name="almoco" value="Arroz com feijão" data-category="good"> Arroz com feijão <span class="food-calories">(400 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="almoco" value="Frango grelhado ou cozido" data-category="good"> Frango grelhado ou cozido <span class="food-calories">(200 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="almoco" value="Ovo cozido ou mexido" data-category="good"> Ovo cozido ou mexido <span class="food-calories">(150 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="almoco" value="Salada simples" data-category="good"> Salada simples <span class="food-calories">(50 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="almoco" value="Abóbora, batata-doce ou mandioca" data-category="good"> Abóbora, batata-doce ou mandioca <span class="food-calories">(120 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="almoco" value="Peixe assado ou cozido" data-category="good"> Peixe assado ou cozido <span class="food-calories">(180 kcal)</span></label>
            </div>
          </div>
          <div class="category medium">
            <h5>⚖️ Opções Medianas</h5>
            <div class="food-grid">
              <label class="food-item medium"><input type="checkbox" name="almoco" value="Carne bovina (patinho ou acém)" data-category="medium"> Carne bovina (patinho ou acém) <span class="food-calories">(250 kcal)</span></label>
              <label class="food-item medium"><input type="checkbox" name="almoco" value="Macarrão com molho de tomate" data-category="medium"> Macarrão com molho de tomate <span class="food-calories">(350 kcal)</span></label>
            </div>
          </div>
          <div class="category bad">
            <h5>❌ Evite Estes</h5>
            <div class="food-grid">
              <label class="food-item bad"><input type="checkbox" name="almoco" value="Frituras (coxinha, pastel, batata frita)" data-category="bad"> Frituras (coxinha, pastel, batata frita) <span class="food-calories">(600 kcal)</span></label>
              <label class="food-item bad"><input type="checkbox" name="almoco" value="Refrigerante ou suco de pozinho" data-category="bad"> Refrigerante ou suco de pozinho <span class="food-calories">(150 kcal)</span></label>
            </div>
          </div>
        </div>
      </div>

      <div class="meal-selection">
        <h4>🥪 Café da Tarde</h4>
        <div class="food-categories">
          <div class="category good">
            <h5>✅ Opções Saudáveis</h5>
            <div class="food-grid">
              <label class="food-item good"><input type="checkbox" name="lanche" value="Pão integral com ovo mexido" data-category="good"> Pão integral com ovo mexido <span class="food-calories">(300 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="lanche" value="Fruta (banana, maçã, laranja)" data-category="good"> Fruta (banana, maçã, laranja) <span class="food-calories">(80 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="lanche" value="Iogurte natural com aveia" data-category="good"> Iogurte natural com aveia <span class="food-calories">(200 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="lanche" value="Tapioca com queijo branco" data-category="good"> Tapioca com queijo branco <span class="food-calories">(250 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="lanche" value="Cuscuz pequeno com ovo" data-category="good"> Cuscuz pequeno com ovo <span class="food-calories">(200 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="lanche" value="Café preto sem açúcar" data-category="good"> Café preto sem açúcar <span class="food-calories">(5 kcal)</span></label>
            </div>
          </div>
          <div class="category medium">
            <h5>⚖️ Opções Medianas</h5>
            <div class="food-grid">
              <label class="food-item medium"><input type="checkbox" name="lanche" value="Pão francês com manteiga" data-category="medium"> Pão francês com manteiga <span class="food-calories">(320 kcal)</span></label>
              <label class="food-item medium"><input type="checkbox" name="lanche" value="Bolo caseiro simples" data-category="medium"> Bolo caseiro simples <span class="food-calories">(280 kcal)</span></label>
            </div>
          </div>
          <div class="category bad">
            <h5>❌ Evite Estes</h5>
            <div class="food-grid">
              <label class="food-item bad"><input type="checkbox" name="lanche" value="Biscoito recheado ou wafer" data-category="bad"> Biscoito recheado ou wafer <span class="food-calories">(400 kcal)</span></label>
              <label class="food-item bad"><input type="checkbox" name="lanche" value="Refrigerante ou suco industrializado" data-category="bad"> Refrigerante ou suco industrializado <span class="food-calories">(140 kcal)</span></label>
            </div>
          </div>
        </div>
      </div>

      <div class="meal-selection">
        <h4>🌙 Jantar</h4>
        <div class="food-categories">
          <div class="category good">
            <h5>✅ Opções Saudáveis</h5>
            <div class="food-grid">
              <label class="food-item good"><input type="checkbox" name="jantar" value="Arroz com feijão (porção moderada)" data-category="good"> Arroz com feijão (porção moderada) <span class="food-calories">(300 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="jantar" value="Frango grelhado ou desfiado" data-category="good"> Frango grelhado ou desfiado <span class="food-calories">(180 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="jantar" value="Ovo cozido ou omelete simples" data-category="good"> Ovo cozido ou omelete simples <span class="food-calories">(150 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="jantar" value="Salada de verduras" data-category="good"> Salada de verduras <span class="food-calories">(40 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="jantar" value="Legumes cozidos" data-category="good"> Legumes cozidos <span class="food-calories">(80 kcal)</span></label>
              <label class="food-item good"><input type="checkbox" name="jantar" value="Sopa caseira de legumes" data-category="good"> Sopa caseira de legumes <span class="food-calories">(120 kcal)</span></label>
            </div>
          </div>
          <div class="category medium">
            <h5>⚖️ Opções Medianas</h5>
            <div class="food-grid">
              <label class="food-item medium"><input type="checkbox" name="jantar" value="Sanduíche caseiro simples" data-category="medium"> Sanduíche caseiro simples <span class="food-calories">(350 kcal)</span></label>
              <label class="food-item medium"><input type="checkbox" name="jantar" value="Macarrão alho e óleo" data-category="medium"> Macarrão alho e óleo <span class="food-calories">(400 kcal)</span></label>
            </div>
          </div>
          <div class="category bad">
            <h5>❌ Evite Estes</h5>
            <div class="food-grid">
              <label class="food-item bad"><input type="checkbox" name="jantar" value="Pizza de fast-food" data-category="bad"> Pizza de fast-food <span class="food-calories">(800 kcal)</span></label>
              <label class="food-item bad"><input type="checkbox" name="jantar" value="Hambúrguer com batata frita" data-category="bad"> Hambúrguer com batata frita <span class="food-calories">(900 kcal)</span></label>
            </div>
          </div>
        </div>
      </div>

      <div class="btn-group">
        <button class="btn outline" onclick="back(3)">← Voltar</button>
        <button class="btn" onclick="buildPreview()" id="preview-btn">Ver Prévia →</button>
      </div>
    </div>

    <div id="s5" class="hidden">
      <div class="motivation-section">
        <h3 id="motivation-title">💪 Seu plano personalizado</h3>
        <p class="motivation-text" id="motivation-text"></p>
      </div>
      
      <div class="health-analysis">
        <h4>📈 Análise de Saúde</h4>
        <div class="imc-info">
          <span>Seu IMC: <strong id="imc-value"></strong></span>
        </div>
        <div class="health-bar">
          <div class="health-scale">
            <div class="health-indicator" id="health-indicator"></div>
          </div>
          <div class="scale-labels">
            <div class="scale-label abaixo">Abaixo</div>
            <div class="scale-label normal">Normal</div>
            <div class="scale-label sobrepeso">Sobrepeso</div>
            <div class="scale-label obeso">Obeso</div>
          </div>
        </div>
      </div>
      
      <div class="profile-summary">
        <h4>📝 Resumo do seu Perfil</h4>
        <div class="profile-grid">
          <div class="profile-item">
            <span class="profile-label">📏 Altura:</span>
            <span class="profile-value" id="profile-altura"></span>
          </div>
          <div class="profile-item">
            <span class="profile-label">⚖️ Peso:</span>
            <span class="profile-value" id="profile-peso"></span>
          </div>
          <div class="profile-item">
            <span class="profile-label">🎂 Idade:</span>
            <span class="profile-value" id="profile-idade"></span>
          </div>
          <div class="profile-item">
            <span class="profile-label">🏋️ Treino:</span>
            <span class="profile-value" id="profile-treino"></span>
          </div>
        </div>
      </div>
      
      <div class="exclusive-plan">
        <div class="plan-header">
          <h4>🎯 Seu Plano Nutricional Está Pronto!</h4>
          <p class="plan-subtitle">Baseado nas suas respostas, nossa IA criou um plano 100% personalizado para você</p>
        </div>
        
        <div class="benefits-grid">
          <div class="benefit-item">
            <div class="benefit-icon">🤖</div>
            <div class="benefit-content">
              <h5>Plano Gerado por IA</h5>
              <p>Algoritmo avançado analisa suas preferências e cria um plano único</p>
            </div>
          </div>
          
          <div class="benefit-item">
            <div class="benefit-icon">📊</div>
            <div class="benefit-content">
              <h5>Cálculo Calórico Preciso</h5>
              <p>Quantas calorias você precisa consumir baseado no seu objetivo</p>
            </div>
          </div>
          
          <div class="benefit-item">
            <div class="benefit-icon">🛒</div>
            <div class="benefit-content">
              <h5>Lista de Compras Semanal</h5>
              <p>Todos os ingredientes organizados para facilitar suas compras</p>
            </div>
          </div>
          
          <div class="benefit-item">
            <div class="benefit-icon">😴</div>
            <div class="benefit-content">
              <h5>Guia de Sono Otimizado</h5>
              <p>Horários e dicas para melhorar sua qualidade de sono</p>
            </div>
          </div>
          
          <div class="benefit-item">
            <div class="benefit-icon">💊</div>
            <div class="benefit-content">
              <h5>Suplementos Recomendados</h5>
              <p>Os melhores suplementos para potencializar seus resultados</p>
            </div>
          </div>
          
          <div class="benefit-item">
            <div class="benefit-icon">💰</div>
            <div class="benefit-content">
              <h5>Melhores Preços</h5>
              <p>Onde comprar seus suplementos com os menores preços do mercado</p>
            </div>
          </div>
        </div>
        
        <div class="plan-highlight">
          <p>✨ <strong>Totalmente Gratuito!</strong> - Seu plano personalizado sem custo</p>
        </div>
      </div>
      <div class="btn-group">
        <button class="btn outline" onclick="back(4)">← Voltar</button>
        <button class="btn" onclick="goToFinalPlan()">📄 Ver Plano Completo</button>
      </div>
    </div>

    <div id="s6" class="hidden">
      <div style="text-align:center">
        <h3>🎉 Obrigado!</h3>
        <p>Se o pagamento foi aprovado, seu PDF está pronto para download:</p>
        <div id="download"></div>
      </div>
    </div>
  </div>
</div>
<script>
let respostas = {};

// Toggle de opções
for (const el of document.querySelectorAll('.option')){
  el.addEventListener('click', () => {
    const group = el.dataset.sexo? 'sexo' : (el.dataset.objetivo? 'objetivo' : null);
    if(group){
      document.querySelectorAll(`[data-${group}]`).forEach(x=>x.classList.remove('active'));
      el.classList.add('active');
      respostas[group] = el.dataset[group];
    }
  });
}

// Sistema de alerta para alimentos ruins
function showAlert(message, type = 'error') {
  const alert = document.createElement('div');
  alert.className = `alert ${type}`;
  alert.innerHTML = message;
  document.body.appendChild(alert);
  
  setTimeout(() => {
    alert.remove();
  }, 4000);
}

// Carrega dados dos alimentos do servidor
let foodsData = {};
let dailyTarget = 0;

async function loadFoodsData() {
  try {
    const response = await fetch('/api/foods');
    foodsData = await response.json();
  } catch (error) {
    console.error('Erro ao carregar dados dos alimentos:', error);
  }
}

// Carrega dados na inicialização
loadFoodsData();

// Função para atualizar calculadora de calorias
function atualizarCalculadora() {
  const refeicoes = ['cafe', 'almoco', 'lanche', 'jantar'];
  let totalDia = 0;
  let recomendacoes = [];
  
  refeicoes.forEach(refeicao => {
    const checkboxes = document.querySelectorAll(`input[name="${refeicao}"]:checked`);
    let totalRefeicao = 0;
    
    checkboxes.forEach(checkbox => {
      const alimento = checkbox.value;
      const foodInfo = foodsData.foods?.[alimento] || {calories: 300, category: 'medium'};
      totalRefeicao += foodInfo.calories;
      
      // Gera recomendação para alimentos ruins
      if (foodInfo.category === 'bad') {
        const alternativas = foodsData.alternatives?.[alimento];
        if (alternativas && alternativas.length > 0) {
          const melhorAlternativa = alternativas[0];
          const altInfo = foodsData.foods?.[melhorAlternativa] || {calories: 200};
          recomendacoes.push(`Em vez de ${alimento} (${foodInfo.calories} kcal), experimente ${melhorAlternativa} (${altInfo.calories} kcal)`);
        }
      }
    });
    
    document.getElementById(`cal-${refeicao}`).textContent = `${totalRefeicao} kcal`;
    totalDia += totalRefeicao;
  });
  
  document.getElementById('cal-total').textContent = `${totalDia} kcal`;
  
  // Calcula porcentagem do alvo diário
  if (dailyTarget > 0) {
    const porcentagem = Math.round((totalDia / dailyTarget) * 100);
    document.getElementById('cal-percentage').textContent = `${porcentagem}% do alvo diário`;
    
    // Calcula calorias para queimar
    const paraQueimar = Math.max(0, totalDia - dailyTarget);
    if (paraQueimar > 0) {
      document.getElementById('cal-burn').textContent = `Precisa queimar ${paraQueimar} kcal para manter o déficit`;
    } else {
      const restante = dailyTarget - totalDia;
      document.getElementById('cal-burn').textContent = `Ainda pode consumir ${restante} kcal hoje`;
    }
  }
  
  // Mostra recomendações
  const recDiv = document.getElementById('recommendations');
  if (recomendacoes.length > 0) {
    recDiv.innerHTML = '<h5>✨ Recomendações:</h5>' + recomendacoes.map(r => `<p style="color:#dc3545;font-size:12px;margin:4px 0;">${r}</p>`).join('');
    recDiv.style.display = 'block';
  } else {
    recDiv.style.display = 'none';
  }
  
  // Adiciona classe visual
  const totalElement = document.getElementById('cal-total');
  if (totalDia > dailyTarget * 1.2) {
    totalElement.style.color = '#dc3545';
  } else if (totalDia > dailyTarget) {
    totalElement.style.color = '#ffc107';
  } else {
    totalElement.style.color = '#ff8c00';
  }
}

// Monitor de seleção de alimentos
document.addEventListener('change', (e) => {
  if (e.target.type === 'checkbox' && e.target.name) {
    // Atualiza calculadora
    atualizarCalculadora();
    
    // Alerta para alimentos ruins
    if (e.target.dataset.category === 'bad' && e.target.checked) {
      showAlert('⚠️ Atenção! Este alimento não é recomendado para uma dieta saudável. Considere escolher opções mais nutritivas.', 'warning');
    }
  }
});

function setStep(i){
  for(let s=1; s<=6; s++){
    const step = document.getElementById('s'+s);
    const dot = document.getElementById('d'+s);
    
    if(s === i) {
      step.classList.remove('hidden');
      step.classList.add('fade-in');
    } else {
      step.classList.add('hidden');
      step.classList.remove('fade-in');
    }
    
    dot.classList.toggle('active', s<=i);
  }
}
function next(i){
  if(i===2){
    // Validação dos campos obrigatórios
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();
    const whatsapp = document.getElementById('whatsapp').value.trim();
    const idade = parseInt(document.getElementById('idade').value||'0');
    const peso = parseFloat(document.getElementById('peso').value||'0');
    const altura = parseInt(document.getElementById('altura').value||'0');
    
    // Validação de email (regex simples)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      alert('Preencha um e-mail válido e um WhatsApp válido.');
      return;
    }
    
    // Validação de WhatsApp (10-13 dígitos)
    const whatsappClean = whatsapp.replace(/[^0-9]/g, '');
    if (whatsappClean.length < 10 || whatsappClean.length > 13) {
      alert('Preencha um e-mail válido e um WhatsApp válido.');
      return;
    }
    
    // Validação dos outros campos
    if (!nome || idade < 10 || peso < 30 || altura < 100) {
      alert('Por favor, preencha todos os campos corretamente.');
      return;
    }
    
    respostas.nome = nome;
    respostas.email = email;
    respostas.whatsapp = whatsappClean;
    respostas.idade = idade;
    respostas.peso = peso;
    respostas.altura = altura;
    
    console.log('Dados salvos no passo 1:', respostas);
  }
  
  if(i===3){
    // Verifica se objetivo foi selecionado
    if(!respostas.objetivo){
      alert('Por favor, selecione seu objetivo.');
      return;
    }
  }
  
  if(i===4){
    // Verifica se atividade foi selecionada
    if(!document.getElementById('atividade').value){
      alert('Por favor, selecione seu nível de atividade física.');
      return;
    }
    respostas.atividade = document.getElementById('atividade').value;
  }
  
  setStep(i);
}
function back(i){ setStep(i); }

async function buildPreview(){
  try {
    // Debug: mostra todos os dados coletados
    console.log('Dados atuais em respostas:', respostas);
    
    // Verifica campos obrigatórios um por um
    const camposObrigatorios = ['nome', 'idade', 'peso', 'altura', 'sexo', 'objetivo'];
    const camposFaltando = [];
    
    camposObrigatorios.forEach(campo => {
      if (!respostas[campo]) {
        camposFaltando.push(campo);
      }
    });
    
    if (camposFaltando.length > 0) {
      console.error('Campos faltando:', camposFaltando);
      alert(`Campos faltando: ${camposFaltando.join(', ')}. Por favor, volte e preencha todos os dados.`);
      return;
    }
    
    // Coleta atividade física
    respostas.atividade = document.getElementById('atividade').value;
    
    // Coleta alimentos selecionados
    const alimentosSelecionados = {};
    ['cafe', 'almoco', 'lanche', 'jantar'].forEach(meal => {
      const checkboxes = document.querySelectorAll(`input[name="${meal}"]:checked`);
      alimentosSelecionados[meal] = Array.from(checkboxes).map(cb => cb.value);
    });
    
    respostas.alimentos = alimentosSelecionados;
    
    console.log('Enviando dados:', respostas); // Debug
    
    const r = await fetch('/api/plan', {
      method: 'POST', 
      headers: {'Content-Type': 'application/json'}, 
      body: JSON.stringify(respostas)
    });
    
    if (!r.ok) {
      const errorData = await r.json().catch(() => ({}));
      console.error('Erro do servidor:', errorData);
      throw new Error(`Erro HTTP: ${r.status} - ${errorData.error || 'Erro desconhecido'}`);
    }
    
    const data = await r.json();
    console.log('Resposta recebida:', data); // Debug
    
    if (!data.metas || !data.metas.imc) {
      throw new Error('Dados incompletos recebidos do servidor');
    }
    
    window._plan = data;
    dailyTarget = data.metas.alvo; // Define o alvo diário
    
    // Atualiza calculadora com o novo alvo
    atualizarCalculadora();
    
    // Atualiza informações motivacionais e de saúde
    document.getElementById('motivation-text').textContent = data.metas.frase_motivacional;
    document.getElementById('imc-value').textContent = data.metas.imc.valor;
    
    // Atualiza barra de saúde
    const indicator = document.getElementById('health-indicator');
    indicator.style.left = `${data.metas.imc.posicao}%`;
    indicator.style.background = data.metas.imc.cor;
    
    // Atualiza resumo do perfil
    document.getElementById('profile-altura').textContent = `${respostas.altura} cm`;
    document.getElementById('profile-peso').textContent = `${respostas.peso} kg`;
    document.getElementById('profile-idade').textContent = `${respostas.idade} anos`;
    
    const nivelTreino = {
      'sedentario': 'Sedentário',
      'iniciante': 'Iniciante',
      'intermediario': 'Intermediário', 
      'avancado': 'Avançado'
    };
    document.getElementById('profile-treino').textContent = nivelTreino[respostas.atividade];
    
    setStep(5);
  } catch (error) {
    console.error('Erro detalhado:', error);
    alert(`Erro ao gerar prévia: ${error.message}`);
  }
}



async function goToFinalPlan() {
  try {
    // Garante que os dados estão processados
    if (!window._plan) {
      await buildPreview();
    }
    
    // Salva dados e gera PDF diretamente
    const r = await fetch('/gerar-plano', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(respostas)
    });
    
    if (r.ok) {
      // Redireciona para página de sucesso
      window.location = '/plano-completo';
    } else {
      throw new Error('Erro ao processar plano');
    }
  } catch (error) {
    console.error('Erro:', error);
    alert('Erro ao processar dados. Tente novamente.');
  }
}


</script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.get('/api/foods')
def api_foods():
    """Retorna dados dos alimentos em JSON."""
    return jsonify(load_foods_data())


@app.post('/api/plan')
def api_plan():
    try:
        respostas = request.get_json(force=True)
        if not respostas: return jsonify({"error": "Dados ausentes"}), 400
        
        required = ['nome', 'idade', 'peso', 'altura', 'sexo', 'objetivo', 'atividade']
        missing = [f for f in required if not respostas.get(f)]
        if missing: return jsonify({"error": f"Campos ausentes: {', '.join(missing)}"}), 400
        
        metas = calcular_alvo_kcal(respostas)
        plano = montar_refeicoes(metas['alvo'], respostas.get('alimentos', {}))
        
        return jsonify({"metas": metas, "plano": plano})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post('/api/save-session')
def save_session():
    data = request.get_json(force=True)
    respostas = data.get('respostas', {})
    salvar_lead(respostas)
    
    session_id = str(uuid.uuid4())
    with open(f"/tmp/{session_id}.json", 'w', encoding='utf-8') as f:
        json.dump({'respostas': respostas, 'plan': data.get('plan', {})}, f)
    
    return jsonify({"session_id": session_id})

@app.get('/resultados/<session_id>')
def resultados(session_id):
    session_path = f"/tmp/{session_id}.json"
    if not os.path.exists(session_path): return "Sessão expirada.", 404
    
    with open(session_path, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    
    respostas = session_data['respostas']
    metas = calcular_alvo_kcal(respostas)
    alimentos = respostas.get('alimentos', {})
    
    return f"""
    <!doctype html>
    <html><head><meta charset="utf-8"><title>Resultados</title>
    <style>body{{font-family:Arial;padding:20px;background:#f5f5f5}}.card{{background:white;padding:20px;margin:10px 0;border-radius:8px}}.btn{{background:#ff8c00;color:white;padding:12px 24px;border:none;border-radius:6px;text-decoration:none;display:inline-block;margin:10px 5px}}</style>
    </head><body>
    <h1>📊 Seus Resultados</h1>
    <div class="card">
        <h2>Dados: {respostas.get('nome', '-')} | {respostas['objetivo'].title()} | {metas['alvo']} kcal/dia</h2>
        <p>IMC: {metas['imc']['valor']} - {metas['imc']['status']}</p>
        <a href="/final-plan/{session_id}" class="btn">Ver Plano Completo</a>
        <a href="/" class="btn" style="background:#666">Novo Quiz</a>
    </div></body></html>
    """

@app.get('/final-plan/<session_id>')
def final_plan(session_id):
    """Página final com análise completa e recomendações."""
    session_path = f"/tmp/{session_id}.json"
    if not os.path.exists(session_path):
        return "Sessão expirada.", 404
    
    with open(session_path, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    
    respostas = session_data['respostas']
    plan_data = session_data['plan']
    
    # Recalcula dados para garantir consistência
    metas = calcular_alvo_kcal(respostas)
    alimentos = respostas.get('alimentos', {})
    plano = montar_refeicoes(metas['alvo'], alimentos)
    
    # Análise de calorias consumidas
    analise_calorias = calcular_calorias_consumidas(alimentos)
    
    # Cálculos adicionais
    peso_ideal = calcular_peso_ideal(respostas['altura'], respostas['sexo'])
    agua_diaria = calcular_agua_diaria(respostas['peso'])
    
    porcentagem_consumo = round((analise_calorias['total_consumido'] / metas['alvo']) * 100)
    calorias_para_queimar = max(0, analise_calorias['total_consumido'] - metas['alvo'])
    
    return render_template_string(FINAL_PLAN_HTML, 
        respostas=respostas,
        metas=metas,
        plano=plano,
        analise_calorias=analise_calorias,
        peso_ideal=peso_ideal,
        agua_diaria=agua_diaria,
        porcentagem_consumo=porcentagem_consumo,
        calorias_para_queimar=calorias_para_queimar,
        session_id=session_id
    )



last_user_data = {}

@app.post('/gerar-plano')
def gerar_plano():
    global last_user_data
    try:
        respostas = request.get_json(force=True)
        if not respostas: return jsonify({"error": "Dados ausentes"}), 400
        salvar_lead(respostas)
        last_user_data = respostas
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get('/plano-completo')
def plano_completo():
    global last_user_data
    if not last_user_data: return redirect('/')
    
    try:
        metas = calcular_alvo_kcal(last_user_data)
        alimentos = last_user_data.get('alimentos', {})
        plano = montar_refeicoes(metas['alvo'], alimentos)
        analise_calorias = calcular_calorias_consumidas(alimentos)
        peso_ideal = calcular_peso_ideal(last_user_data['altura'], last_user_data['sexo'])
        agua_diaria = calcular_agua_diaria(last_user_data['peso'])
        
        porcentagem_consumo = round((analise_calorias['total_consumido'] / metas['alvo']) * 100) if metas['alvo'] > 0 else 0
        calorias_para_queimar = max(0, analise_calorias['total_consumido'] - metas['alvo'])
        
        return render_template_string(FINAL_PLAN_HTML, 
            respostas=last_user_data, metas=metas, plano=plano,
            analise_calorias=analise_calorias, peso_ideal=peso_ideal,
            agua_diaria=agua_diaria, porcentagem_consumo=porcentagem_consumo,
            calorias_para_queimar=calorias_para_queimar, session_id='current'
        )
    except Exception as e:
        return f"Erro ao gerar plano: {str(e)}", 500

@app.get('/gerar-pdf/<session_id>')
def gerar_pdf_route(session_id):
    global last_user_data
    if not last_user_data: return "Dados não encontrados.", 404
    
    try:
        metas = calcular_alvo_kcal(last_user_data)
        plano = montar_refeicoes(metas['alvo'], last_user_data.get('alimentos', {}))
        pdf_bytes = gerar_pdf(plano, last_user_data, metas)
        return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name='plano_personalizado.pdf', mimetype='application/pdf')
    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500





if __name__ == '__main__':
    app.run(debug=True)
