# IntelliNews AI Service

AI microservice for IntelliNews providing Text-to-Speech (TTS), News Recommendation, and Text Summarization capabilities.

## 🎯 Features

### ✅ Text-to-Speech (TTS)
- **Model**: VieNeu-TTS-0.3B-q8-gguf (Vietnamese TTS)
- **Capabilities**: 
  - High-quality Vietnamese speech synthesis
  - Voice cloning support
  - CPU-optimized for fast inference
- **Status**: Fully implemented ✅

### 🔄 News Recommendation
- **Status**: Placeholder implementation 🚧
- **Planned**: Personalized news recommendations based on user preferences

### 📝 Text Summarization
- **Status**: Placeholder implementation 🚧
- **Planned**: Automatic summarization of news articles

---

## 📋 Prerequisites

### System Dependencies

**espeak-ng** is required for TTS phonemization:

```bash
# Ubuntu/Debian
sudo apt install espeak-ng

# Amazon Linux/Fedora
sudo dnf install espeak

# Verify installation
espeak-ng --version
```

### Python Requirements
- Python 3.10 or higher
- Poetry (for dependency management)

---

## 🚀 Quick Start

### 1. Install Poetry

```bash
# Linux/macOS
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

### 2. Install Dependencies

```bash
cd /home/luukien/Downloads/PycharmProjects/IntelliNews-AI
poetry install
```

### 3. Configure Environment

Edit `.env` file if needed (default values are already set):

```env
TTS_MODEL_REPO=pnnbao-ump/VieNeu-TTS-0.3B-q8-gguf
TTS_OUTPUT_DIR=outputs/tts
SERVER_PORT=8000
```

### 4. Start the Server

```bash
# Using Poetry
poetry run python main.py

# Or using uvicorn directly
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`

### 5. Access API Documentation

Open your browser and navigate to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📖 API Endpoints

### Root & Health

#### `GET /`
Service information and available features

#### `GET /health`
Health check endpoint

---

### 🎤 TTS Endpoints

#### `POST /api/tts/generate`
Generate speech from text

**Request Body:**
```json
{
  "text": "Xin chào, tôi là trợ lý AI của IntelliNews.",
  "ref_audio": null,
  "ref_text": null
}
```

**Response:**
```json
{
  "success": true,
  "filename": "tts_20260207_224000_abc123.wav",
  "file_path": "outputs/tts/tts_20260207_224000_abc123.wav",
  "download_url": "/api/tts/audio/tts_20260207_224000_abc123.wav",
  "message": "Audio generated successfully"
}
```

#### `GET /api/tts/audio/{filename}`
Download generated audio file

**Example:**
```bash
curl -O http://localhost:8000/api/tts/audio/tts_20260207_224000_abc123.wav
```

#### `GET /api/tts/health`
TTS service health check

---

### 📊 Recommendation Endpoints (Placeholder)

#### `POST /api/recommendation/`
Get personalized news recommendations

**Request Body:**
```json
{
  "user_id": "user123",
  "limit": 10
}
```

**Response:**
```json
{
  "success": true,
  "recommendations": [
    {
      "id": "news1",
      "title": "Sample News Article 1",
      "score": 0.9
    }
  ],
  "message": "Recommendations generated successfully (placeholder)"
}
```

#### `GET /api/recommendation/health`
Recommendation service health check

---

### 📝 Summarization Endpoints (Placeholder)

#### `POST /api/summarization/`
Generate text summary

**Request Body:**
```json
{
  "text": "Long news article content...",
  "max_length": 150
}
```

**Response:**
```json
{
  "success": true,
  "summary": "Generated summary...",
  "original_length": 1000,
  "summary_length": 150,
  "message": "Summary generated successfully (placeholder)"
}
```

#### `GET /api/summarization/health`
Summarization service health check

---

## 💻 Usage Examples

### Python Example

```python
import requests

# TTS Generation
response = requests.post(
    "http://localhost:8000/api/tts/generate",
    json={
        "text": "Chào mừng bạn đến với IntelliNews. Đây là tin tức hôm nay."
    }
)

