import os
import logging
from typing import TypedDict, List
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages import HumanMessage, SystemMessage
from llm_utils import get_llm


from langgraph.graph import StateGraph, START, END

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define State
class AgentState(TypedDict):
    job_title: str
    company_name: str
    job_description: str
    master_resume: str
    extracted_keywords: List[str]
    tailored_resume: str


# Node 1: Extract Keywords
def extract_keywords_node(state: AgentState):
    logger.info("Node: Extracting Keywords...")
    llm = get_llm(temperature=0)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical recruiter analyzing a job description. Extract the top 15 most important technical skills, tools, and keywords required for this role. Output MUST be valid JSON with a single key 'keywords' containing a list of strings."),
        ("human", "Job Title: {job_title}\nCompany: {company_name}\nDescription:\n{job_description}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({
            "job_title": state["job_title"],
            "company_name": state["company_name"],
            "job_description": state["job_description"]
        })
        keywords = result.get("keywords", [])
        logger.info(f"Extracted Keywords: {keywords}")
        return {"extracted_keywords": keywords}
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return {"extracted_keywords": []}

# Node 2: Tailor Resume
def tailor_resume_node(state: AgentState):
    logger.info("Node: Tailoring Resume...")
    llm = get_llm(temperature=0.2)
    
    system_instruction = """
    You are an expert Resume Writer and Career Coach. 
    Your task is to take a Master Resume and a Job Description (along with its key ATS keywords), 
    and tailor the Master Resume to perfectly fit the role.
    
    CRITICAL RULES:
    1. DO NOT HALLUCINATE experience. Only rephrase and emphasize existing experience.
    2. Naturally integrate the highly relevant extracted keywords into the professional summary and bullet points.
    3. Keep the output focused strictly on the resume content. Do not include extra conversational text like "Here is your resume".
    4. PUNCTUATION RULE: Absolutely NO em-dashes (`——`). If you need a dash, use a standard hyphen (`-`). Em-dashes break downstream tools.
    5. FORMATTING RULE: You MUST use EXACTLY this markdown skeleton structure to ensure the PDFs render evenly. Do not omit the '#' header tags. ALWAYS include valid Markdown Links for formatting Contact details (e.g. `[LinkedIn](https://...)`):
    6. KEYWORD HIGHLIGHTING: Highlight highly relevant extracted keywords by using **bold** text naturally within your bullet points.
    
    # [Full Name]
    [Location] | [Phone] | [Email] | [LinkedIn](url) | [GitHub](url)
    
    ## PROFESSIONAL SUMMARY
    [1-2 paragraphs here]
    
    ## CORE COMPETENCIES
    * [Bullet points here]
    
    ## PROFESSIONAL EXPERIENCE
    **[Job Title]** | [Dates]  
    *[Company]* - [Short Description]  
    
    * [Achievement bullets...]
    
    ## EDUCATION
    **[Degree]** | [Dates]  
    *[University]*
    """
    
    human_instruction = f"""
    TARGET ROLE: {state['job_title']} at {state['company_name']}
    
    EXTRACTED ATS KEYWORDS TO INCLUDE IF POSSIBLE:
    {', '.join(state['extracted_keywords'])}
    
    MASTER RESUME CONTENT:
    {state['master_resume']}
    
    JOB DESCRIPTION:
    {state['job_description']}
    
    Return the optimized resume formatted in Markdown.
    """
    
    messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=human_instruction)
    ]
    
    try:
        response = llm.invoke(messages)
        tailored_markdown = response.content
        logger.info("Successfully tailored the resume.")
        return {"tailored_resume": tailored_markdown}
    except Exception as e:
        logger.error(f"Error tailoring resume: {e}")
        return {"tailored_resume": f"Error tailoring resume: {str(e)}"}

# Build the Graph
def build_tailor_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("extract_keywords", extract_keywords_node)
    workflow.add_node("tailor_resume", tailor_resume_node)
    
    workflow.add_edge(START, "extract_keywords")
    workflow.add_edge("extract_keywords", "tailor_resume")
    workflow.add_edge("tailor_resume", END)
    
    return workflow.compile()

# Main entry point for this module
def tailor_for_job(job_title, company_name, job_description, master_resume_text):
    graph = build_tailor_graph()
    
    initial_state = {
        "job_title": job_title,
        "company_name": company_name,
        "job_description": job_description,
        "master_resume": master_resume_text,
        "extracted_keywords": [],
        "tailored_resume": ""
    }
    
    logger.info(f"Invoking graph for {job_title}")
    result = graph.invoke(initial_state)
    return result["tailored_resume"]

if __name__ == "__main__":
    # Test execution
    print("Graph builder module compiled successfully.")
