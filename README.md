# 💼 AI Resume Enhancer

An AI-powered resume analyzer and enhancer that:
- Extracts and analyzes resumes from PDF/DOCX
- Compares them against job descriptions
- Suggests bullet point improvements and missing keywords
- Enhances resume language using an LLM

---

## 📦 Features

✅ FastAPI backend  
✅ React frontend  
✅ File upload + parsing  
✅ Local LLM support (via Ollama)  
✅ Async analysis  
✅ Downloadable enhanced resume

---

## 🧠 Requirements

### Python (Backend)
- Python 3.10+
- FastAPI
- Uvicorn
- pdfplumber
- python-docx
- nltk
- requests

Install with:
```bash
cd backend
pip install -r requirements.txt

## 🧠 AI Model Requirements

This app uses the `llama3:8b` or `llama3:70b` models via [Ollama](https://ollama.com/).  
To run the LLM-enhanced features locally, you need:

- At least 16 GB RAM for `llama3:8b`
- At least 48 GB RAM (or swap+GPU) for `llama3:70b`
- Install Ollama and pull the model:
  ```bash
  ollama pull llama3:8b

## 🚀 Future Enhancement Ideas

- Replace Ollama with cloud inference (e.g., Groq or OpenAI)
- Add GPT-based resume templates
- Include skill scoring across multiple job roles
