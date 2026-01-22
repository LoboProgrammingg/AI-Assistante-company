# Auditoria de Segurança - Sistema IRIS

> **Data:** Janeiro 2026  
> **Auditor:** Cascade AI  
> **Status:** Análise completa com correções pendentes

---

## Resumo Executivo

| Categoria | Crítico | Alto | Médio | Baixo |
|-----------|---------|------|-------|-------|
| Autenticação | 2 | 1 | 1 | 0 |
| Autorização | 0 | 1 | 0 | 0 |
| Input Validation | 0 | 0 | 1 | 0 |
| Headers | 0 | 0 | 1 | 1 |
| API Exposure | 2 | 1 | 0 | 0 |
| **TOTAL** | **4** | **3** | **3** | **1** |

---

## 1. Problemas CRÍTICOS 🔴

### 1.1 Endpoint `/auth/bypass-verify` em Produção

**Arquivo:** `backend/app/api/auth.py:198-222`

**Problema:** Endpoint permite bypass de verificação de email sem autenticação.

```python
@router.post("/bypass-verify")
async def bypass_verify_email(request: Request, db: Session = Depends(get_db)):
    """Endpoint temporário para bypass de verificação (apenas para desenvolvimento)"""
    # Qualquer pessoa pode verificar qualquer conta!
```

**Risco:** Atacante pode verificar qualquer conta sem acesso ao email.

**Correção:** Remover ou proteger com flag DEBUG.

---

### 1.2 Endpoint `/auth/email-config` Expõe Configuração

**Arquivo:** `backend/app/api/auth.py:225-243`

**Problema:** Expõe configurações sensíveis do servidor SMTP.

```python
@router.get("/email-config")
async def check_email_config():
    return {
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        # ... configurações internas expostas
    }
```

**Risco:** Informação de infraestrutura exposta a atacantes.

**Correção:** Remover ou proteger com autenticação admin.

---

### 1.3 Endpoint `/auth/test-email` Sem Autenticação

**Arquivo:** `backend/app/api/auth.py:246-275`

**Problema:** Permite envio de emails sem autenticação.

**Risco:** Pode ser usado para spam ou phishing.

**Correção:** Remover ou proteger com autenticação admin.

---

### 1.4 CSP Permite `'unsafe-inline'`

**Arquivo:** `backend/app/core/security.py:57-64`

**Problema:**
```python
"Content-Security-Policy": (
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
)
```

**Risco:** Permite XSS inline scripts/styles.

**Correção:** Usar nonces ou hashes para scripts inline.

---

## 2. Problemas ALTOS 🟠

### 2.1 Token JWT Sem Tipo de Token

**Arquivo:** `backend/app/api/deps.py:27-51`

**Problema:** Token não inclui campo `type` para diferenciar access/refresh tokens.

```python
to_encode = {
    "sub": str(user_id),
    "exp": expire,
    "iat": datetime.now(timezone.utc),
    # Falta: "type": "access"
}
```

**Risco:** Refresh token pode ser usado como access token.

**Correção:** Adicionar campo `type` e validar no decode.

---

### 2.2 Falta Verificação `is_active` no Login

**Arquivo:** `backend/app/api/deps.py:95-100`

**Problema:** Não verifica se usuário está ativo após decode do token.

```python
user = db.query(User).filter(User.id == int(user_id)).first()
if not user:
    raise HTTPException(...)
# Falta: if not user.is_active: raise ...
return user
```

**Risco:** Usuários desativados continuam com acesso.

---

### 2.3 Falta Rate Limiting em Alguns Endpoints de Auth

**Arquivo:** `backend/app/api/auth.py`

**Problema:** `verify-email` e `resend-code` não têm rate limiting.

**Risco:** Brute force no código de verificação (6 dígitos = 1M combinações).

---

## 3. Problemas MÉDIOS 🟡

### 3.1 CORS Muito Permissivo

**Arquivo:** `backend/app/main.py:53-59`

