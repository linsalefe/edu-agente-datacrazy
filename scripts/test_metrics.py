from app.workers.metrics_worker import calculate_daily_metrics
from datetime import date, timedelta

print("🧪 Testando cálculo de métricas...")

yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"📅 Data alvo: {yesterday}")

result = calculate_daily_metrics(yesterday)
print("\n✅ RESULTADO:")
print(result)