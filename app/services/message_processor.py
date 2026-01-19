"""
Processador de Mensagens
Orquestra todo o fluxo de processamento de mensagens
"""

from datetime import datetime
from typing import Dict, Optional, Tuple, List

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified  # 🆕 IMPORTANTE!

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
            dados_extraidos = self._extract_and_save_info(text, conversation.lead)

            # 6. Atualiza timestamp da conversa
            conversation.last_message_at = datetime.utcnow()
            self.db.commit()

            # 7. Busca contexto RAG
            rag_query = RAGQuery()
            context = rag_query.build_context(text, top_k=4)
            logger.info(f"📚 Contexto RAG obtido: {len(context)} caracteres")

            # 8. Busca histórico da conversa
            history = self._get_conversation_history(conversation.id, limit=10)

            # 9. 🆕 Recarrega o lead do banco para garantir dados atualizados
            self.db.refresh(conversation.lead)
            
            # 10. Monta payload completo do lead para o LLM (inclui profile/qualification)
            llm_lead_data = self._build_llm_lead_data(conversation)

            # 11. Gera resposta da IA
            response, needs_handoff = self.response_gen.generate_response(
                user_message=text,
                history=history,
                stage=conversation.current_stage.value,
                lead_data=llm_lead_data,
                context=context,
            )

            logger.info(f"🤖 Resposta gerada: {response[:100]}...")
            logger.info(f"🤝 Necessita handoff: {needs_handoff}")

            # 12. Verifica se precisa de handoff
            if needs_handoff:
                HandoffService.request_handoff(
                    conversation_id=conversation.id,
                    reason="IA solicitou transferência para humano",
                    db=self.db,
                )
                return

            # 13. Salva resposta da IA
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response,
            )
            self.db.add(assistant_message)
            self.db.commit()

            # 14. Verificar se deve avançar stage (usando o mesmo payload que o LLM vê)
            old_stage = conversation.current_stage.value
            new_stage = self._should_advance_stage(conversation, llm_lead_data)
            
            if new_stage:
                conversation.current_stage = ConversationStage[new_stage]
                self.db.commit()
                logger.info(f"📊 Stage avançado: {old_stage} → {new_stage}")
                
                # 🆕 MOVER CARD NA PIPELINE DO DATACRAZY AUTOMATICAMENTE
                try:
                    self.crm.move_lead_in_pipeline(conversation.lead_id, new_stage)
                    logger.info(f"✅ Card movido na pipeline: {new_stage}")
                    
                    # 🆕 ADICIONAR NOTA DE MUDANÇA DE ESTÁGIO
                    self._add_stage_change_note(conversation.lead_id, old_stage, new_stage, llm_lead_data)
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao mover card na pipeline: {e}")

            # 15. Envia resposta via WhatsApp
            self.zapi.send_text(phone, response)
            logger.info(f"✅ Resposta enviada para {phone}")

            # 16. Sincroniza com CRM - Nota da conversa (simplificada)
            try:
                if conversation.lead and dados_extraidos:
                    # Se extraiu dados novos, adiciona nota resumida
                    self._add_data_collected_note(conversation.lead_id, dados_extraidos)
            except Exception as e:
                logger.warning(f"⚠️  Erro ao adicionar nota no CRM: {e}")

            # 17. Agenda follow-ups (apenas para novas conversas)
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

    # ==========================================
    # 🆕 NOTAS INTELIGENTES PARA TIME COMERCIAL
    # ==========================================

    def _add_stage_change_note(self, lead_id: int, old_stage: str, new_stage: str, lead_data: dict):
        """
        Adiciona nota quando o lead muda de estágio na pipeline.
        Resumo útil para o time comercial.
        """
        try:
            profile = lead_data.get("profile", {})
            qual = profile.get("qualification", {}) if isinstance(profile, dict) else {}
            
            # Monta resumo dos dados coletados
            dados = []
            if lead_data.get("name") and lead_data["name"] != "Cliente":
                dados.append(f"👤 Nome: {lead_data['name']}")
            if qual.get("course"):
                dados.append(f"📚 Curso: {qual['course']}")
            if qual.get("city"):
                dados.append(f"📍 Cidade: {qual['city']}")
            if qual.get("education_level"):
                dados.append(f"🎓 Escolaridade: {qual['education_level']}")
            if qual.get("motivation"):
                motiv = qual['motivation']
                if len(motiv) > 100:
                    motiv = motiv[:100] + "..."
                dados.append(f"💡 Motivação: {motiv}")
            if qual.get("cpf"):
                dados.append(f"📋 CPF: {qual['cpf']}")
            if qual.get("email"):
                dados.append(f"📧 E-mail: {qual['email']}")
            
            # Mapeia estágios para nomes amigáveis
            stage_names = {
                "novo": "Entrada do Lead",
                "atendimento": "Em Conversa",
                "qualificacao": "Lead Interessado",
                "fechamento": "Fechamento",
            }
            
            old_name = stage_names.get(old_stage, old_stage)
            new_name = stage_names.get(new_stage, new_stage)
            
            note = f"""📊 MUDANÇA DE ESTÁGIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{old_name} → {new_name}
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}

📝 DADOS COLETADOS:
{chr(10).join(dados) if dados else "Nenhum dado coletado ainda"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            self.crm.add_note_to_lead(lead_id, note)
            logger.info(f"📝 Nota de mudança de estágio adicionada ao lead {lead_id}")
            
        except Exception as e:
            logger.warning(f"⚠️  Erro ao adicionar nota de estágio: {e}")

    def _add_data_collected_note(self, lead_id: int, dados_extraidos: dict):
        """
        Adiciona nota quando dados importantes são coletados.
        Só adiciona se coletou algo relevante.
        """
        try:
            if not dados_extraidos:
                return
            
            items = []
            
            if dados_extraidos.get("course"):
                items.append(f"📚 Curso de interesse: {dados_extraidos['course']}")
            if dados_extraidos.get("city"):
                items.append(f"📍 Cidade/Polo: {dados_extraidos['city']}")
            if dados_extraidos.get("education_level"):
                items.append(f"🎓 Escolaridade: {dados_extraidos['education_level']}")
            if dados_extraidos.get("motivation"):
                motiv = dados_extraidos['motivation']
                if len(motiv) > 80:
                    motiv = motiv[:80] + "..."
                items.append(f"💡 Motivação: {motiv}")
            if dados_extraidos.get("cpf"):
                items.append(f"📋 CPF coletado")
            if dados_extraidos.get("email"):
                items.append(f"📧 E-mail: {dados_extraidos['email']}")
            if dados_extraidos.get("birth_date"):
                items.append(f"🎂 Data nascimento: {dados_extraidos['birth_date']}")
            if dados_extraidos.get("cep"):
                items.append(f"📮 CEP: {dados_extraidos['cep']}")
            if dados_extraidos.get("name"):
                items.append(f"👤 Nome: {dados_extraidos['name']}")
            
            if not items:
                return
            
            note = f"""✨ NOVOS DADOS COLETADOS
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(items)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            self.crm.add_note_to_lead(lead_id, note)
            logger.info(f"📝 Nota de dados coletados adicionada ao lead {lead_id}")
            
        except Exception as e:
            logger.warning(f"⚠️  Erro ao adicionar nota de dados: {e}")

    def _add_qualification_summary_note(self, lead_id: int, lead_data: dict):
        """
        Adiciona nota de resumo quando lead está qualificado.
        Chamada quando atinge estágio de fechamento.
        """
        try:
            profile = lead_data.get("profile", {})
            qual = profile.get("qualification", {}) if isinstance(profile, dict) else {}
            
            note = f"""🎯 LEAD QUALIFICADO - PRONTO PARA FECHAMENTO!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}

👤 DADOS DO LEAD:
• Nome: {lead_data.get('name', 'Não informado')}
• Telefone: {lead_data.get('phone', 'Não informado')}
• E-mail: {qual.get('email', 'Não informado')}

📚 INTERESSE:
• Curso: {qual.get('course', 'Não informado')}
• Cidade/Polo: {qual.get('city', 'Não informado')}

🎓 PERFIL:
• Escolaridade: {qual.get('education_level', 'Não informado')}
• Motivação: {qual.get('motivation', 'Não informado')[:150] if qual.get('motivation') else 'Não informado'}

📋 DADOS PARA MATRÍCULA:
• CPF: {qual.get('cpf', '❌ Não coletado')}
• Data Nasc.: {qual.get('birth_date', '❌ Não coletado')}
• CEP: {qual.get('cep', '❌ Não coletado')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Ação: Entrar em contato para finalizar matrícula!"""
            
            self.crm.add_note_to_lead(lead_id, note)
            logger.info(f"📝 Resumo de qualificação adicionado ao lead {lead_id}")
            
        except Exception as e:
            logger.warning(f"⚠️  Erro ao adicionar resumo de qualificação: {e}")

    # ==========================================
    # MÉTODOS AUXILIARES
    # ==========================================

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
                qual = dict(profile.get("qualification"))  # Copia para evitar mutação
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
            profile={"qualification": {}}  # 🆕 Inicializa profile corretamente
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

    def _extract_and_save_info(self, text: str, lead: Lead) -> dict:
        """
        Extrai informações da mensagem do usuário e salva no perfil.
        Retorna dict com os dados extraídos nesta mensagem.
        
        🆕 CORRIGIDO: Usa flag_modified para garantir persistência do JSON
        """
        import re
        
        text_lower = (text or "").lower().strip()
        dados_extraidos = {}

        # 🆕 Carrega profile existente ou cria novo
        profile = lead.profile if lead.profile else {}
        if not isinstance(profile, dict):
            profile = {}

        # 🆕 Garante que qualification existe e é um dict
        if "qualification" not in profile or not isinstance(profile.get("qualification"), dict):
            profile["qualification"] = {}
        
        qual = profile["qualification"]

        updated = False

        # Detectar curso
        cursos = [
            "administração", "administracao", "pedagogia", "enfermagem",
            "engenharia", "direito", "psicologia", "ti", "tecnologia",
            "marketing", "gestão", "gestao", "rh", "recursos humanos",
            "adm", "contabilidade", "logistica", "logística"
        ]
        for curso in cursos:
            if curso in text_lower and not qual.get("course"):
                qual["course"] = curso.title()
                dados_extraidos["course"] = curso.title()
                updated = True
                logger.info(f"📚 Curso detectado: {curso}")
                break

        # Detectar cidade
        if not qual.get("city"):
            if "arcos" in text_lower:
                qual["city"] = "Arcos"
                dados_extraidos["city"] = "Arcos"
                updated = True
                logger.info("📍 Cidade detectada: Arcos")
            elif "lagoa" in text_lower or "prata" in text_lower:
                qual["city"] = "Lagoa da Prata"
                dados_extraidos["city"] = "Lagoa da Prata"
                updated = True
                logger.info("📍 Cidade detectada: Lagoa da Prata")
            elif "formiga" in text_lower:
                qual["city"] = "Formiga"
                dados_extraidos["city"] = "Formiga"
                updated = True
                logger.info("📍 Cidade detectada: Formiga")

        # Detectar escolaridade
        if not qual.get("education_level"):
            if text_lower in ["sim", "s", "já", "ja", "tenho", "concluí", "conclui", "terminei"]:
                qual["education_level"] = "Ensino Médio Completo"
                dados_extraidos["education_level"] = "Ensino Médio Completo"
                updated = True
                logger.info("✅ Escolaridade detectada: Ensino Médio Completo")
            elif any(palavra in text_lower for palavra in ["sim", "conclu", "tenho", "já fiz", "ja fiz", "terminei"]):
                if any(p in text_lower for p in ["superior", "graduação", "graduacao", "faculdade"]):
                    qual["education_level"] = "Ensino Superior Completo"
                    dados_extraidos["education_level"] = "Ensino Superior Completo"
                    updated = True
                    logger.info("✅ Escolaridade detectada: Ensino Superior Completo")
                elif any(p in text_lower for p in ["médio", "medio", "ensino", "colegial"]):
                    qual["education_level"] = "Ensino Médio Completo"
                    dados_extraidos["education_level"] = "Ensino Médio Completo"
                    updated = True
                    logger.info("✅ Escolaridade detectada: Ensino Médio Completo")

        # Detectar motivação
        if not qual.get("motivation"):
            if any(palavra in text_lower for palavra in ["empresa", "negócio", "negocio", "trabalho", "carreira", "dono", "empresário", "empresario", "crescer", "promoção", "promocao"]):
                qual["motivation"] = text[:200]
                dados_extraidos["motivation"] = text[:200]
                updated = True
                logger.info(f"💼 Motivação detectada: {text[:50]}...")

        # Detectar CPF (formato: XXX.XXX.XXX-XX ou 11 dígitos)
        if not qual.get("cpf"):
            cpf_pattern = r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}'
            cpf_match = re.search(cpf_pattern, text)
            if cpf_match:
                cpf = cpf_match.group()
                qual["cpf"] = cpf
                dados_extraidos["cpf"] = cpf
                updated = True
                logger.info(f"📋 CPF detectado: {cpf}")

        # Detectar e-mail
        if not qual.get("email"):
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_match = re.search(email_pattern, text)
            if email_match:
                email = email_match.group()
                qual["email"] = email
                dados_extraidos["email"] = email
                updated = True
                logger.info(f"📧 E-mail detectado: {email}")

        # Detectar data de nascimento (formatos: DD/MM/AAAA, DD-MM-AAAA, DD.MM.AAAA)
        if not qual.get("birth_date"):
            date_pattern = r'\d{2}[/.-]\d{2}[/.-]\d{4}'
            date_match = re.search(date_pattern, text)
            if date_match:
                birth_date = date_match.group()
                qual["birth_date"] = birth_date
                dados_extraidos["birth_date"] = birth_date
                updated = True
                logger.info(f"🎂 Data de nascimento detectada: {birth_date}")

        # Detectar CEP (formato: XXXXX-XXX ou 8 dígitos)
        if not qual.get("cep"):
            cep_pattern = r'\d{5}-?\d{3}'
            cep_match = re.search(cep_pattern, text)
            if cep_match:
                cep = cep_match.group()
                qual["cep"] = cep
                dados_extraidos["cep"] = cep
                updated = True
                logger.info(f"📮 CEP detectado: {cep}")

        # Detectar nome completo (se o lead está como "Cliente")
        if (not lead.name or lead.name == "Cliente") and len(text.split()) >= 2:
            words = text.split()
            if len(words[0]) > 2 and not any(palavra in text_lower for palavra in ["ola", "olá", "bom", "dia", "tenho", "quero", "sim", "não", "nao"]):
                possible_name = " ".join(words[:3]).strip()
                if possible_name and len(possible_name) > 3:
                    lead.name = possible_name.title()[:100]
                    dados_extraidos["name"] = lead.name
                    updated = True
                    logger.info(f"👤 Nome detectado: {lead.name}")

        if updated:
            # 🆕 IMPORTANTE: Reatribui o profile inteiro e usa flag_modified
            profile["qualification"] = qual
            lead.profile = profile
            flag_modified(lead, "profile")  # 🆕 Força o SQLAlchemy a detectar a mudança
            self.db.commit()
            logger.info(f"💾 Perfil atualizado (qualification): {qual}")

        return dados_extraidos

    def _should_advance_stage(self, conversation: Conversation, lead_data: dict) -> Optional[str]:
        """Determina se deve avançar o stage baseado nas informações coletadas."""
        current_stage = conversation.current_stage.value

        # Normaliza profile -> qualification
        profile = lead_data.get("profile") or {}
        if isinstance(profile, dict) and isinstance(profile.get("qualification"), dict):
            qual = profile["qualification"]
        else:
            qual = {}

        has_name = bool(lead_data.get("name") and lead_data["name"] != "Cliente")
        has_city = bool(qual.get("city"))
        has_course = bool(qual.get("course"))
        has_education = bool(qual.get("education_level"))
        has_motivation = bool(qual.get("motivation"))
        has_cpf = bool(qual.get("cpf"))
        has_email = bool(qual.get("email"))
        has_birth_date = bool(qual.get("birth_date"))
        has_cep = bool(qual.get("cep"))

        logger.info("🔍 Verificando avanço de stage:")
        logger.info(f"   Stage atual: {current_stage}")
        logger.info(f"   has_name: {has_name} ({lead_data.get('name')})")
        logger.info(f"   has_city: {has_city} ({qual.get('city')})")
        logger.info(f"   has_course: {has_course} ({qual.get('course')})")
        logger.info(f"   has_education: {has_education} ({qual.get('education_level')})")
        logger.info(f"   has_motivation: {has_motivation}")
        logger.info(f"   has_cpf: {has_cpf}")
        logger.info(f"   has_email: {has_email}")

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
                # Adiciona resumo de qualificação
                try:
                    self._add_qualification_summary_note(conversation.lead_id, lead_data)
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao adicionar resumo: {e}")
                return "fechamento"

        logger.info(f"⏸️  Stage permanece: {current_stage}")
        return None

    def _is_ai_paused(self, lead: Lead) -> bool:
        """
        Verifica se a IA está pausada para este lead
        Checa se o lead tem a tag IA_PAUSADA no DataCrazy
        """
        if not lead or not lead.datacrazy_id:
            return False

        try:
            lead_data = self.crm.crm.get_lead(lead.datacrazy_id)
            logger.info(f"🔍 Lead data recebido: {lead_data.keys()}")

            tags = lead_data.get("tags", [])
            logger.info(f"🏷️  Tags encontradas: {tags}")

            if isinstance(tags, list):
                for tag in tags:
                    tag_name = (tag or {}).get("name", "")
                    if tag_name == "IA_PAUSADA":
                        logger.info(f"🔴 Tag IA_PAUSADA encontrada para lead {lead.id}")
                        return True

            elif isinstance(tags, dict):
                tag_name = tags.get("name", "")
                if tag_name == "IA_PAUSADA":
                    logger.info(f"🔴 Tag IA_PAUSADA encontrada para lead {lead.id}")
                    return True

            logger.info(f"✅ Lead {lead.id} sem tag IA_PAUSADA - IA ativa")
            return False

        except Exception as e:
            logger.warning(f"⚠️  Erro ao verificar tags do lead {lead.id}: {e}")
            return False