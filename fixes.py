# Correções principais para os problemas críticos

import os
import re

def sanitize_filename(filename):
    """Remove caracteres perigosos do nome do arquivo"""
    return re.sub(r'[^a-zA-Z0-9_-]', '', filename)

def safe_int_conversion(value, default=990):
    """Conversão segura para int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Exemplo de uso nas rotas:
@app.get('/download/<pdf_id>')
def download(pdf_id):
    # Sanitizar o pdf_id
    safe_pdf_id = sanitize_filename(pdf_id)
    if not safe_pdf_id or safe_pdf_id != pdf_id:
        return "ID inválido", 400
    
    path = f"/tmp/{safe_pdf_id}.pdf"
    if not os.path.exists(path):
        return "Arquivo expirado.", 404
    return send_file(path, as_attachment=True, download_name='plano_personalizado.pdf')

# Para requests com timeout e error handling:
def safe_request_get(url, headers, timeout=10):
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return None

# Para configuração segura:
app.config['PRICE_CENTS'] = safe_int_conversion(os.environ.get('PRICE_CENTS', '990'))

# Para produção:
if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)