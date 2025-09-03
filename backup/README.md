# App Dieta - Quiz Personalizado

## Descrição
Aplicação Flask que gera planos de dieta personalizados através de um quiz multi-etapas com integração ao Mercado Pago.

## Funcionalidades
- Quiz interativo com 5 etapas
- Cálculo de BMR usando fórmula Mifflin-St Jeor
- Geração de plano alimentar personalizado
- Integração com Mercado Pago para pagamentos
- Geração de PDF com o plano completo
- Interface moderna e responsiva

## Como executar

### 1. Configurar ambiente
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente
Crie um arquivo `.env` na raiz:
```
MERCADO_PAGO_ACCESS_TOKEN=SEU_TOKEN_AQUI
PAYMENT_PROVIDER=mercadopago
PRICE_CENTS=990
APP_BASE_URL=http://localhost:5000
SECRET_KEY=sua_chave_secreta
```

### 3. Executar aplicação
```bash
python quiz.py
```

Acesse: http://localhost:5000

## Estrutura do Projeto
- `quiz.py` - Aplicação principal Flask
- `test_app.py` - Testes unitários
- `fixes.py` - Correções de segurança
- `requirements.txt` - Dependências Python
- `requirements-test.txt` - Dependências para testes

## Tecnologias
- Flask (backend)
- ReportLab (geração PDF)
- HTML/CSS/JavaScript (frontend)
- Mercado Pago API (pagamentos)

## Melhorias Implementadas
- Interface moderna com animações
- Validação de campos
- Design responsivo
- Ícones e emojis
- Gradientes e sombras
- Transições suaves

## Backup - Data: 2024
Este backup contém:
- quiz_backup.py - Aplicação principal
- requirements.txt - Dependências
- .env - Configurações
- data/foods.json - Base de dados dos alimentos
- README.md - Documentação

## Status do Projeto
✅ Aplicação funcional e otimizada
✅ Sistema de recomendações inteligentes
✅ Cálculos nutricionais precisos
✅ Interface moderna e responsiva
✅ Geração de PDF personalizado
✅ Sistema de leads em CSV
✅ Aplicação gratuita (sem pagamentos)