result = response.json()
print(f"Audio file: {result['download_url']}")

# Download audio file
audio_url = f"http://localhost:8000{result['download_url']}"
audio_response = requests.get(audio_url)
with open("output.wav", "wb") as f:
    f.write(audio_response.content)
print("Audio saved to output.wav")
```

### cURL Examples

```bash
# Generate TTS
curl -X POST "http://localhost:8000/api/tts/generate" \
  -H "Content-Type: application/json" \
  -d '{"text": "Xin chào từ IntelliNews AI Service"}'

# Download audio
curl -O http://localhost:8000/api/tts/audio/FILENAME.wav

# Get recommendations (placeholder)
curl -X POST "http://localhost:8000/api/recommendation/" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "limit": 5}'

# Summarize text (placeholder)
curl -X POST "http://localhost:8000/api/summarization/" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your long article text here...", "max_length": 150}'
```

---

## 🏗️ Project Structure

```
IntelliNews-AI/
├── main.py                      # FastAPI application entry point
├── pyproject.toml               # Poetry configuration
├── .env                         # Environment variables
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuration management
│
├── services/
│   ├── __init__.py
│   ├── tts/                     # TTS service
│   │   ├── __init__.py
│   │   ├── service.py           # TTS implementation
│   │   └── models.py            # Request/response models
│   ├── recommendation/          # Recommendation service (placeholder)
│   │   ├── __init__.py
│   │   ├── service.py
│   │   └── models.py
│   └── summarization/           # Summarization service (placeholder)
│       ├── __init__.py
│       ├── service.py
│       └── models.py
│
├── api/
│   ├── __init__.py
│   ├── routes.py                # Main router
│   └── endpoints/
│       ├── __init__.py
│       ├── tts.py               # TTS endpoints
│       ├── recommendation.py    # Recommendation endpoints
│       └── summarization.py     # Summarization endpoints
│
└── outputs/
    └── tts/                     # Generated audio files
