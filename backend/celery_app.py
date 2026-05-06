from celery import Celery

# Conexión al servidor Redis que actuará como "Sala de Espera"
celery_app = Celery(
    "documusic_factory",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=['tasks']
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # ¡ESTA ES LA LÍNEA MÁS IMPORTANTE DEL PROYECTO!
    # Obliga a Celery a procesar solo 1 canción a la vez. 
    # Así enviemos 100, la GPU de 16GB nunca colapsará.
    worker_concurrency=1, 
    worker_prefetch_multiplier=1
)
