"""
Processador de Mensagens
Orquestra todo o fluxo de processamento de mensagens
"""

import re
from datetime import datetime
from typing import Dict, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.channels.whatsapp.zapi import ZAPIClient
from app.config import settings
from app.core.scheduler import FollowupScheduler

from app.crm.sync_service import CRMSyncService
from app.llm.response_generator import ResponseGenerator
from app.models.conversation import Conversation, ConversationStage, ConversationStatus
from app.models.lead import Lead
from app.models.message import Message
from app.rag.query import RAGQuery
from app.services.handoff import HandoffService


class MessageProcessor:
    """Processa mensagens do WhatsApp e orquestra respostas da IA"""

    def __init__(self, db: Session):
        self.db = db
        self.zapi = ZAPIClient()
        self.crm = CRMSyncService(db)
        self.response_gen = ResponseGenerator()

    async def process_message(self, phone: str, text: str, name: str = None):
        """
        Processa uma mensagem recebida

        Args:
            phone: Telefone do cliente
            text: Texto da mensagem
            name: Nome do cliente (opcional)
        """
        logger.info(f"📱 Processando mensagem de {phone}")

        try:
            # 1. Get/Create Conversation
            conversation = self._get_or_create_conversation(phone, name)

            # 2. Verifica se está em handoff
            if conversation.status == ConversationStatus.handoff:
                logger.info(f"⚠️  Conversa {conversation.id} está em handoff - ignorando")
                return

            # 3. Verifica se IA está pausada (tag IA_PAUSADA)
            if self._is_ai_paused(conversation.lead):
                logger.info(f"⏸️  IA pausada para lead {conversation.lead_id} - ignorando mensagem")
                return

            # 4. Salva mensagem do usuário
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=text,
            )
            self.db.add(user_message)
            self.db.commit()

            # 5. Extrair e salvar informações do usuário (course/city/education/motivation/cpf/email/etc)
            self._extract_and_save_info(text, conversation.lead)

            # 6. Atualiza timestamp da conversa
            conversation.last_message_at = datetime.utcnow()
            self.db.commit()

            # 7. Busca contexto RAG
            rag_query = RAGQuery()
            context = rag_query.build_context(text, top_k=4)
            logger.info(f"📚 Contexto RAG obtido: {len(context)} caracteres")

            # 8. Busca histórico da conversa
            history = self._get_conversation_history(conversation.id, limit=10)

            # 9. Monta payload completo do lead para o LLM (inclui profile/qualification)
            llm_lead_data = self._build_llm_lead_data(conversation)

            # 10. Gera resposta da IA
            response, needs_handoff = self.response_gen.generate_response(
                user_message=text,
                history=history,
                stage=conversation.current_stage.value,
                lead_data=llm_lead_data,
                context=context,
            )

            logger.info(f"🤖 Resposta gerada: {response[:100]}...")
            logger.info(f"🤝 Necessita handoff: {needs_handoff}")

            # 11. Verifica se precisa de handoff
            if needs_handoff:
                HandoffService.request_handoff(
                    conversation_id=conversation.id,
                    reason="IA solicitou transferência para humano",
                    db=self.db,
                )
                return

            # 12. Salva resposta da IA
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response,
            )
            self.db.add(assistant_message)
            self.db.commit()

            # 13. Verificar se deve avançar stage (usando o mesmo payload que o LLM vê)
            new_stage = self._should_advance_stage(conversation, llm_lead_data)
            if new_stage:
                conversation.current_stage = ConversationStage[new_stage]
                self.db.commit()
                logger.info(f"📊 Stage avançado: {conversation.current_stage.value}")

            # 14. Envia resposta via WhatsApp
            self.zapi.send_text(phone, response)
            logger.info(f"✅ Resposta enviada para {phone}")

            # 15. Sincroniza com CRM (async best-effort)
            try:
                if conversation.lead:
                    self.crm.add_note_to_lead(
                        conversation.lead_id,
                        f"💬 CONVERSA\n\nCliente: {text}\n\nIA: {response}",
                    )
            except Exception as e:
                logger.warning(f"⚠️  Erro ao sincronizar com CRM: {e}")

            # 16. Agenda follow-ups (apenas para novas conversas)
            messages_count = (
                self.db.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .count()
            )

            if messages_count == 2:  # primeira interação (user + assistant)
                FollowupScheduler.schedule_followups(conversation.id, self.db)
                logger.info(f"📅 Follow-ups agendados para conversa {conversation.id}")

            logger.info("✅ Mensagem processada com sucesso")

        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            raise

    def _build_llm_lead_data(self, conversation: Conversation) -> Dict:
        """Monta payload de lead para o LLM, garantindo profile.qualification."""
        lead = conversation.lead
        if not lead:
            return {}

        payload: Dict = {
            "name": lead.name,
            "phone": lead.phone,
            "email": getattr(lead, "email", None),
        }

        profile = lead.profile or {}
        # Normaliza: tudo que estiver flat vai para qualification
        qual = {}
        if isinstance(profile, dict):
            if isinstance(profile.get("qualification"), dict):
                qual = profile.get("qualification") or {}
            else:
                qual = dict(profile)  # copia

        payload["profile"] = {"qualification": qual}
        return payload

    def _get_or_create_conversation(self, phone: str, name: str = None):
        """Busca ou cria uma conversa"""
        conversation = (
            self.db.query(Conversation)
            .filter(
                Conversation.phone == phone,
                Conversation.status == ConversationStatus.active,
            )
            .first()
        )

        if conversation:
            logger.info(f"📖 Conversa existente encontrada: {conversation.id}")
            return conversation

        logger.info(f"🆕 Criando nova conversa para {phone}")

        lead = self._get_or_create_lead(phone, name)

        conversation = Conversation(
            phone=phone,
            lead_id=lead.id,
            status=ConversationStatus.active,
            current_stage=ConversationStage.novo,
            last_message_at=datetime.utcnow(),
        )

        self.db.add(conversation)
        self.db.commit()

        logger.info(f"✅ Conversa criada: {conversation.id}")

        try:
            self.crm.sync_lead_create(lead.id)
        except Exception as e:
            logger.warning(f"⚠️  Erro ao sincronizar lead com CRM: {e}")

        return conversation

    def _get_or_create_lead(self, phone: str, name: str = None):
        """Busca ou cria um lead"""
        lead = self.db.query(Lead).filter(Lead.phone == phone).first()

        if lead:
            logger.info(f"📖 Lead existente: {lead.id}")
            return lead

        lead = Lead(
            phone=phone,
            name=name or "Cliente",
            origin="whatsapp",
        )

        self.db.add(lead)
        self.db.commit()

        logger.info(f"✅ Lead criado: {lead.id}")
        return lead

    def _get_conversation_history(self, conversation_id: int, limit: int = 10):
        """Busca histórico de mensagens"""
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )

        messages.reverse()

        history = []
        for msg in messages:
            history.append({"role": msg.role, "content": msg.content})

        return history

    def _extract_and_save_info(self, text: str, lead: Lead):
        """Extrai informações da mensagem do usuário e salva no perfil (em profile.qualification)."""
        text_lower = (text or "").lower().strip()
        text_original = (text or "").strip()

        profile = lead.profile or {}
        if not isinstance(profile, dict):
            profile = {}

        # Garante qualification (e migra flat -> qualification quando necessário)
        qual = profile.get("qualification")
        if not isinstance(qual, dict):
            qual = {}
            # migra campos flat antigos
            for k in ["course", "city", "education_level", "motivation", "full_name", "has_high_school", "cpf", "email", "birth_date", "cep"]:
                if k in profile and k != "qualification":
                    qual[k] = profile.get(k)
            profile["qualification"] = qual

        updated = False

        # ========== DETECTAR CPF ==========
        # Formatos: 123.456.789-00 ou 12345678900
        cpf_pattern = r'\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b'
        cpf_match = re.search(cpf_pattern, text_original)
        if cpf_match and not qual.get("cpf"):
            cpf_raw = cpf_match.group(1)
            # Remove pontuação para validar quantidade de dígitos
            cpf_digits = re.sub(r'\D', '', cpf_raw)
            if len(cpf_digits) == 11:
                qual["cpf"] = cpf_raw
                updated = True
                logger.info(f"🆔 CPF detectado: {cpf_raw}")

        # ========== DETECTAR E-MAIL ==========
        email_pattern = r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        email_match = re.search(email_pattern, text_original)
        if email_match and not qual.get("email"):
            email_found = email_match.group(1)
            qual["email"] = email_found
            # Também atualiza o campo email do lead
            if not lead.email:
                lead.email = email_found
            updated = True
            logger.info(f"📧 E-mail detectado: {email_found}")

        # ========== DETECTAR DATA DE NASCIMENTO ==========
        # Formatos: dd/mm/aaaa, dd-mm-aaaa, dd.mm.aaaa
        date_pattern = r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})\b'
        date_match = re.search(date_pattern, text_original)
        if date_match and not qual.get("birth_date"):
            date_raw = date_match.group(1)
            qual["birth_date"] = date_raw
            updated = True
            logger.info(f"🎂 Data de nascimento detectada: {date_raw}")

        # ========== DETECTAR CEP ==========
        # Formatos: 12345-678 ou 12345678
        cep_pattern = r'\b(\d{5}-?\d{3})\b'
        cep_match = re.search(cep_pattern, text_original)
        if cep_match and not qual.get("cep"):
            cep_raw = cep_match.group(1)
            qual["cep"] = cep_raw
            updated = True
            logger.info(f"📍 CEP detectado: {cep_raw}")

        # ========== DETECTAR CURSO ==========
        cursos = [
            "administração", "administracao", "pedagogia", "enfermagem",
            "engenharia", "direito", "psicologia", "ti", "tecnologia",
            "marketing", "gestão", "gestao", "rh", "recursos humanos",
            "adm", "contabilidade", "logistica", "logística"
        ]
        if not qual.get("course"):
            for curso in cursos:
                if curso in text_lower:
                    qual["course"] = curso.title()
                    updated = True
                    logger.info(f"📚 Curso detectado: {curso}")
                    break

        # ========== DETECTAR CIDADE ==========
        if not qual.get("city"):
            if "arcos" in text_lower:
                qual["city"] = "Arcos"
                updated = True
                logger.info("📍 Cidade detectada: Arcos")
            elif "lagoa" in text_lower or "prata" in text_lower:
                qual["city"] = "Lagoa da Prata"
                updated = True
                logger.info("📍 Cidade detectada: Lagoa da Prata")
            elif "formiga" in text_lower:
                qual["city"] = "Formiga"
                updated = True
                logger.info("📍 Cidade detectada: Formiga")

        # ========== DETECTAR ESCOLARIDADE ==========
        if not qual.get("education_level"):
            if text_lower in ["sim", "s", "já", "ja", "tenho", "concluí", "conclui", "terminei"]:
                qual["education_level"] = "Ensino Médio Completo"
                updated = True
                logger.info("✅ Escolaridade detectada: Ensino Médio Completo")
            elif any(palavra in text_lower for palavra in ["sim", "conclu", "tenho", "já fiz", "ja fiz", "terminei"]):
                if any(p in text_lower for p in ["superior", "graduação", "graduacao", "faculdade"]):
                    qual["education_level"] = "Ensino Superior Completo"
                    updated = True
                    logger.info("✅ Escolaridade detectada: Ensino Superior Completo")
                elif any(p in text_lower for p in ["médio", "medio", "ensino", "colegial"]):
                    qual["education_level"] = "Ensino Médio Completo"
                    updated = True
                    logger.info("✅ Escolaridade detectada: Ensino Médio Completo")

        # ========== DETECTAR MOTIVAÇÃO ==========
        if not qual.get("motivation"):
            if any(palavra in text_lower for palavra in ["empresa", "negócio", "negocio", "trabalho", "carreira", "dono", "empresário", "empresario"]):
                qual["motivation"] = text[:200]
                updated = True
                logger.info(f"💼 Motivação detectada: {text[:50]}...")

        # ========== DETECTAR NOME COMPLETO ==========
        if (not lead.name or lead.name == "Cliente") and len(text.split()) >= 2:
            words = text.split()
            if len(words[0]) > 2 and not any(palavra in text_lower for palavra in ["ola", "olá", "bom", "dia", "tenho", "quero", "sim", "não", "nao"]):
                possible_name = " ".join(words[:3]).strip()
                if possible_name and len(possible_name) > 3:
                    lead.name = possible_name.title()[:100]
                    updated = True
                    logger.info(f"👤 Nome detectado: {lead.name}")

        if updated:
            profile["qualification"] = qual
            lead.profile = profile
            flag_modified(lead, "profile")
            self.db.commit()
            logger.info(f"💾 Perfil atualizado (qualification): {qual}")

    def _should_advance_stage(self, conversation: Conversation, lead_data: dict) -> str:
        """
        Determina se deve avançar o stage baseado nas informações coletadas

        Returns:
            Novo stage ou None se não deve mudar
        """
        current_stage = conversation.current_stage.value

        # NORMALIZA profile -> qualification (novo formato)
        profile = lead_data.get("profile") or {}
        if isinstance(profile, dict) and isinstance(profile.get("qualification"), dict):
            qual = profile.get("qualification") or {}
        elif isinstance(profile, dict):
            qual = profile
        else:
            qual = {}

        has_name = bool(lead_data.get("name") and lead_data["name"] != "Cliente")

        city = qual.get("city")
        course = qual.get("course")
        education_level = qual.get("education_level")
        has_high_school = qual.get("has_high_school")
        motivation = qual.get("motivation")

        has_city = bool(city)
        has_course = bool(course)
        has_education = bool(education_level) or (has_high_school is True)
        has_motivation = bool(motivation)

        logger.info("🔍 Verificando avanço de stage:")
        logger.info(f"   Stage atual: {current_stage}")
        logger.info(f"   has_name: {has_name} ({lead_data.get('name')})")
        logger.info(f"   has_city: {has_city} ({city})")
        logger.info(f"   has_course: {has_course} ({course})")
        logger.info(f"   has_education: {has_education} ({education_level or has_high_school})")
        logger.info(f"   has_motivation: {has_motivation}")

        if current_stage == "novo":
            if has_course or has_city:
                logger.info("✅ Avançando de 'novo' para 'atendimento'")
                return "atendimento"

        elif current_stage == "atendimento":
            if has_course and has_city and has_education:
                logger.info("✅ Avançando de 'atendimento' para 'qualificacao'")
                return "qualificacao"

        elif current_stage == "qualificacao":
            if has_motivation and has_name and has_course and has_city:
                logger.info("✅ Avançando de 'qualificacao' para 'fechamento'")
                return "fechamento"

        logger.info(f"⏸️  Stage permanece: {current_stage}")
        return None

    def _is_ai_paused(self, lead: Lead) -> bool:
        """
        Verifica se a IA está pausada para este lead
        Checa se o lead tem a tag IA_PAUSADA no DataCrazy
        """
        if not lead.datacrazy_id:
            return False

        try:
            lead_data = self.crm.crm.get_lead(lead.datacrazy_id)
            logger.info(f"🔍 Lead data recebido: {lead_data.keys()}")

            tags = lead_data.get("tags", [])
            logger.info(f"🏷️  Tags encontradas: {tags}")

            if isinstance(tags, list):
                for tag in tags:
                    tag_name = (tag or {}).get("name", "")
                    logger.info(f"🏷️  Verificando tag: {tag_name}")
                    if tag_name == "IA_PAUSADA":
                        logger.info(f"🔴 Tag IA_PAUSADA encontrada para lead {lead.id}")
                        return True

            elif isinstance(tags, dict):
                tag_name = tags.get("name", "")
                logger.info(f"🏷️  Verificando tag: {tag_name}")
                if tag_name == "IA_PAUSADA":
                    logger.info(f"🔴 Tag IA_PAUSADA encontrada para lead {lead.id}")
                    return True

            logger.info(f"✅ Lead {lead.id} sem tag IA_PAUSADA - IA ativa")
            return False

        except Exception as e:
            logger.warning(f"⚠️  Erro ao verificar tags do lead {lead.id}: {e}")
            return False