```

---

## 🔧 Development

### Install Development Dependencies

```bash
poetry install --with dev
```

### Run Tests

```bash
poetry run pytest
```

### Format Code

```bash
poetry run black .
poetry run isort .
```

---

## 🐳 Docker Deployment (Coming Soon)

Docker support will be added in future versions for easy deployment.

---

## 📝 License

### TTS Model License
- **VieNeu-TTS-0.3B**: CC BY-NC 4.0 (Non-commercial use)
- For commercial use, contact the model author or use the 0.5B variant (Apache 2.0)

### Service Code
- Apache 2.0 License

---

## 🤝 Contributing

This service is part of the IntelliNews ecosystem. For contribution guidelines, please refer to the main IntelliNews repository.

---

## 📚 References

- **VieNeu-TTS**: https://huggingface.co/pnnbao-ump/VieNeu-TTS-0.3B-q8-gguf
- **FastAPI**: https://fastapi.tiangolo.com/
- **Poetry**: https://python-poetry.org/

---

## 🔮 Roadmap

- [x] TTS service with VieNeu model
- [x] FastAPI server setup
- [x] Poetry dependency management
- [ ] Implement recommendation service
- [ ] Implement summarization service
- [ ] Add Docker support
- [ ] Add authentication
- [ ] Add rate limiting
- [ ] Add caching layer
- [ ] Performance optimization
- [ ] Monitoring and logging

---

**Made with ❤️ for IntelliNews**


[![Awesome](https://img.shields.io/badge/Awesome-NLP-green?logo=github)](https://github.com/keon/awesome-nlp)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-5865F2?logo=discord&logoColor=white)](https://discord.gg/yJt8kzjzWZ)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1V1DjG-KdmurCAhvXrxxTLsa9tteDxSVO?usp=sharing)
[![Hugging Face 0.5B](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-0.5B-yellow)](https://huggingface.co/pnnbao-ump/VieNeu-TTS)
[![Hugging Face 0.3B](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-0.3B-orange)](https://huggingface.co/pnnbao-ump/VieNeu-TTS-0.3B)

<img width="899" height="615" alt="VieNeu-TTS UI" src="https://github.com/user-attachments/assets/7eb9b816-6ab7-4049-866f-f85e36cb9c6f" />

**VieNeu-TTS** is an advanced on-device Vietnamese Text-to-Speech (TTS) model with **instant voice cloning**.

> [!TIP]
> **Voice Cloning:** All model variants (including GGUF) support instant voice cloning with just **3-5 seconds** of reference audio.

This project features two core architectures trained on the [VieNeu-TTS-1000h](https://huggingface.co/datasets/pnnbao-ump/VieNeu-TTS-1000h) dataset:
- **VieNeu-TTS (0.5B):** An enhanced model fine-tuned from the NeuTTS Air architecture for maximum stability.
- **VieNeu-TTS-0.3B:** A specialized model **trained from scratch** using the VieNeu-TTS-1000h dataset, delivering 2x faster inference and ultra-low latency.

These represent a significant upgrade from the previous VieNeu-TTS-140h with the following improvements:
- **Enhanced pronunciation**: More accurate and stable Vietnamese pronunciation
- **Code-switching support**: Seamless transitions between Vietnamese and English
- **Better voice cloning**: Higher fidelity and speaker consistency
- **Real-time synthesis**: 24 kHz waveform generation on CPU or GPU
- **Multiple model formats**: Support for PyTorch, GGUF Q4/Q8 (CPU optimized), and ONNX codec

VieNeu-TTS delivers production-ready speech synthesis fully offline.  

**Author:** Phạm Nguyễn Ngọc Bảo

---

[<img width="600" height="595" alt="VieNeu-TTS Demo" src="https://github.com/user-attachments/assets/021f6671-2d7f-4635-91fb-88b2ab0ddbcd" />](https://github.com/user-attachments/assets/021f6671-2d7f-4635-91fb-88b2ab0ddbcd)

---

## 📌 Table of Contents

1. [🦜 Installation & Web UI](#installation)
2. [📦 Using the Python SDK](#sdk)
3. [🐳 Docker & Remote Server](#docker-remote)
4. [🎯 Custom Models](#custom-models)
5. [🛠️ Fine-tuning Guide](#finetuning)
6. [🔬 Model Overview](#backbones)
7. [🐋 Deployment with Docker (Compose)](#docker)
8. [🤝 Support & Contact](#support)

---

## 🦜 1. Installation & Web UI <a name="installation"></a>

> ⚡ **Quick Start**  
> ℹ️ This is the fastest way to get started.  
> For **streaming inference, SDK integration, Docker deployment, and advanced setups**, see the sections below.
> ```bash
> git clone https://github.com/pnnbao97/VieNeu-TTS.git
> cd VieNeu-TTS
> uv sync
> uv run gradio_app.py
> ```
> Open `http://127.0.0.1:7860` and start generating speech.