```python
app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],  # Permite todos os métodos
    allow_headers=["*"],  # Permite todos os headers
)
```

**Recomendação:** Especificar métodos e headers permitidos.

---

### 3.2 Validação de Senha Pode Ser Mais Forte

**Arquivo:** `backend/app/core/security.py:37-42`

```python
REQUIRE_SPECIAL = False  # Não exige caractere especial
```

**Recomendação:** Ativar caractere especial obrigatório.

---

### 3.3 Input Sanitizer Não Aplicado Consistentemente

**Problema:** `InputSanitizer` existe mas não é usado em todos os endpoints.

**Recomendação:** Criar middleware de sanitização global.

---

## 4. Problemas BAIXOS 🟢

### 4.1 Logs Podem Expor Dados Sensíveis

**Vários arquivos**

**Problema:** Alguns logs incluem dados do usuário.

**Recomendação:** Usar `mask_sensitive_data()` consistentemente.

---

## 5. O Que Está BEM IMPLEMENTADO ✅

### 5.1 Autenticação
- ✅ Senhas hasheadas com bcrypt
- ✅ JWT com expiração
- ✅ Verificação de email obrigatória
- ✅ Reset de senha com código temporário

### 5.2 Rate Limiting
- ✅ Rate limiting por IP com Redis
- ✅ Limite por minuto e hora
- ✅ Bloqueio progressivo por violações
- ✅ Rate limiter específico para auth (5/min, 30/hora)

### 5.3 Headers de Segurança
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ X-XSS-Protection habilitado
- ✅ HSTS configurado
- ✅ Referrer-Policy

### 5.4 Input Validation
- ✅ InputSanitizer detecta padrões perigosos
- ✅ Proteção contra SQL injection patterns
- ✅ Proteção contra XSS patterns
- ✅ Limite de tamanho de mensagens

### 5.5 Proteção de Requisições
- ✅ RequestValidator bloqueia user-agents suspeitos
- ✅ Validação de IP real via X-Forwarded-For

### 5.6 Proteção contra Brute Force
- ✅ LoginAttemptTracker com lockout
- ✅ Máximo 5 tentativas, lockout 15 minutos
- ✅ Bloqueio progressivo

---

## 6. Correções a Implementar

### Prioridade 1 - CRÍTICO (Fazer AGORA)
1. [ ] Remover `/auth/bypass-verify` em produção
2. [ ] Proteger `/auth/email-config` com admin auth
3. [ ] Proteger `/auth/test-email` com admin auth
4. [ ] Remover `'unsafe-inline'` do CSP

### Prioridade 2 - ALTO (Fazer esta semana)
5. [ ] Adicionar campo `type` ao JWT
6. [ ] Verificar `is_active` no get_current_user
7. [ ] Adicionar rate limiting em verify-email
8. [ ] Adicionar rate limiting em resend-code

### Prioridade 3 - MÉDIO (Fazer este mês)
9. [ ] Especificar métodos CORS permitidos
10. [ ] Ativar REQUIRE_SPECIAL para senhas
11. [ ] Criar middleware de sanitização global

---

## 7. Checklist OWASP Top 10

| Vulnerabilidade | Status | Notas |
|-----------------|--------|-------|
| A01 - Broken Access Control | ⚠️ | Endpoints debug expostos |
| A02 - Cryptographic Failures | ✅ | bcrypt, JWT HS256 |
| A03 - Injection | ✅ | SQLAlchemy ORM, sanitizer |
| A04 - Insecure Design | ✅ | Arquitetura segura |
| A05 - Security Misconfiguration | ⚠️ | CSP unsafe-inline |
| A06 - Vulnerable Components | ✅ | Deps atualizadas |
| A07 - Auth Failures | ⚠️ | Falta type no JWT |
| A08 - Data Integrity Failures | ✅ | Validação Pydantic |
| A09 - Logging Failures | ✅ | Logging estruturado |
| A10 - SSRF | ✅ | Integrações validadas |

---

*Auditoria gerada automaticamente. Revisão manual recomendada.*
