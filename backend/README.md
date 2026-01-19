# 🤖 WhatsApp AI Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61dafb.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Sistema profissional de assistente pessoal via WhatsApp com IA, gerenciamento financeiro, lembretes inteligentes e análise de reuniões.

## 🌟 Características

### ✅ Funcionalidades Principais

- **🗓️ Agenda & Lembretes Inteligentes**
  - Criação de lembretes por voz ou texto
  - Recorrência personalizável (diário, semanal, mensal)
  - Notificações automáticas no horário configurado
  - Suporte a diferentes timezones

- **💰 Controle Financeiro Completo**
  - Registro de receitas e despesas
  - Categorização automática
  - Relatórios mensais, semanais e anuais
  - Gráficos e visualizações interativas

- **📋 Análise de Reuniões**
  - Transcrição automática de áudios
  - Resumo executivo gerado por IA
  - Extração de tópicos principais
  - Identificação de action items
  - Lista de participantes e decisões

- **🧠 Memória Contextual**
  - Session ID único por usuário
  - Histórico completo de conversas
  - Personalização baseada em preferências
  - Aprendizado contínuo

### 🎨 Dashboard White Label

- Interface moderna e responsiva
- Gráficos interativos (Recharts)
- Visualização de finanças
- Calendário de lembretes
- Histórico de reuniões
- Exportação de relatórios

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        WhatsApp User                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Twilio    │
                    │  (WhatsApp   │
                    │   Business)  │
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   FastAPI Backend      │
              │  - Webhooks Handler    │
              │  - Background Tasks    │
              └────────┬───────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
    ┌─────────────┐         ┌──────────────┐
    │  LangGraph  │         │  PostgreSQL  │
    │  AI Agent   │◄────────┤   Database   │
    │  (Gemini)   │         │              │
    └─────────────┘         └──────────────┘
           │                       ▲
           ▼                       │
    ┌─────────────┐                │
    │   Agents:   │                │
    │  - Reminder │────────────────┘
    │  - Finance  │
    │  - Meeting  │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  Scheduler  │
    │   Worker    │
    └─────────────┘
```

---

## 🚀 Quick Start

### Pré-requisitos

```bash
# Verificar versões
python --version  # 3.11+
node --version    # 18+
docker --version  # 20+
```

### Instalação Rápida

```bash
# 1. Clonar repositório
git clone https://github.com/seu-usuario/whatsapp-ai-assistant.git
cd whatsapp-ai-assistant

# 2. Configurar variáveis de ambiente
cp backend/.env.example backend/.env
# Edite backend/.env com suas credenciais

# 3. Iniciar com Docker
docker-compose up -d

# 4. Verificar status
docker-compose ps

# 5. Acessar aplicação
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

---

## 📦 Stack Tecnológica

### Backend
- **Framework**: FastAPI 0.109
- **AI/ML**: LangGraph + Gemini 2.5 Flash
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **ORM**: SQLAlchemy 2.0
- **WhatsApp**: Twilio API
- **Scheduler**: APScheduler

### Frontend
- **Framework**: React 18 + TypeScript
- **Styling**: TailwindCSS 3
- **Charts**: Recharts
- **Icons**: Lucide React
- **Build**: Vite

### DevOps
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx
- **CI/CD**: GitHub Actions (configurar)

---

## 📁 Estrutura do Projeto

```
whatsapp-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── api/              # API endpoints
│   │   ├── services/         # Business logic
│   │   ├── ai/               # LangGraph agents
│   │   │   ├── graph.py      # Main AI graph
│   │   │   └── agents/       # Specialized agents
│   │   ├── workers/          # Background workers
│   │   │   └── scheduler.py  # Reminder scheduler
│   │   └── utils/            # Utilities
│   ├── alembic/              # Database migrations
│   ├── tests/                # Unit tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Page components
│   │   ├── services/         # API services
│   │   ├── hooks/            # Custom hooks
│   │   └── types/            # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
└── README.md
```

---

## 🔧 Configuração Detalhada

### 1. Twilio WhatsApp Setup

