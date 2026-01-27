"""
Prompts para transcrição e sumarização de reuniões.
"""

TRANSCRIPTION_PROMPT = """Transcreva o áudio a seguir em {language}.

Regras:
- Transcreva exatamente o que foi dito
- Identifique diferentes falantes quando possível (Falante 1, Falante 2, etc.)
- Mantenha pontuação apropriada
- Preserve nomes próprios e termos técnicos
- Se houver partes inaudíveis, marque como [inaudível]

Retorne APENAS a transcrição, sem comentários adicionais."""


SUMMARIZATION_PROMPT = """Analise a transcrição de reunião abaixo e extraia informações estruturadas.

TRANSCRIÇÃO:
{transcript}

---

Retorne um JSON válido com a seguinte estrutura EXATA:
{{
    "executive_summary": "Resumo executivo da reunião em 2-3 parágrafos",
    "short_summary": "Resumo curto em até 100 caracteres para preview",
    "topics": [
        {{"topic": "Nome do tópico", "summary": "Breve descrição do que foi discutido"}}
    ],
    "action_items": [
        {{"task": "Descrição da tarefa", "owner": "Responsável ou null", "due_date": "Data limite ou null", "confidence": 0.9}}
    ],
    "decisions": [
        {{"decision": "Descrição da decisão", "context": "Contexto ou null", "made_by": "Quem decidiu ou null"}}
    ],
    "risks_blockers": ["Lista de riscos ou bloqueadores mencionados"],
    "participants_detected": ["Lista de participantes identificados"]
}}

REGRAS IMPORTANTES:
1. Use APENAS informações presentes na transcrição
2. NÃO invente fatos ou detalhes
3. Se algo não estiver claro, omita ou marque confidence baixo
4. Retorne APENAS o JSON, sem markdown ou texto adicional"""
