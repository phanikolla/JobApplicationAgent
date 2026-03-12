# Lessons Learned

*This file tracks corrections and self-improvement loops.*

## General Principles
- Do not mark a task complete until verified (e.g. validating PDF formatting).
- Seek simple, elegant solutions before writing overly complex scripts.
- Only fix what is broken, avoid unnecessary impact.

## Autonomous Fixes
- **LangChain Google GenAI Model Names**: When initializing `ChatGoogleGenerativeAI`, the exact string `gemini-1.5-flash` may return an HTTP 404 NOT_FOUND error depending on the `langchain-google-genai` package. Some newer API keys exclusively support `gemini-2.0-flash` or `gemini-2.5-flash` over the `1.5` architectures. To ensure highest compatibility without guessing, running a quick python script to dump `genai.list_models()` is the fastest way to resolve `NOT_FOUND` bugs.

## Formatting Issues
- **Markdown Resumes & PDF Conversion**: When relying on Python markdown-to-html libraries for PDF generation, be sure that the generated markdown structure explicitly mandates an *empty line* before bulleted lists (e.g., after the company description block). Failing to include this empty line will cause the markdown parser to treat asterisks as literal characters instead of list items, ruining text flow and font consistency.
