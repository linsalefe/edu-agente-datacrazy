from sqlalchemy import Column, Integer, Float, Date, UniqueConstraint
from app.database import Base
from datetime import date


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    handoff_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    avg_response_time = Column(Float, default=0.0)  # em segundos

    __table_args__ = (
        UniqueConstraint('date', name='uq_metrics_date'),
    )

    @staticmethod
    def calculate_for_date(target_date: date):
        """
        Calcula métricas para uma data específica.
        Esta função será implementada depois com as queries necessárias.
        """
        pass