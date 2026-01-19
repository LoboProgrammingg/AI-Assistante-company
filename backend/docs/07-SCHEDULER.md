# ⏰ Sistema de Scheduler

## Visão Geral

O Scheduler é responsável por:
1. Verificar lembretes pendentes
2. Enviar notificações no horário correto
3. Gerenciar recorrências
4. Tratar falhas de envio

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                      SCHEDULER WORKER                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐                                        │
│  │   Main Loop     │ ◄─── Executa a cada 30 segundos        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ Query Pending   │ ◄─── Busca lembretes pendentes         │
│  │   Reminders     │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ For Each        │                                        │
│  │ Reminder:       │                                        │
│  │                 │                                        │
│  │  ┌───────────┐  │                                        │
│  │  │Format Msg │  │                                        │
│  │  └─────┬─────┘  │                                        │
│  │        ▼        │                                        │
│  │  ┌───────────┐  │                                        │
│  │  │Send WA Msg│  │ ──▶ WhatsApp Service                   │
│  │  └─────┬─────┘  │                                        │
│  │        ▼        │                                        │
│  │  ┌───────────┐  │                                        │
│  │  │Mark Done  │  │                                        │
│  │  └─────┬─────┘  │                                        │
│  │        ▼        │                                        │
│  │  ┌───────────┐  │                                        │
│  │  │ Recurrence│  │ ──▶ Cria próxima ocorrência            │
│  │  └───────────┘  │                                        │
│  └─────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementação Atual

```python
# app/workers/scheduler.py

class ReminderScheduler:
    def __init__(self):
        self.whatsapp_service = WhatsAppService(...)
        self.running = False
    
    def get_pending_reminders(self, db: Session) -> List[Reminder]:
        """Busca lembretes que devem ser notificados."""
        now = datetime.utcnow()
        
        return db.query(Reminder).filter(
            and_(
                Reminder.is_active == True,
                Reminder.notified == False,
                Reminder.actual_reminder_time <= now
            )
        ).all()
    
    async def run(self):
        """Loop principal."""
        self.running = True
        
        while self.running:
            await self.process_reminders()
            await asyncio.sleep(SCHEDULER_CHECK_INTERVAL)
```

---

## Lógica de Recorrência

### Tipos Suportados

| Tipo | Descrição | Cálculo Próxima Data |
|------|-----------|---------------------|
| `once` | Único | Não cria próxima |
| `daily` | Diário | +1 dia |
| `weekdays` | Seg-Sex | Pula fim de semana |
| `weekends` | Sáb-Dom | Pula dias úteis |
| `weekly` | Semanal | +7 dias |
| `monthly` | Mensal | Mesmo dia do mês |
| `yearly` | Anual | +1 ano |

### Implementação

```python
def create_next_occurrence(self, reminder: Reminder, db: Session):
    """Cria próxima ocorrência de lembrete recorrente."""
    
    next_time = None
    
    if reminder.recurrence_type == RecurrenceType.DAILY:
        next_time = reminder.scheduled_time + timedelta(days=1)
    
    elif reminder.recurrence_type == RecurrenceType.WEEKDAYS:
        next_time = reminder.scheduled_time + timedelta(days=1)
        while next_time.weekday() >= 5:  # Sáb=5, Dom=6
            next_time += timedelta(days=1)
    
    elif reminder.recurrence_type == RecurrenceType.WEEKENDS:
        next_time = reminder.scheduled_time + timedelta(days=1)
        while next_time.weekday() < 5:
            next_time += timedelta(days=1)
    
    elif reminder.recurrence_type == RecurrenceType.WEEKLY:
        next_time = reminder.scheduled_time + timedelta(weeks=1)
    
    elif reminder.recurrence_type == RecurrenceType.MONTHLY:
        # Mesmo dia do próximo mês
        current = reminder.scheduled_time
        if current.month == 12:
            next_time = current.replace(year=current.year + 1, month=1)
        else:
            next_time = current.replace(month=current.month + 1)
    
    if next_time:
        new_reminder = Reminder(
            user_id=reminder.user_id,
            title=reminder.title,
            description=reminder.description,
            scheduled_time=next_time,
            remind_before_minutes=reminder.remind_before_minutes,
            actual_reminder_time=next_time - timedelta(
                minutes=reminder.remind_before_minutes
            ),
            recurrence_type=reminder.recurrence_type,
            is_active=True
        )
        db.add(new_reminder)
        db.commit()
```

