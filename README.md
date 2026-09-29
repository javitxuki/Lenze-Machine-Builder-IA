# Lenze Machine Builder Web

Interfaz Streamlit para configurar máquinas Lenze y descargar un script que crea el
proyecto en PLC Designer 4.2.

La web **genera** el script; PLC Designer y su ScriptEngine se ejecutan en el PC Windows
de ingeniería (`Tools > Scripting > Execute Script File`).

## Qué crea el script

- El proyecto (`.project`) en la ruta indicada. Si ya existe, se para sin tocarlo.
- La CPU (c430 / c520 / c550), la `Application`, un `PLC_PRG` vacío y la `MainTask` cíclica de 10 ms.
- El EtherCAT Master y el Controller Sync Device.
- Por cada eje activo:
  - el drive EtherCAT, llamado `Drv_<eje>`;
  - el objeto de eje de motion (eje universal L_MC1P) bajo `Device > Functions`, con el nombre del eje;
  - los **datos de máquina escritos como parámetros del eje en el proyecto**, sin ningún bloque de función en el controlador.

  | Dato | Parámetro del eje | Valor |
  |---|---|---|
  | Tipo de movimiento | `:020` | 2 rotación (ROTARY), 1 traslación (resto) |
  | Rango de desplazamiento | `:030` | 0 MODULO, 1 LIMITED |
  | Cycle Length | `:031` | solo en MODULO |
  | Feed Constant | `:032` | |
  | Reductora | `:033` / `:034` | numerador Z2 / denominador Z1 |
  | Reductora adicional | `:025` / `:026` | numerador Z4 / denominador Z3 |

  Cada parámetro se busca por su Id (`0x10000000 + subíndice`), que no depende del eje, y
  se **relee** después de escribirlo.

Al acabar, el script imprime un resumen: `RESULT: OK` o la lista de avisos. Todavía **no**
escribe en el proyecto el Station Alias ni el Second Alias de los drives, ni crea los
Robot Groups: los valida y los lista en los avisos para configurarlos a mano. Si
PLC Designer no deja enlazar por script el eje con su drive, también lo avisa.

## Local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Usuarios

No hay usuarios en el código. Se definen en la variable de entorno `MB_USERS_JSON`:

```json
{"persona@empresa.com": {"password": "pbkdf2_sha256$...", "role": "admin", "name": "Nombre"}}
```

La contraseña va con hash. Para generarlo: `python auth.py hash`. Una contraseña en claro
todavía se acepta, pero la aplicación avisa al administrador. Tras cinco intentos
fallidos, el acceso se bloquea un minuto.

## Asistente IA

| Variable | Uso |
|---|---|
| `OPENAI_API_KEY` | Activa OpenAI. Sin ella se usa el intérprete local. |
| `OPENAI_MODEL` | Modelo que interpreta las órdenes (por defecto `gpt-5.6-luna`). |
| `OPENAI_TRANSCRIPTION_MODEL` | Transcripción por OpenAI (por defecto `gpt-4o-mini-transcribe`). |
| `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_LANGUAGE` | Transcripción local con Faster-Whisper. |

Si OpenAI falla, la aplicación lo dice y usa el intérprete local.

## Catálogo de dispositivos

`device_repository.json` sale de `Export_DeviceRepository.py`, que se ejecuta **dentro
de PLC Designer** y exporta las CPU, el EtherCAT Master, el Sync Device, los drives y los
objetos de eje instalados.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas de la interfaz (`tests/test_app.py`) solo se ejecutan si Streamlit está
instalado. El `Jenkinsfile` las lanza en cada build.

## Railway

Railway detecta el `Dockerfile`. Configura `MB_USERS_JSON` y, si quieres la IA de OpenAI,
`OPENAI_API_KEY`.
