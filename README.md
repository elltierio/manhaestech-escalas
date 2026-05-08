# ManhãesTech Escalas

Aplicativo profissional em Python (Flask) para gerenciamento de escalas 12x36 de portaria condominial, com dashboard em estilo “escalação de futebol”, calendário completo e exportação de PDF.

## Como executar (Windows)

```powershell
cd "c:\Users\elliterio\Documents\Aplicativo de Escalas de Plantão"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Acesse: http://127.0.0.1:5000

## Login inicial

- Usuário: `admin`
- Senha: `admin`

Para alterar, defina variáveis de ambiente antes do primeiro start:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

## Regra 12x36 (implementação atual)

- A aplicação cria automaticamente 1 escala **Diurna** e 1 escala **Noturna** por dia.
- A alternância é feita por ordem configurável:
  - Diurno: `Felipe Manhães | Thiago Nascimento`
  - Noturno: `Allan Garcia | Joabe Alves`
- A data-base é salva em `settings.schedule.base_date` no primeiro start.

## Fotos

- Upload individual por funcionário
- Corte quadrado automático e exibição circular no dashboard
- Armazenamento local em `instance/uploads`

## Estrutura

- `app/models.py`: modelos SQL (SQLite compatível com PostgreSQL futuramente)
- `app/routes/*`: rotas (auth, dashboard, funcionários, calendário, API)
- `app/services/*`: serviços (seed, escala, fotos, PDF, backup)
- `app/templates/*`: templates HTML (Bootstrap)
- `app/static/*`: CSS/JS do tema escuro moderno

