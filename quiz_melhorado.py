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
    """Calcula peso real da porção baseado em dados nutricionais reais"""
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

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, height - 2*cm, "Plano Personalizado")

    c.setFont("Helvetica", 11)
    y = height - 3*cm
    c.drawString(2*cm, y, f"Nome: {respostas.get('nome','-')}")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Objetivo: {respostas['objetivo'].title()} | Alvo: {metas['alvo']} kcal")
    y -= 0.5*cm
    c.drawString(2*cm, y, f"Peso: {respostas['peso']} kg | Altura: {respostas['altura']} cm | Idade: {respostas['idade']}")

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
        <p style="text-align: center; color: #dc3545; font-weight: 600;">
          ⚠️ Para manter o déficit, você precisa queimar pelo menos {{ calorias_para_queimar }} kcal hoje
        </p>
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
            <span>{{ opcao.descricao }}</span>
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
      margin: 0; padding: 0; line-height: 1.6; color: #2c3e50;
    }
    .wrap {
      max-width: 800px; margin: 0 auto; padding: 32px 24px; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }
    .card {
      background: #fff; border-radius: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,.08), 0 8px 25px rgba(0,0,0,.06);
      padding: 40px; margin-bottom: 16px; width: 100%;
      position: relative; overflow: hidden; transition: all 0.3s ease;
    }
    .card::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
      background: linear-gradient(90deg, #ff8c00, #ffa500);
    }
    .row { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }
    .col { flex: 1 1 200px; min-width: 200px; }
    .btn {
      background: linear-gradient(135deg, #ff8c00, #ffa500);
      border: none; color: #fff; padding: 16px 24px; border-radius: 12px;
      font-weight: 600; font-size: 16px; cursor: pointer; transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(255, 140, 0, 0.3);
    }
    .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(255, 140, 0, 0.4); }
    .btn.outline {
      background: transparent; color: #ff8c00; border: 2px solid #ff8c00; box-shadow: none;
    }
    .btn.outline:hover { background: rgba(255, 140, 0, 0.05); }
    .hidden { display: none; }
    input, select {
      width: 100%; padding: 16px 20px; border-radius: 12px; border: 2px solid #e3e6ec;
      font-size: 16px; transition: all 0.3s ease; background: #fafbfc;
    }
    input:focus, select:focus {
      outline: none; border-color: #ff8c00; background-color: #fff;
      box-shadow: 0 0 0 3px rgba(255, 140, 0, 0.1);
    }
    label {
      display: block; margin-bottom: 8px; font-weight: 600; color: #34495e;
      font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;
    }
    h1 {
      margin: 0 0 32px; font-size: 32px; font-weight: 700; text-align: center;
      background: linear-gradient(135deg, #2c3e50, #34495e);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    h3 { margin: 0 0 24px; font-size: 24px; font-weight: 600; text-align: center; color: #2c3e50; }
    .steps {
      display: flex; justify-content: center; gap: 12px; margin-bottom: 32px; padding: 0 20px;
    }
    .dot {
      width: 12px; height: 12px; border-radius: 50%; background: #e3e6ec;
      transition: all 0.3s ease; position: relative;
    }
    .dot.active {
      background: #ff8c00; transform: scale(1.2);
      box-shadow: 0 0 0 4px rgba(255, 140, 0, 0.2);
    }
    .grid2 {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px; margin-bottom: 24px;
    }
    .option {
      padding: 20px 24px; border: 2px solid #e3e6ec; border-radius: 16px;
      cursor: pointer; transition: all 0.3s ease; text-align: center;
      font-weight: 500; font-size: 16px; background: #fafbfc;
    }
    .option:hover { border-color: #ff8c00; transform: translateY(-2px); }
    .option.active {
      border-color: #ff8c00; background: #fff6ea; transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(255, 140, 0, 0.2);
    }
    .btn-group {
      display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin-top: 32px;
    }
    .fade-in { animation: fadeIn 0.5s ease-in; }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
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
      <p style="text-align:center;color:#666;margin-bottom:24px">Selecione os alimentos que você gosta de comer</p>
      <div class="btn-group">
        <button class="btn outline" onclick="back(3)">← Voltar</button>
        <button class="btn" onclick="goToFinalPlan()">📄 Ver Plano Completo</button>
      </div>
    </div>
  </div>
</div>
<script>
let respostas = {};

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

function setStep(i){
  for(let s=1; s<=5; s++){
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
    const nome = document.getElementById('nome').value.trim();
    const email = document.getElementById('email').value.trim();
    const whatsapp = document.getElementById('whatsapp').value.trim();
    const idade = parseInt(document.getElementById('idade').value||'0');
    const peso = parseFloat(document.getElementById('peso').value||'0');
    const altura = parseInt(document.getElementById('altura').value||'0');
    
    if (!nome || !email || !whatsapp || idade < 10 || peso < 30 || altura < 100) {
      alert('Por favor, preencha todos os campos corretamente.');
      return;
    }
    
    respostas.nome = nome;
    respostas.email = email;
    respostas.whatsapp = whatsapp;
    respostas.idade = idade;
    respostas.peso = peso;
    respostas.altura = altura;
  }
  
  if(i===3){
    if(!respostas.objetivo){
      alert('Por favor, selecione seu objetivo.');
      return;
    }
  }
  
  if(i===4){
    if(!document.getElementById('atividade').value){
      alert('Por favor, selecione seu nível de atividade física.');
      return;
    }
    respostas.atividade = document.getElementById('atividade').value;
  }
  
  setStep(i);
}

function back(i){ setStep(i); }

async function goToFinalPlan() {
  try {
    const r = await fetch('/gerar-plano', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(respostas)
    });
    
    if (r.ok) {
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