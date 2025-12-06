from app.config import settings

print("Verificando variáveis Z-API:")
print(f"ZAPI_TOKEN: {settings.ZAPI_TOKEN[:10]}... (primeiros 10 chars)")
print(f"ZAPI_INSTANCE: {settings.ZAPI_INSTANCE[:10]}... (primeiros 10 chars)")
print(f"\nURL completa: https://api.z-api.io/instances/{settings.ZAPI_INSTANCE}/token/{settings.ZAPI_TOKEN}/status")