### System Requirements
- **eSpeak NG:** Required for phonemization.
  - **Windows:** Download the `.msi` from [eSpeak NG Releases](https://github.com/espeak-ng/espeak-ng/releases).
  - **macOS:** `brew install espeak`
  - **Ubuntu/Debian:** `sudo apt install espeak-ng`
  - **Amazon Linux: Fedora**: `sudo dnf install espeak`
- **NVIDIA GPU (Optional):** For maximum speed via LMDeploy or GGUF GPU acceleration.
  - Requires **NVIDIA Driver >= 570.65** (CUDA 12.8+) or higher.
  - For **LMDeploy**, it is recommended to have the [NVIDIA GPU Computing Toolkit](https://developer.nvidia.com/cuda-downloads) installed.

### Installation Steps
1. **Clone the Repo:**
   ```bash
   git clone https://github.com/pnnbao97/VieNeu-TTS.git
   cd VieNeu-TTS
   ```

2. **Environment Setup with `uv` (Recommended):**
  - **Step A: Install uv (if you haven't)**
    ```bash
    # Windows:
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    # Linux/macOS:
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

  - **Step B: Install dependencies**

    **Option 1: GPU Support (Default)**
    ```bash
    uv sync
    ```
    *(Optional: See [GGUF GPU Acceleration](#gguf-gpu) if you want to use GGUF models on GPU)*

    **Option 2: CPU-ONLY (Lightweight, no CUDA)**
    ```bash
    # Linux/macOS:
    cp pyproject.toml pyproject.toml.gpu
    cp pyproject.toml.cpu pyproject.toml
    uv sync

    # Windows (PowerShell/CMD):
    copy pyproject.toml pyproject.toml.gpu
    copy pyproject.toml.cpu pyproject.toml
    uv sync
    ```

3. **Start the Web UI:**
   ```bash
   uv run gradio_app.py
   ```
   Access the UI at `http://127.0.0.1:7860`.

### ⚡ Real-time Streaming (CPU Optimized)
VieNeu-TTS supports **ultra-low latency streaming**, allowing audio playback to start before the entire sentence is finished. This is specifically optimized for **CPU-only** devices using the GGUF backend.

*   **Latency:** <300ms for the first chunk on modern i3/i5 CPUs.
*   **Efficiency:** Uses Q4/Q8 quantization and ONNX-based lightweight codecs.
*   **Usage:** Perfect for real-time interactive AI assistants.

**Start the dedicated CPU streaming demo:**
```bash
uv run web_stream_gguf.py
```
Then open `http://localhost:8001` in your browser.

### 🚀 GGUF GPU Acceleration (Optional) <a name="gguf-gpu"></a>
If you want to use GGUF models with GPU acceleration (llama-cpp-python), follow these steps:

#### **Windows Users**
Run the following command after `uv sync`:
```bash
uv pip install "https://github.com/pnnbao97/VieNeu-TTS/releases/download/llama-cpp-python-cu124/llama_cpp_python-0.3.16-cp312-cp312-win_amd64.whl"
```
*Note: Requires NVIDIA Driver version **551.61** (CUDA 12.4) or newer.*

#### **Linux / macOS Users**
Please refer to the official [llama-cpp-python documentation](https://llama-cpp-python.readthedocs.io/en/latest/) for installation instructions specific to your hardware (CUDA, Metal, ROCm).

---

## 📦 2. Using the Python SDK (vieneu) <a name="sdk"></a>

Integrate VieNeu-TTS into your own software projects.

### Quick Install
```bash
# Windows (Avoid llama-cpp build errors)
pip install vieneu --extra-index-url https://pnnbao97.github.io/llama-cpp-python-v0.3.16/cpu/

# Linux / MacOS
pip install vieneu
```

### Quick Start (main.py)
```python
from vieneu import Vieneu
import os

# Initialization
tts = Vieneu()

# Standard synthesis (uses default voice)
text = "Xin chào, tôi là VieNeu. Tôi có thể giúp bạn đọc sách, làm chatbot thời gian thực, hoặc thậm chí clone giọng nói của bạn."
audio = tts.infer(text=text)
tts.save(audio, "standard_output.wav")
print("💾 Saved synthesis to: standard_output.wav")
```

*For full implementation details, see [main.py](main.py).*

---

## 🐳 3. Docker & Remote Server <a name="docker-remote"></a>

Deploy VieNeu-TTS as a high-performance API Server (powered by LMDeploy) with a single command.

### 1. Run with Docker (Recommended)

**Requirement**: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) is required for GPU support.

**Start the Server with a Public Tunnel (No port forwarding needed):**
```bash
docker run --gpus all -p 23333:23333 pnnbao/vieneu-tts:serve --tunnel
```

*   **Default**: The server loads the `VieNeu-TTS` model for maximum quality.
*   **Tunneling**: The Docker image includes a built-in `bore` tunnel. Check the container logs to find your public address (e.g., `bore.pub:31631`).

### 2. Using the SDK (Remote Mode)

Once the server is running, you can connect from anywhere (Colab, Web Apps, etc.) without loading heavy models locally:

```python
from vieneu import Vieneu
import os

# Configuration
REMOTE_API_BASE = 'http://your-server-ip:23333/v1'  # Or bore tunnel URL
REMOTE_MODEL_ID = "pnnbao-ump/VieNeu-TTS"

# Initialization (LIGHTWEIGHT - only loads small codec locally)
tts = Vieneu(mode='remote', api_base=REMOTE_API_BASE, model_name=REMOTE_MODEL_ID)
os.makedirs("outputs", exist_ok=True)

# List remote voices
available_voices = tts.list_preset_voices()
for desc, name in available_voices:
    print(f"   - {desc} (ID: {name})")

# Use specific voice (dynamically select second voice)
if available_voices:
    _, my_voice_id = available_voices[1]
    voice_data = tts.get_preset_voice(my_voice_id)
    audio_spec = tts.infer(text="Chào bạn, tôi đang nói bằng giọng của bác sĩ Tuyên.", voice=voice_data)
    tts.save(audio_spec, f"outputs/remote_{my_voice_id}.wav")
    print(f"💾 Saved synthesis to: outputs/remote_{my_voice_id}.wav")

# Standard synthesis (uses default voice)
text_input = "Chế độ remote giúp tích hợp VieNeu vào ứng dụng Web hoặc App cực nhanh mà không cần GPU tại máy khách."
audio = tts.infer(text=text_input)
tts.save(audio, "outputs/remote_output.wav")
print("💾 Saved remote synthesis to: outputs/remote_output.wav")

# Zero-shot voice cloning (encodes audio locally, sends codes to server)
if os.path.exists("examples/audio_ref/example_ngoc_huyen.wav"):
    cloned_audio = tts.infer(
        text="Đây là giọng nói được clone và xử lý thông qua VieNeu Server.",
        ref_audio="examples/audio_ref/example_ngoc_huyen.wav",
        ref_text="Tác phẩm dự thi bảo đảm tính khoa học, tính đảng, tính chiến đấu, tính định hướng."
    )
    tts.save(cloned_audio, "outputs/remote_cloned_output.wav")
    print("💾 Saved remote cloned voice to: outputs/remote_cloned_output.wav")
```

*For full implementation details, see: [main_remote.py](main_remote.py)*

### Voice Preset Specification (v1.0)
VieNeu-TTS uses the official `vieneu.voice.presets` specification to define reusable voice assets.
Only `voices.json` files following this spec are guaranteed to be compatible with VieNeu-TTS SDK ≥ v1.x.

### 3. Advanced Configuration

Customize the server to run specific versions or your own fine-tuned models.

**Run the 0.3B Model (Faster):**
```bash
docker run --gpus all pnnbao/vieneu-tts:serve --model pnnbao-ump/VieNeu-TTS-0.3B --tunnel
```

**Serve a Local Fine-tuned Model:**
If you have merged a LoRA adapter, mount your output directory to the container:
```bash
# Linux / macOS
docker run --gpus all \
  -v $(pwd)/finetune/output:/workspace/models \
  pnnbao/vieneu-tts:serve \
  --model /workspace/models/merged_model --tunnel
```

*For full implementation details, see: [main_remote.py](main_remote.py)*

---

## 🎯 4. Custom Models (LoRA, GGUF, Finetune) <a name="custom-models"></a>

VieNeu-TTS allows you to load custom models directly from HuggingFace or local paths via the Web UI.

*👉 See the detailed guide at: **[docs/CUSTOM_MODEL_USAGE.md](docs/CUSTOM_MODEL_USAGE.md)***

---

## 🛠️ 5. Fine-tuning Guide <a name="finetuning"></a>

Train VieNeu-TTS on your own voice or custom datasets.

- **Simple Workflow:** Use the `train.py` script with optimized LoRA configurations.
- **Documentation:** Follow the step-by-step guide in **[finetune/README.md](finetune/README.md)**.
- **Notebook:** Experience it directly on Google Colab via `finetune/finetune_VieNeu-TTS.ipynb`.

---

## 🔬 6. Model Overview (Backbones) <a name="backbones"></a>

| Model                   | Format  | Device  | Quality    | Speed                   |
| ----------------------- | ------- | ------- | ---------- | ----------------------- |
| VieNeu-TTS              | PyTorch | GPU/CPU | ⭐⭐⭐⭐⭐ | Very Fast with lmdeploy |
| VieNeu-TTS-0.3B         | PyTorch | GPU/CPU | ⭐⭐⭐⭐   | **Ultra Fast (2x)**     |
| VieNeu-TTS-q8-gguf      | GGUF Q8 | CPU/GPU | ⭐⭐⭐⭐   | Fast                    |
| VieNeu-TTS-q4-gguf      | GGUF Q4 | CPU/GPU | ⭐⭐⭐     | Very Fast               |
| VieNeu-TTS-0.3B-q8-gguf | GGUF Q8 | CPU/GPU | ⭐⭐⭐⭐   | **Ultra Fast (1.5x)**   |
| VieNeu-TTS-0.3B-q4-gguf | GGUF Q4 | CPU/GPU | ⭐⭐⭐     | **Extreme Speed (2x)**  |

### 🔬 Model Details

- **Training Data:** [VieNeu-TTS-1000h](https://huggingface.co/datasets/pnnbao-ump/VieNeu-TTS-1000h) — 443,641 curated Vietnamese samples (Used for all versions).
- **Audio Codec:** NeuCodec (Torch implementation; ONNX & quantized variants supported).
- **Context Window:** 2,048 tokens shared by prompt text and speech tokens.
- **Output Watermark:** Enabled by default.

---

## 🐋 7. Deployment with Docker (Compose) <a name="docker"></a>

Deploy quickly without manual environment setup.

> **Note:** Docker deployment currently supports **GPU only**. For CPU usage, please follow the [Installation & Web UI](#installation) section to install from source.

```bash
# Run with GPU (Requires NVIDIA Container Toolkit)
docker compose --profile gpu up
```
Check [docs/Deploy.md](docs/Deploy.md) for more details.

---


## 📚 References

- **Dataset:** [VieNeu-TTS-1000h (Hugging Face)](https://huggingface.co/datasets/pnnbao-ump/VieNeu-TTS-1000h)
- **Model 0.5B:** [pnnbao-ump/VieNeu-TTS](https://huggingface.co/pnnbao-ump/VieNeu-TTS)
- **Model 0.3B:** [pnnbao-ump/VieNeu-TTS-0.3B](https://huggingface.co/pnnbao-ump/VieNeu-TTS-0.3B)
- **LoRA Guide:** [docs/CUSTOM_MODEL_USAGE.md](docs/CUSTOM_MODEL_USAGE.md)

---

## 🤝 8. Support & Contact <a name="support"></a>

- **Hugging Face:** [pnnbao-ump](https://huggingface.co/pnnbao-ump)
- **Discord:** [Join our community](https://discord.gg/yJt8kzjzWZ)
- **Facebook:** [Pham Nguyen Ngoc Bao](https://www.facebook.com/bao.phamnguyenngoc.5)
- **Licensing:** 
  - **VieNeu-TTS (0.5B):** Apache 2.0 (Free to use).
  - **VieNeu-TTS-0.3B:** CC BY-NC 4.0 (Non-commercial).
    - ✅ **Free:** For students, researchers, and non-profit purposes.
    - ⚠️ **Commercial/Enterprise:** Contact the author for licensing.

---

## 📑 Citation

```bibtex
@misc{vieneutts2026,
  title        = {VieNeu-TTS: Vietnamese Text-to-Speech with Instant Voice Cloning},
  author       = {Pham Nguyen Ngoc Bao},
  year         = {2026},
  publisher    = {Hugging Face},
  howpublished = {\url{https://huggingface.co/pnnbao-ump/VieNeu-TTS}}
}
```

---

## 🙏 Acknowledgements

This project builds upon the [NeuTTS Air](https://huggingface.co/neuphonic/neutts-air) and [NeuCodec](https://huggingface.co/neuphonic/neucodec) architectures. Specifically, the **VieNeu-TTS (0.5B)** model is fine-tuned from NeuTTS Air, while the **VieNeu-TTS-0.3B** model is a custom architecture trained from scratch using the [VieNeu-TTS-1000h](https://huggingface.co/datasets/pnnbao-ump/VieNeu-TTS-1000h) dataset.

---

**Made with ❤️ for the Vietnamese TTS community**
