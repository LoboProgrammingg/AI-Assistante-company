# =============================================================================
# IRIS - WhatsApp AI Assistant
# Makefile com melhores práticas
# =============================================================================

.PHONY: help install dev test lint format clean docker-up docker-down docker-logs migrate db-reset

# Variáveis
PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker compose
APP_NAME := whatsapp_ai

# Cores para output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

# =============================================================================
# HELP
# =============================================================================

help: ## Mostra esta ajuda
	@echo "$(GREEN)IRIS - WhatsApp AI Assistant$(NC)"
	@echo ""
	@echo "Comandos disponíveis:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# INSTALAÇÃO E SETUP
# =============================================================================

install: ## Instala dependências do projeto
	@echo "$(GREEN)Instalando dependências...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install ## Instala dependências de desenvolvimento
	@echo "$(GREEN)Instalando dependências de dev...$(NC)"
	$(PIP) install pytest pytest-asyncio pytest-cov black isort flake8 mypy

setup: ## Configura ambiente inicial
	@echo "$(GREEN)Configurando ambiente...$(NC)"
	@cp -n .env.example .env 2>/dev/null || true
	@echo "Edite o arquivo .env com suas configurações"

# =============================================================================
# DESENVOLVIMENTO
# =============================================================================

dev: ## Inicia servidor de desenvolvimento
	@echo "$(GREEN)Iniciando servidor de desenvolvimento...$(NC)"
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8005

run: ## Inicia servidor de produção
	@echo "$(GREEN)Iniciando servidor...$(NC)"
	uvicorn app.main:app --host 0.0.0.0 --port 8005

shell: ## Abre shell Python com contexto da aplicação
	@echo "$(GREEN)Abrindo shell...$(NC)"
	$(PYTHON) -c "from app.database import SessionLocal; from app.models import *; db = SessionLocal(); print('Variáveis: db, User, Reminder, Finance, Meeting')"
	$(PYTHON) -i -c "from app.database import SessionLocal; from app.models import *; db = SessionLocal()"

# =============================================================================
# TESTES E QUALIDADE
# =============================================================================

test: ## Executa testes
	@echo "$(GREEN)Executando testes...$(NC)"
	pytest -v

test-cov: ## Executa testes com cobertura
	@echo "$(GREEN)Executando testes com cobertura...$(NC)"
	pytest --cov=app --cov-report=html --cov-report=term-missing

lint: ## Verifica código com linters
	@echo "$(GREEN)Verificando código...$(NC)"
	flake8 app --max-line-length=120 --ignore=E501,W503
	mypy app --ignore-missing-imports

format: ## Formata código
	@echo "$(GREEN)Formatando código...$(NC)"
	black app --line-length=120
	isort app --profile=black

check: lint test ## Executa lint e testes

# =============================================================================
# BANCO DE DADOS
# =============================================================================

migrate: ## Executa migrações do banco
	@echo "$(GREEN)Executando migrações...$(NC)"
	alembic upgrade head

migrate-create: ## Cria nova migração (uso: make migrate-create MSG="descricao")
	@echo "$(GREEN)Criando migração...$(NC)"
	alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Reverte última migração
	@echo "$(YELLOW)Revertendo migração...$(NC)"
	alembic downgrade -1

db-reset: ## Reseta banco de dados (CUIDADO!)
	@echo "$(RED)Resetando banco de dados...$(NC)"
	@read -p "Tem certeza? [y/N] " confirm && [ "$$confirm" = "y" ]
	alembic downgrade base
	alembic upgrade head

# =============================================================================
# DOCKER
# =============================================================================

docker-up: ## Sobe containers Docker
	@echo "$(GREEN)Subindo containers...$(NC)"
	$(DOCKER_COMPOSE) up -d

docker-up-build: ## Sobe containers com rebuild
	@echo "$(GREEN)Subindo containers com rebuild...$(NC)"
	$(DOCKER_COMPOSE) up -d --build

docker-down: ## Para containers Docker
	@echo "$(YELLOW)Parando containers...$(NC)"
	$(DOCKER_COMPOSE) down

docker-logs: ## Mostra logs dos containers
	$(DOCKER_COMPOSE) logs -f

docker-logs-backend: ## Mostra logs do backend
	docker logs -f $(APP_NAME)_backend

docker-shell: ## Abre shell no container backend
	docker exec -it $(APP_NAME)_backend /bin/bash

docker-clean: ## Remove containers e volumes
	@echo "$(RED)Removendo containers e volumes...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans

# =============================================================================
# PRODUÇÃO
# =============================================================================

build: ## Build para produção
	@echo "$(GREEN)Fazendo build...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache

deploy: ## Deploy (push para origin)
	@echo "$(GREEN)Fazendo deploy...$(NC)"
	git push origin main

health: ## Verifica saúde da aplicação
	@echo "$(GREEN)Verificando saúde...$(NC)"
	curl -s http://localhost:8005/health | python -m json.tool

health-detailed: ## Verifica saúde detalhada
	@echo "$(GREEN)Verificando saúde detalhada...$(NC)"
	curl -s http://localhost:8005/health/detailed | python -m json.tool

# =============================================================================
# LIMPEZA
# =============================================================================

clean: ## Limpa arquivos temporários
	@echo "$(YELLOW)Limpando arquivos temporários...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "htmlcov" -delete
	find . -type f -name ".coverage" -delete

clean-all: clean docker-clean ## Limpa tudo (incluindo Docker)

# =============================================================================
# UTILITÁRIOS
# =============================================================================

env-check: ## Verifica variáveis de ambiente
	@echo "$(GREEN)Variáveis de ambiente:$(NC)"
	@echo "DATABASE_URL: $${DATABASE_URL:-(não definido)}"
	@echo "REDIS_URL: $${REDIS_URL:-(não definido)}"
	@echo "GOOGLE_API_KEY: $${GOOGLE_API_KEY:+definido}"
	@echo "TWILIO_ACCOUNT_SID: $${TWILIO_ACCOUNT_SID:+definido}"

generate-secret: ## Gera SECRET_KEY aleatório
	@echo "$(GREEN)Gerando SECRET_KEY...$(NC)"
	@$(PYTHON) -c "import secrets; print(secrets.token_urlsafe(32))"

docs: ## Gera documentação
	@echo "$(GREEN)Abrindo documentação...$(NC)"
	@echo "Acesse: http://localhost:8005/docs"

# =============================================================================
# ATALHOS
# =============================================================================

up: docker-up ## Alias para docker-up
down: docker-down ## Alias para docker-down
logs: docker-logs ## Alias para docker-logs
restart: docker-down docker-up ## Reinicia containers
