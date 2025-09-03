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

def calcular_calorias_consumidas(alimentos_selecionados: dict) -> dict:
    foods_data = load_foods_data()
    foods = foods_data.get('foods', {})
    
    total_consumido = 0
    recomendacoes = []
    
    for refeicao, alimentos in alimentos_selecionados.items():
        for alimento in alimentos:
            food_info = foods.get(alimento, {"calories": 300, "category": "medium"})
            total_consumido += food_info["calories"]
            
            if food_info["category"] == "bad":
                alternativas = foods_data.get('alternatives', {}).get(alimento, [])
                if alternativas:
                    alt_principal = alternativas[0]
                    alt_calorias = foods.get(alt_principal, {"calories": 200})["calories"]
                    recomendacoes.append({
                        "original": alimento,
                        "original_calorias": food_info["calories"],
                        "alternativa": alt_principal,
                        "alternativa_calorias": alt_calorias
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
  <title>Seu Plano Completo</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: Arial, sans-serif; background: #f6f7f9; margin: 0; padding: 20px; color: #2c3e50; }
    .container { max-width: 1200px; margin: 0 auto; }
    .card { background: #fff; border-radius: 16px; box-shadow: 0 8px 25px rgba(0,0,0,.1); padding: 32px; margin-bottom: 24px; }
    .header { text-align: center; margin-bottom: 32px; padding: 24px; background: linear-gradient(135deg, #ff8c00, #ffa500); border-radius: 16px; color: white; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
    .metric { text-align: center; padding: 20px; background: #f8f9fa; border-radius: 12px; border: 2px solid #ff8c00; }
    .metric-value { font-size: 24px; font-weight: bold; color: #ff8c00; }
    .metric-label { font-size: 14px; color: #666; margin-top: 8px; }
    .meal-analysis { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 32px; }
    .meal-card { background: #f8f9fa; border-radius: 12px; padding: 20px; border-left: 4px solid #ff8c00; }
    .meal-title { font-weight: 600; color: #2c3e50; margin-bottom: 12px; }
    .food-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin: 6px 0; background: white; border-radius: 6px; }
    .food-item.good { border-left: 3px solid #28a745; }
    .food-item.medium { border-left: 3px solid #ffc107; }
    .food-item.bad { border-left: 3px solid #dc3545; }
    .btn { background: linear-gradient(135deg, #ff8c00, #ffa500); color: white; padding: 16px 32px; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; text-align: center; margin: 16px 8px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎯 Seu Plano Nutricional Completo</h1>
      <p>Análise detalhada com quantidades exatas</p>
    </div>
    
    <div class="card">
      <h2>👤 Seu Perfil</h2>
      <div class="metrics">
        <div class="metric">
          <div class="metric-value">{{ respostas.peso }} kg</div>
          <div class="metric-label">Peso Atual</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ "%.1f"|format(peso_ideal) }} kg</div>
          <div class="metric-label">Peso Ideal</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ metas.imc.valor }}</div>
          <div class="metric-label">IMC - {{ metas.imc.status }}</div>
        </div>
        <div class="metric">
          <div class="metric-value">{{ metas.alvo }}</div>
          <div class="metric-label">Meta Diária (kcal)</div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <h2>🍽️ Plano Alimentar com Quantidades Exatas</h2>
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
              <strong>{{ opcao.descricao }}</strong><br>
              <small style="color: #666;">{{ opcao.quantidade }}</small>
            </div>
            <span>{{ opcao.kcal }} kcal</span>
          </div>
          {% endfor %}
        </div>
        {% endfor %}
      </div>
    </div>
    
    <div class="card" style="text-align: center;">
      <h2>📄 Baixe seu Plano</h2>
      <p>Tenha sempre em mãos seu plano personalizado com quantidades exatas</p>
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
  <title>Quiz Nutricional</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: Arial, sans-serif; background: #f6f7f9; margin: 0; padding: 0; color: #2c3e50; }
    .wrap { max-width: 800px; margin: 0 auto; padding: 32px 24px; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .card { background: #fff; border-radius: 24px; box-shadow: 0 20px 60px rgba(0,0,0,.08); padding: 40px; width: 100%; }
    .btn { background: linear-gradient(135deg, #ff8c00, #ffa500); border: none; color: #fff; padding: 16px 24px; border-radius: 12px; font-weight: 600; font-size: 16px; cursor: pointer; }
    .btn:hover { transform: translateY(-2px); }
    .hidden { display: none; }
    input, select { width: 100%; padding: 16px 20px; border-radius: 12px; border: 2px solid #e3e6ec; font-size: 16px; }
    h1 { text-align: center; font-size: 32px; margin-bottom: 32px; }
    .steps { display: flex; justify-content: center; gap: 12px; margin-bottom: 32px; }
    .dot { width: 12px; height: 12px; border-radius: 50%; background: #e3e6ec; }
    .dot.active { background: #ff8c00; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="steps">
      <div class="dot active" id="d1"></div>
      <div class="dot" id="d2"></div>
      <div class="dot" id="d3"></div>
    </div>
    <h1>Monte seu plano personalizado</h1>
    <div id="s1">
      <input id="nome" placeholder="Seu nome" style="margin-bottom:16px" />
      <input id="email" type="email" placeholder="Seu e-mail" style="margin-bottom:16px" />
      <input id="whatsapp" placeholder="WhatsApp" style="margin-bottom:16px" />
      <input id="idade" type="number" placeholder="Idade" style="margin-bottom:16px" />
      <input id="peso" type="number" step="0.1" placeholder="Peso (kg)" style="margin-bottom:16px" />
      <input id="altura" type="number" placeholder="Altura (cm)" style="margin-bottom:16px" />
      <select id="sexo" style="margin-bottom:16px">
        <option value="">Selecione o sexo</option>
        <option value="masculino">Masculino</option>
        <option value="feminino">Feminino</option>
      </select>
      <button class="btn" onclick="next(2)" style="width:100%">Continuar →</button>
    </div>

    <div id="s2" class="hidden">
      <h3>Qual é o seu objetivo?</h3>
      <select id="objetivo" style="margin-bottom:16px">
        <option value="">Selecione seu objetivo</option>
        <option value="emagrecer">Emagrecer</option>
        <option value="manter">Manter Peso</option>
        <option value="ganhar">Ganhar Massa</option>
      </select>
      <select id="atividade" style="margin-bottom:16px">
        <option value="">Nível de atividade</option>
        <option value="sedentario">Sedentário</option>
        <option value="iniciante">Iniciante</option>
        <option value="intermediario">Intermediário</option>
        <option value="avancado">Avançado</option>
      </select>
      <button class="btn" onclick="back(1)" style="width:48%;margin-right:4%">← Voltar</button>
      <button class="btn" onclick="next(3)" style="width:48%">Continuar →</button>
    </div>

    <div id="s3" class="hidden">
      <h3>Finalizando...</h3>
      <p>Processando seu plano personalizado com quantidades exatas!</p>
      <button class="btn" onclick="back(2)" style="width:48%;margin-right:4%">← Voltar</button>
      <button class="btn" onclick="finalizar()" style="width:48%">Ver Plano →</button>
    </div>
  </div>
</div>
<script>
let respostas = {};

function setStep(i) {
  for(let s=1; s<=3; s++) {
    document.getElementById('s'+s).classList.toggle('hidden', s !== i);
    document.getElementById('d'+s).classList.toggle('active', s <= i);
  }
}

function next(i) {
  if(i===2) {
    respostas.nome = document.getElementById('nome').value;
    respostas.email = document.getElementById('email').value;
    respostas.whatsapp = document.getElementById('whatsapp').value;
    respostas.idade = parseInt(document.getElementById('idade').value);
    respostas.peso = parseFloat(document.getElementById('peso').value);
    respostas.altura = parseInt(document.getElementById('altura').value);
    respostas.sexo = document.getElementById('sexo').value;
    
    if(!respostas.nome || !respostas.email || !respostas.sexo) {
      alert('Preencha todos os campos');
      return;
    }
  }
  
  if(i===3) {
    respostas.objetivo = document.getElementById('objetivo').value;
    respostas.atividade = document.getElementById('atividade').value;
    
    if(!respostas.objetivo || !respostas.atividade) {
      alert('Selecione objetivo e atividade');
      return;
    }
  }
  
  setStep(i);
}

function back(i) { setStep(i); }

async function finalizar() {
  try {
    const r = await fetch('/gerar-plano', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(respostas)
    });
    
    if (r.ok) {
      window.location = '/plano-completo';
    } else {
      alert('Erro ao processar plano');
    }
  } catch (error) {
    alert('Erro ao processar dados');
  }
}
</script>
</body>
</html>
"""

last_user_data = {}

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.get('/api/foods')
def api_foods():
    return jsonify(load_foods_data())

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
        # Simula alimentos selecionados para demonstração
        alimentos = {
            'cafe': ['Pão integral', 'Café preto sem açúcar'],
            'almoco': ['Arroz com feijão', 'Frango grelhado ou cozido'],
            'lanche': ['Fruta (banana, maçã, laranja)'],
            'jantar': ['Salada de verduras', 'Frango grelhado ou desfiado']
        }
        plano = montar_refeicoes(metas['alvo'], alimentos)
        peso_ideal = calcular_peso_ideal(last_user_data['altura'], last_user_data['sexo'])
        
        return render_template_string(FINAL_PLAN_HTML, 
            respostas=last_user_data, metas=metas, plano=plano, peso_ideal=peso_ideal
        )
    except Exception as e:
        return f"Erro ao gerar plano: {str(e)}", 500

@app.get('/gerar-pdf/<session_id>')
def gerar_pdf_route(session_id):
    global last_user_data
    if not last_user_data: return "Dados não encontrados.", 404
    
    try:
        metas = calcular_alvo_kcal(last_user_data)
        alimentos = {
            'cafe': ['Pão integral', 'Café preto sem açúcar'],
            'almoco': ['Arroz com feijão', 'Frango grelhado ou cozido'],
            'lanche': ['Fruta (banana, maçã, laranja)'],
            'jantar': ['Salada de verduras', 'Frango grelhado ou desfiado']
        }
        plano = montar_refeicoes(metas['alvo'], alimentos)
        pdf_bytes = gerar_pdf(plano, last_user_data, metas)
        return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name='plano_personalizado.pdf', mimetype='application/pdf')
    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)