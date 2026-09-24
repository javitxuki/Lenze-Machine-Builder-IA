# Lenze Machine Builder Web

Interfaz Streamlit para configurar máquinas Lenze y descargar un script ejecutable en PLC Designer 4.2.

## Local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Railway
Sube esta carpeta a GitHub y crea un servicio en Railway desde el repositorio. Railway detectará el Dockerfile.

## Importante
La web genera el script. PLC Designer y ScriptEngine se ejecutan en el PC Windows de ingeniería.
