import pytest
import json
from quiz_→_pagamento_→_pdf_flask_mvp import app, mifflin_st_jeor, calcular_alvo_kcal, montar_refeicoes

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_mifflin_st_jeor():
    # Teste masculino
    bmr = mifflin_st_jeor('masculino', 80, 180, 25)
    assert bmr == 1805
    
    # Teste feminino
    bmr = mifflin_st_jeor('feminino', 60, 165, 30)
    assert bmr == 1372

def test_calcular_alvo_kcal():
    respostas = {
        'sexo': 'masculino',
        'peso': 80,
        'altura': 180,
        'idade': 25,
        'atividade': 'intermediario',
        'objetivo': 'manter'
    }
    resultado = calcular_alvo_kcal(respostas)
    assert 'bmr' in resultado
    assert 'tdee' in resultado
    assert 'alvo' in resultado
    assert resultado['alvo'] > 0

def test_montar_refeicoes():
    plano = montar_refeicoes(2000)
    assert 'cafe' in plano
    assert 'almoco' in plano
    assert 'lanche' in plano
    assert 'jantar' in plano
    assert plano['cafe']['meta_kcal'] == 500

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Quiz' in response.data

def test_api_plan(client):
    data = {
        'sexo': 'masculino',
        'peso': 80,
        'altura': 180,
        'idade': 25,
        'atividade': 'intermediario',
        'objetivo': 'manter'
    }
    response = client.post('/api/plan', 
                          data=json.dumps(data),
                          content_type='application/json')
    assert response.status_code == 200
    result = json.loads(response.data)
    assert 'metas' in result
    assert 'plano' in result

if __name__ == '__main__':
    pytest.main([__file__])