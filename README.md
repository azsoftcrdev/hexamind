

# 🤖 Robot Server

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Servidor en **FastAPI** para controlar y monitorear un robot hexápodo (**HexaMind**).
Optimizado para ejecutarse tanto en **PCs de desarrollo** como en **Jetson Nano** (edge computing).

Incluye:

* Control de movimiento del robot.
* Streaming de cámara en tiempo real (MJPEG).
* Detección de colores en HSV.
* Reconocimiento facial.
* Sistema de eventos/alertas mediante bus interno.

---

## 📑 Índice

1. [Arquitectura](#arquitectura)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Uso](#uso)
5. [Configuración](#configuración)
6. [Estructura del Proyecto](#estructura-del-proyecto)
7. [Endpoints](#endpoints)

   * [7.1. Básicos](#71-básicos)
   * [7.2. Movimiento](#72-movimiento)
   * [7.3. Endpoint `/move`](#73-endpoint-move)
8.  [WebSocket API](#websocket-api)
9.  [Testing](#testing)
10. [Contribución](#contribución)
11. [Roadmap](#roadmap)
12. [Licencia](#licencia)

---

## 🏗️ Arquitectura

* **Lenguaje:** Python 3.11+
* **Framework:** FastAPI (ASGI, alto rendimiento)
* **IA:** OpenCV + Mediapipe (detección de colores y rostros)
* **Streaming:** MJPEG
* **Dispositivos target:**

  * Jetson Nano (edge)
  * Windows/Linux dev machines
* **Patrón:** Modular (IA, sensores, movimiento, core)

---

## 📋 Requisitos

* Python **3.9+**
* `pip` actualizado
* Cámara compatible con OpenCV
* Jetson Nano (opcional, para despliegue embebido)

---

## ⚙️ Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/usuario/robot-server.git
cd robot-server
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Instalar dependencias

Dependencias base:

```bash
pip install -r requirements.base.txt
```

Si usas **Jetson Nano**:

```bash
pip install -r requirements.jetson.txt
```

En **Windows**:

```bash
pip install -r requirements.win.txt
```

---

## ▶️ Uso

### Linux / Mac

```bash
./run.sh
```

### Windows

```powershell
./run_dev.ps1
```

Servidor disponible en:
👉 `http://localhost:8000`

Swagger UI (documentación automática):
👉 `http://localhost:8000/docs`

---

## 🔧 Configuración

Variables de entorno (`.env`):

| Variable         | Descripción                  | Default   |
| ---------------- | ---------------------------- | --------- |
| `HOST`           | Dirección de escucha         | `0.0.0.0` |
| `PORT`           | Puerto del servidor          | `8000`    |
| `CAMERA_INDEX`   | Índice de cámara para OpenCV | `0`       |
| `STREAM_QUALITY` | Calidad MJPEG (1-100)        | `80`      |

---

## 📂 Estructura del Proyecto

```bash
robot-server/
├── app/
│   ├── main.py               # Punto de entrada FastAPI
│   ├── schemas.py            # Modelos de datos (Pydantic)
│   ├── streaming.py          # Generador de stream MJPEG
│   ├── core/                 # Configuración y bus de eventos
│   │   ├── alerts.py
│   │   ├── bus.py
│   │   └── settings.py
│   ├── IA/                   # Módulos de Inteligencia Artificial
│   │   ├── color_recognition.py
│   │   ├── face_recognition.py
│   ├── motion/               # Control de movimiento del robot
│   │   └── controller_vel.py
│   └── sensors/              # Módulos de sensores
│       └── camera.py
├── requirements.base.txt
├── requirements.jetson.txt
├── requirements.win.txt
├── run.sh
└── run_dev.ps1
```

---

## 🔌 Endpoints

### 7.1. Básicos

| Método | Endpoint        | Descripción                 |
| ------ | --------------- | --------------------------- |
| GET    | `/health`       | Estado del servidor         |
| GET    | `/stream.mjpg`  | Streaming de cámara MJPEG   |
| GET    | `/snapshot.jpg` | Captura de imagen actual    |
| POST   | `/move`         | Comandos de movimiento JSON |

---

### 7.2. Movimiento

| Método | Ruta         | Descripción                           |
| ------ | ------------ | ------------------------------------- |
| POST   | `/vel`       | Control de velocidad (lineal/angular) |
| POST   | `/stop`      | Detener movimiento                    |
| GET    | `/status`    | Estado actual del movimiento          |
| POST   | `/forward`   | Mover hacia adelante                  |
| POST   | `/back`      | Mover hacia atrás                     |
| POST   | `/left`      | Girar/mover a la izquierda            |
| POST   | `/right`     | Girar/mover a la derecha              |
| POST   | `/turnleft`  | Rotar hacia la izquierda              |
| POST   | `/turnright` | Rotar hacia la derecha                |

---

### 7.3. Endpoint `/move`

**Payload esperado:**

```json
{
  "linear": 0.3,
  "angular": 0.2,
  "duration_ms": 800
}
```

**Ejemplo `curl`:**

```bash
curl -X POST http://localhost:8000/move \
  -H "Content-Type: application/json" \
  -d '{"linear": 0.3, "angular": 0.2, "duration_ms": 800}'
```

---

## 🌐 WebSocket API

### Endpoint

```
ws://<host>:<port>/
```

Ejemplo local: `ws://localhost:8000/`

#### Suscripciones automáticas (servidor → cliente)

* `telemetry` → telemetría del robot
* `alert` → alertas críticas
* `mode` → cambios de modo
* `ui_event` → eventos de interfaz

Formato:

```json
{
  "topic": "telemetry",
  "data": { "battery": 92, "temp": 41.2 }
}
```

#### Comandos del cliente

1. **Movimiento (`motion_setpoint`)**

```json
{
  "type": "motion_setpoint",
  "x": 0, "y": 1, "z": 0, "speed": 40
}
```

2. **Publicar en bus**

```json
{
  "topic": "ui_event",
  "data": { "button": "start", "pressed": true }
}
```

Ejemplos listos en **JavaScript** y **Python** ya incluidos en el repo.

---

## 🧪 Testing

Ejecutar pruebas unitarias:

```bash
pip install pytest
pytest
```

---

## 🤝 Contribución

1. Haz un fork.
2. Crea una rama: `git checkout -b feature/nueva-funcion`
3. Commit: `git commit -m 'Agrega nueva función'`
4. Push: `git push origin feature/nueva-funcion`
5. Pull Request.

Estilo de código:

* Sigue [PEP8](https://peps.python.org/pep-0008/)
* Usa type hints
* Ejecuta `black` y `flake8` antes de commit

---

## 🛣️ Roadmap

* [ ] Mejorar performance en Jetson Nano
* [ ] Soporte para múltiples cámaras
* [ ] Detección de objetos (YOLOv8)
* [ ] Autonomía básica con LiDAR

---

## 📜 Licencia

License © 2025 - HexaMind UH