```bash
# 1. Criar conta: https://www.twilio.com/try-twilio
# 2. Obter credenciais no dashboard
# 3. Configurar número do WhatsApp
# 4. Configurar webhook
```

**Webhook URL (Produção):**
```
POST https://seu-dominio.com/webhook/whatsapp
```

**Webhook URL (Desenvolvimento com ngrok):**
```bash
ngrok http 8000
# Copiar URL gerada: https://abc123.ngrok.io
```

### 2. Google Gemini API

```bash
# 1. Acessar: https://makersuite.google.com/app/apikey
# 2. Criar API Key
# 3. Adicionar ao .env
GOOGLE_API_KEY=sua_chave_aqui
```

### 3. Variáveis de Ambiente

```env
# backend/.env
POSTGRES_SERVER=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua_senha_segura
POSTGRES_DB=whatsapp_ai

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=seu_token
TWILIO_WHATSAPP_NUMBER=+14155238886

GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash

SECRET_KEY=chave_super_secreta_mude_em_producao
```

---

## 💻 Desenvolvimento

### Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Criar banco de dados
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload

# Iniciar scheduler (em outro terminal)
python -m app.workers.scheduler

# Executar testes
pytest tests/ -v
```

### Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Iniciar servidor dev
npm run dev

# Build para produção
npm run build

# Executar testes
npm run test
```

---

## 🧪 Testes

```bash
# Backend
cd backend
pytest tests/ -v --cov=app

# Frontend
cd frontend
npm run test
npm run test:coverage
```

---

## 📊 API Documentation

Acesse a documentação interativa da API:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Principais Endpoints

```
GET  /api/v1/users/{user_id}
POST /webhook/whatsapp
POST /api/v1/reminders
GET  /api/v1/finances
POST /api/v1/meetings
```

---

## 🔐 Segurança

- ✅ Autenticação JWT
- ✅ HTTPS obrigatório em produção
- ✅ Rate limiting
- ✅ Validação de inputs
- ✅ SQL injection protection (SQLAlchemy)
- ✅ XSS protection
- ✅ CORS configurado

---

## 🚀 Deploy

### Opção 1: Railway

```bash
# 1. Instalar Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Deploy
railway up
```

### Opção 2: Docker VPS

```bash
# 1. Conectar ao servidor
ssh user@seu-servidor

# 2. Clonar repositório
git clone https://github.com/seu-usuario/whatsapp-ai-assistant.git

# 3. Configurar .env
cd whatsapp-ai-assistant
cp backend/.env.example backend/.env
# Editar com credenciais de produção

# 4. Iniciar
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📈 Roadmap

- [ ] **v1.0** - MVP funcional
  - [x] Lembretes básicos
  - [x] Controle financeiro
  - [x] Análise de reuniões
  - [ ] Dashboard básico

- [ ] **v1.5** - Melhorias
  - [ ] Autenticação multi-usuário
  - [ ] Exportação de relatórios (PDF)
  - [ ] Integração com calendário (Google/Outlook)
  - [ ] Notificações push no dashboard

- [ ] **v2.0** - Features Avançadas
  - [ ] Reconhecimento de voz nativo
  - [ ] Análise de sentimentos
  - [ ] Predição de gastos futuros
  - [ ] Recomendações personalizadas
  - [ ] Multi-idioma

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, siga os passos:

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto está sob a licença MIT. Veja [LICENSE](LICENSE) para mais informações.

---

## 👥 Autores

- **Seu Nome** - *Desenvolvimento Inicial* - [@seu-usuario](https://github.com/seu-usuario)

---

## 🙏 Agradecimentos

- FastAPI por um framework incrível
- Twilio pela API do WhatsApp
- Google pela Gemini AI
- Comunidade Open Source

---

## 📞 Suporte

- 📧 Email: suporte@seudominio.com
- 💬 Discord: [Link do servidor]
- 🐛 Issues: [GitHub Issues](https://github.com/seu-usuario/whatsapp-ai-assistant/issues)

---

**⭐ Se este projeto te ajudou, considere dar uma estrela!**

Made with ❤️ and ☕