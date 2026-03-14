import os
import logging
from dotenv import load_dotenv
from src.core.config import load_config

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    has_gemini = True
except ImportError:
    has_gemini = False

try:
    from langchain_openai import ChatOpenAI
    has_openai = True
except ImportError:
    has_openai = False

load_dotenv()
logger = logging.getLogger(__name__)

def get_llm(temperature=None):
    cfg = load_config()

    if temperature is None:
        temperature = cfg.llm.default_temperature

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if has_gemini and gemini_key and gemini_key != "your_gemini_api_key_here":
        return ChatGoogleGenerativeAI(model=cfg.llm.gemini_model, temperature=temperature)
    elif has_openai and openai_key and openai_key != "your_openai_api_key_here":
        return ChatOpenAI(model=cfg.llm.openai_model, temperature=temperature)
    else:
        raise ValueError("No valid API keys found for Gemini or OpenAI in .env")
