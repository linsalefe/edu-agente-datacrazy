from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    profile = Column(JSON, default={})  # Dados adicionais flexíveis
    
    datacrazy_id = Column(String(50), nullable=True, unique=True)
    origin = Column(String(50), default="whatsapp")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_qualification_data(self):
        """Retorna dados de qualificação do lead"""
        return self.profile.get('qualification', {})

    def is_qualified(self):
        """Verifica se o lead está qualificado"""
        qual = self.get_qualification_data()
        return qual.get('score', 0) >= 70