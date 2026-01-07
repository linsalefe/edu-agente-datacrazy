from typing import List, Dict, Tuple, Optional, Any

from loguru import logger

from app.llm.openai_client import OpenAIClient
from app.llm.prompt_builder import PromptBuilder
from app.rag.query import RAGQuery


class ResponseGenerator:
    """Gera respostas da IA integrando RAG, prompts e OpenAI"""

    def __init__(self):
        self.openai_client = OpenAIClient()
        self.prompt_builder = PromptBuilder()
        self.rag_query = RAGQuery()

    def generate_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        stage: str = "",
        lead_data: Optional[Dict[str, Any]] = None,
        intent: Optional[str] = None,
        # Alias para compatibilidade com chamadas antigas (ex: history=...)
        history: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Tuple[Optional[str], bool]:
        """
        Gera resposta baseada na mensagem do usuário

        Args:
            user_message: Mensagem do usuário
            conversation_history: Histórico da conversa (últimas N mensagens)
            stage: Estágio atual da conversa
            lead_data: Dados do lead
            intent: Intenção detectada (opcional)
            history: Alias de conversation_history (compatibilidade)
            kwargs: Ignora args extras sem quebrar

        Returns:
            Tupla (resposta, precisa_handoff)
        """
        try:
            # Normaliza parâmetros
            if conversation_history is None:
                conversation_history = history or []
            stage = stage or ""

            # 1) Buscar contexto relevante no RAG
            preview = (user_message or "")[:80].replace("\n", " ")
            logger.info(f"🔍 Buscando contexto RAG para: {preview}...")
            context_rag = self.rag_query.build_context(user_message, top_k=3)

            # 2) Construir prompt do sistema
            system_prompt = self.prompt_builder.build_system_prompt(
                stage=stage,
                context_rag=context_rag,
                lead_data=lead_data,
                intent=intent
            )

            # 3) Montar mensagens para OpenAI
            messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

            # Adicionar histórico (últimas 6 mensagens = 3 trocas)
            # Aceita entradas com chaves role/content OU fallback para outras chaves comuns.
            safe_history = conversation_history[-6:] if conversation_history else []
            for msg in safe_history:
                role = msg.get("role") or msg.get("sender") or msg.get("type")
                content = msg.get("content") or msg.get("text") or msg.get("message")

                # Validação mínima
                if role not in ("system", "user", "assistant"):
                    # Se vier algo estranho (ex: "bot", "human"), tenta mapear
                    role = "assistant" if str(role).lower() in ("bot", "ai") else "user"

                if not content:
                    continue

                messages.append({"role": role, "content": str(content)})

            # Adicionar mensagem atual do usuário
            messages.append({"role": "user", "content": user_message})

            # 4) Gerar resposta
            logger.info("🤖 Gerando resposta com OpenAI...")
            response = self.openai_client.chat_completion(
                messages=messages,
                temperature=0.8,  # Mais criativo para vendas
                max_tokens=500
            )

            if not response:
                logger.error("❌ OpenAI retornou resposta vazia")
                return None, False

            # 5) Detectar se precisa handoff
            precisa_handoff = self._detect_handoff(response)
            if precisa_handoff:
                logger.warning("⚠️ Handoff detectado na resposta")

            logger.info(f"✅ Resposta gerada: {len(response)} caracteres")
            return response, precisa_handoff

        except Exception as e:
            logger.exception(f"❌ Erro ao gerar resposta: {e}")
            return None, False

    def _detect_handoff(self, response: str) -> bool:
        """
        Detecta se a IA está indicando necessidade de handoff.

        Keywords que indicam handoff:
        - Transferir, passar, conectar
        - Atendente, consultor, especialista
        - Não consigo, não posso
        """

        handoff_keywords = [
            "transferir",
            "passar para",
            "conectar com",
            "atendente",
            "consultor",
            "especialista",
            "equipe",
            "não consigo",
            "nao consigo",
            "não posso ajudar",
            "nao posso ajudar",
            "aguarde um momento",
            "alguém te retorna",
            "alguem te retorna",
        ]

        response_lower = (response or "").lower()

        for keyword in handoff_keywords:
            if keyword in response_lower:
                logger.info(f"🎯 Keyword de handoff detectada: {keyword}")
                return True

        return False