---

## Formato de Mensagem

```python
def format_reminder_message(self, reminder: Reminder, user: User) -> str:
    """Formata mensagem do lembrete."""
    
    # Converter para timezone do usuário
    user_tz = pytz.timezone(user.timezone)
    scheduled = reminder.scheduled_time.replace(
        tzinfo=pytz.utc
    ).astimezone(user_tz)
    
    time_str = scheduled.strftime("%H:%M")
    date_str = scheduled.strftime("%d/%m/%Y")
    
    message = f"🔔 *Lembrete*\n\n"
    message += f"📌 {reminder.title}\n"
    
    if reminder.description:
        message += f"\n{reminder.description}\n"
    
    message += f"\n⏰ Horário: {time_str}"
    
    # Se não for hoje, mostrar data
    today = datetime.now(user_tz).date()
    if scheduled.date() != today:
        message += f" - {date_str}"
    
    return message
```

**Exemplo de Output:**
```
🔔 *Lembrete*

📌 Reunião com cliente

Discutir proposta comercial

⏰ Horário: 19:00
```

---

## Tratamento de Erros

```python
async def send_reminder(self, reminder: Reminder, user: User, db: Session):
    """Envia lembrete com tratamento de erros."""
    
    try:
        message = self.format_reminder_message(reminder, user)
        
        result = self.whatsapp_service.send_message(
            to_number=user.phone_number,
            message=message
        )
        
        if result["success"]:
            reminder.notified = True
            reminder.notified_at = datetime.utcnow()
            
            # Criar próxima ocorrência se recorrente
            if reminder.recurrence_type != RecurrenceType.ONCE:
                self.create_next_occurrence(reminder, db)
            else:
                reminder.is_completed = True
            
            db.commit()
            logger.info(f"Lembrete {reminder.id} enviado")
        else:
            # Falha no envio
            logger.error(f"Falha ao enviar: {result.get('error')}")
            self._handle_send_failure(reminder, db)
    
    except Exception as e:
        logger.error(f"Erro: {e}")
        self._handle_send_failure(reminder, db)

def _handle_send_failure(self, reminder: Reminder, db: Session):
    """Trata falha de envio."""
    reminder.retry_count = (reminder.retry_count or 0) + 1
    
    if reminder.retry_count >= 3:
        # Máximo de tentativas
        reminder.is_active = False
        logger.warning(f"Lembrete {reminder.id} desativado após 3 falhas")
    else:
        # Tentar novamente em 5 minutos
        reminder.actual_reminder_time = datetime.utcnow() + timedelta(minutes=5)
    
    db.commit()
```

---

## Executar como Worker Separado

### Docker Compose

```yaml
scheduler:
  build:
    context: ./backend
  command: python -m app.workers.scheduler
  depends_on:
    - postgres
    - redis
    - backend
  environment:
    - POSTGRES_SERVER=postgres
    - REDIS_HOST=redis
```

### Linha de Comando

```bash
# Ativar virtualenv
source venv/bin/activate

# Executar scheduler
python -m app.workers.scheduler
```

---

## Monitoramento

### Logs Importantes

```python
logger.info(f"Scheduler iniciado")
logger.info(f"Encontrados {len(reminders)} lembretes pendentes")
logger.info(f"Lembrete {id} enviado para usuário {user_id}")
logger.error(f"Erro ao enviar lembrete {id}: {error}")
logger.warning(f"Lembrete {id} desativado após falhas")
```

### Métricas Sugeridas

- Lembretes processados/minuto
- Taxa de sucesso de envio
- Tempo médio de processamento
- Lembretes pendentes na fila
