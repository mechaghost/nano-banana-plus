# AI Image Studio

A sophisticated local web application combining cloud-based AI image generation and local machine learning for image processing. Built with a responsive, glassmorphic UI and a lightning-fast API backend perfectly suited for both human users and AI agent integrations.

## Features

- **Gemini Image Generation**: Generate stunning assets using Google's latest **Imagen 4.0** models (Fast, Standard, and Ultra) directly via the Gemini API.
- **Image-to-Image Support**: Upload an initial asset alongside your text prompt to guide the AI's generation.
- **Local Background Removal**: Uses `rembg` (U^2-Net model) to strip backgrounds natively without any cloud overhead.
- **Smart Cropping**: Trims transparency and isolates the subject using `Pillow` bounding box calculations.
- **Agentic API**: The FastAPI backend automatically generates standard OpenAPI documentation, allowing modern AI tools and agents to seamlessly interact with your local server.

## Architecture

This project is separated into two microservices contained within this repository:

1.  **`server/`**: A Python **FastAPI** backend handling external cloud routing and local ML loading.
2.  **`web/`**: A **Vite + React** frontend leveraging raw CSS for dynamic styling and interactions.

## Getting Started

Because the UI connects directly to the server API, you need to run both concurrently in separate terminals.

### 1. Start the API Backend
Open a terminal in the root directory and run the following:

```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # Or manually install: fastapi "uvicorn[standard]" google-genai rembg Pillow python-multipart python-dotenv
python3 main.py
```
*The backend will boot up on `http://127.0.0.1:43211`.*

### 2. Start the Frontend web UI
Open a second terminal window in the root directory:

```bash
cd web
npm install
npm run dev
```
*The frontend will boot up on `http://127.0.0.1:43210`.*

### 3. Usage & Configuration
1. Open [http://localhost:43210/](http://localhost:43210/) in your web browser.
2. If this is your first time running the server, the UI will prompt you to input your `GEMINI_API_KEY`.
3. Provide your key. This application automatically serializes it securely into your local `server/.env` file.
4. Enjoy generating and cropping images!
