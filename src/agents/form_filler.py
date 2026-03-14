"""
LangGraph-based auto-apply engine.
Visits job application pages, reads form fields, maps to applicant profile,
fills fields via Playwright, and submits with human-in-the-loop confirmation.

All Playwright calls use the sync API. The entire graph runs in a dedicated
thread (via run_in_executor in app.py) to avoid asyncio conflicts.
"""

import base64
import json
import logging
import os
import time
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from playwright.sync_api import sync_playwright

from src.core.llm import get_llm
from src.models.profile_parser import get_profile_as_text
from src.core.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory for apply screenshots
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "apply_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


# =====================================================================
# State
# =====================================================================
class ApplyState(TypedDict):
    application_url: str
    resume_pdf_path: str
    profile_text: str
    current_step: int
    max_steps: int
    page_screenshot_b64: str
    page_fields_text: str
    fill_actions: list
    status: str  # reading, filling, waiting_approval, submitting, completed, failed
    message: str
    screenshots: list  # list of file paths
    error: str


# =====================================================================
# Global browser session (managed within the executor thread)
# =====================================================================
_apply_session = {
    "playwright": None,
    "browser": None,
    "page": None,
}


def _ensure_browser(url: str) -> bool:
    """Start browser and navigate to URL. Returns True on success."""
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        _apply_session["playwright"] = pw
        _apply_session["browser"] = browser
        _apply_session["page"] = page
        return True
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        return False


def _read_page() -> dict:
    """Read the current page: extract form fields and take a screenshot."""
    page = _apply_session.get("page")
    if not page:
        return {"fields_text": "", "screenshot_b64": "", "error": "No active page"}

    try:
        screenshot_bytes = page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        ts = int(time.time())
        shot_path = os.path.join(SCREENSHOTS_DIR, f"step_{ts}.png")
        with open(shot_path, "wb") as f:
            f.write(screenshot_bytes)

        fields_text = page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, select, textarea');
                inputs.forEach((el, idx) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) return;

                    const type = el.tagName.toLowerCase() === 'select' ? 'select' :
                                 el.tagName.toLowerCase() === 'textarea' ? 'textarea' :
                                 (el.type || 'text');

                    let label = '';
                    if (el.id) {
                        const labelEl = document.querySelector(`label[for="${el.id}"]`);
                        if (labelEl) label = labelEl.textContent.trim();
                    }
                    if (!label && el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
                    if (!label && el.placeholder) label = el.placeholder;
                    if (!label) {
                        const parent = el.closest('label, .form-group, .field, [data-automation-id]');
                        if (parent) label = parent.textContent.trim().substring(0, 100);
                    }

                    const required = el.required || el.getAttribute('aria-required') === 'true';
                    let options = [];
                    if (el.tagName.toLowerCase() === 'select') {
                        options = Array.from(el.options).map(o => o.text).filter(t => t.trim());
                    }

                    let selector = '';
                    if (el.id) selector = '#' + CSS.escape(el.id);
                    else if (el.name) selector = `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                    else if (el.getAttribute('data-automation-id')) selector = `[data-automation-id="${el.getAttribute('data-automation-id')}"]`;
                    else if (el.getAttribute('aria-label')) selector = `[aria-label="${el.getAttribute('aria-label')}"]`;
                    else selector = `${el.tagName.toLowerCase()}:nth-of-type(${idx + 1})`;

                    fields.push({
                        index: idx,
                        type: type,
                        label: label.substring(0, 150),
                        selector: selector,
                        required: required,
                        current_value: (el.value || '').substring(0, 100),
                        options: options.slice(0, 20)
                    });
                });

                const buttons = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
                const actionBtns = [];
                buttons.forEach(btn => {
                    const text = (btn.textContent || btn.value || '').trim().toLowerCase();
                    if (['submit', 'next', 'continue', 'apply', 'review', 'save'].some(k => text.includes(k))) {
                        let selector = '';
                        if (btn.id) selector = '#' + CSS.escape(btn.id);
                        else if (btn.getAttribute('data-automation-id')) selector = `[data-automation-id="${btn.getAttribute('data-automation-id')}"]`;
                        else selector = `button:has-text("${text.substring(0, 30)}")`;

                        actionBtns.push({ text: text.substring(0, 50), selector: selector, type: 'button' });
                    }
                });

                return JSON.stringify({
                    page_title: document.title,
                    page_url: window.location.href,
                    form_fields: fields,
                    action_buttons: actionBtns,
                    visible_text: document.body.innerText.substring(0, 3000)
                });
            }
        """)

        return {"fields_text": fields_text, "screenshot_b64": screenshot_b64, "screenshot_path": shot_path}
    except Exception as e:
        logger.error(f"Error reading page: {e}")
        return {"fields_text": "", "screenshot_b64": "", "error": str(e)}


def _fill_fields(actions: list, resume_pdf_path: str) -> list:
    """Execute fill actions on the current page. Returns list of result strings."""
    page = _apply_session.get("page")
    if not page:
        return ["No active page"]

    results = []
    for action in actions:
        try:
            selector = action.get("selector", "")
            act_type = action.get("action", "")
            value = action.get("value", "")

            if act_type == "type":
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        page.wait_for_timeout(200)
                        el.fill(value)
                    else:
                        page.locator(selector).first.fill(value)
                    results.append(f"Typed '{value[:30]}' into {selector}")
                except Exception as e:
                    results.append(f"Type failed {selector}: {e}")

            elif act_type == "select":
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.select_option(label=value)
                    else:
                        page.locator(selector).first.click()
                        page.wait_for_timeout(500)
                        page.locator(f"text={value}").first.click()
                    results.append(f"Selected '{value}' in {selector}")
                except Exception as e:
                    results.append(f"Select failed {selector}: {e}")

            elif act_type == "check":
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.check()
                    results.append(f"Checked {selector}")
                except Exception as e:
                    results.append(f"Check failed {selector}: {e}")

            elif act_type == "upload":
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.set_input_files(resume_pdf_path)
                    else:
                        page.locator(selector).set_input_files(resume_pdf_path)
                    results.append(f"Uploaded resume to {selector}")
                except Exception as e:
                    results.append(f"Upload failed {selector}: {e}")

            elif act_type == "skip":
                results.append(f"Skipped: {action.get('reason', '')}")

            page.wait_for_timeout(300)
        except Exception as e:
            results.append(f"Action error: {e}")

    return results


def _click_button(selector: str) -> bool:
    """Click a button and wait for transition."""
    page = _apply_session.get("page")
    if not page:
        return False
    try:
        el = page.query_selector(selector)
        if el:
            el.click()
        else:
            page.locator(selector).first.click()
        page.wait_for_timeout(3000)
        return True
    except Exception as e:
        logger.warning(f"Click failed for {selector}: {e}")
        return False


def _close_browser():
    """Close the browser session."""
    try:
        if _apply_session.get("browser"):
            _apply_session["browser"].close()
        if _apply_session.get("playwright"):
            _apply_session["playwright"].stop()
    except Exception:
        pass
    finally:
        _apply_session["playwright"] = None
        _apply_session["browser"] = None
        _apply_session["page"] = None


# =====================================================================
# LangGraph Nodes (all synchronous - run in executor thread)
# =====================================================================

def navigate_to_application(state: ApplyState) -> dict:
    """Node 1: Open browser and navigate to the application URL."""
    logger.info(f"Navigating to application: {state['application_url']}")

    success = _ensure_browser(state["application_url"])
    if not success:
        return {"status": "failed", "error": "Failed to open browser", "message": "Failed to navigate to application URL"}

    return {"status": "reading", "current_step": 1, "message": "Navigated to application page"}


def read_form_page(state: ApplyState) -> dict:
    """Node 2: Read the current form page."""
    logger.info(f"Reading form page (step {state['current_step']})...")

    result = _read_page()
    if result.get("error"):
        return {"status": "failed", "error": result["error"], "message": "Failed to read form page"}

    screenshots = list(state.get("screenshots", []))
    if result.get("screenshot_path"):
        screenshots.append(result["screenshot_path"])

    return {
        "page_fields_text": result["fields_text"],
        "page_screenshot_b64": result["screenshot_b64"],
        "screenshots": screenshots,
        "status": "filling",
        "message": f"Read form page (step {state['current_step']})"
    }


def map_and_fill_fields(state: ApplyState) -> dict:
    """Node 3: LLM maps form fields to profile data and fills them."""
    logger.info("LLM mapping fields to profile data...")

    llm = get_llm(temperature=0.0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert job application form filler. You will receive:
1. A JSON description of form fields visible on the current page
2. The applicant's profile with all their personal/professional details

Your task: Generate a JSON array of actions to fill each visible form field.

RULES:
- Fill ALL fields, especially required ones
- For file upload fields (type "file"), use action "upload"
- For select/dropdown fields, choose the BEST matching option from available options
- For checkboxes, use action "check" if appropriate
- For text/textarea fields, use action "type"
- If a field asks a question not in the profile, craft a professional answer
- If a field is already correctly filled, use action "skip" with reason "already filled"
- Do NOT fill password fields or account creation fields
- For "How did you hear about us" questions, answer "LinkedIn"
- ALWAYS identify the Next/Submit/Continue/Apply button and add a "click" action LAST

Return ONLY a valid JSON array. Each item:
{{"selector": "CSS selector", "action": "type|select|check|click|upload|skip", "value": "the value", "reason": "brief explanation"}}"""),
        ("human", """FORM FIELDS:
{fields_text}

APPLICANT PROFILE:
{profile_text}

RESUME PDF PATH: {resume_path}

Generate the fill actions as a JSON array:""")
    ])

    chain = prompt | llm | JsonOutputParser()

    try:
        actions = chain.invoke({
            "fields_text": state["page_fields_text"],
            "profile_text": state["profile_text"],
            "resume_path": state["resume_pdf_path"]
        })

        logger.info(f"LLM generated {len(actions)} fill actions")

        # Separate fill actions from click actions
        fill_actions = [a for a in actions if a.get("action") != "click"]
        if fill_actions:
            results = _fill_fields(fill_actions, state["resume_pdf_path"])
            for r in results:
                logger.info(f"  {r}")

        return {
            "fill_actions": actions,
            "status": "reading",
            "message": f"Filled {len(fill_actions)} fields on step {state['current_step']}"
        }
    except Exception as e:
        logger.error(f"Error in LLM field mapping: {e}")
        return {"status": "failed", "error": str(e), "message": "Failed to map fields with LLM"}


def detect_next_or_submit(state: ApplyState) -> dict:
    """Node 4: Detect and click next/submit button."""
    actions = state.get("fill_actions", [])
    click_actions = [a for a in actions if a.get("action") == "click"]

    if not click_actions:
        logger.warning("No next/submit button found by LLM")
        return {"status": "waiting_approval", "message": "No clear next/submit button found. Please review."}

    click_action = click_actions[-1]
    btn_text = (click_action.get("reason", "") + click_action.get("value", "")).lower()
    is_submit = any(kw in btn_text for kw in ["submit", "apply", "finish", "complete"])

    if is_submit:
        logger.info("Submit button detected - pausing for human approval")
        result = _read_page()
        screenshots = list(state.get("screenshots", []))
        if result.get("screenshot_path"):
            screenshots.append(result["screenshot_path"])

        return {
            "status": "waiting_approval",
            "screenshots": screenshots,
            "fill_actions": actions,
            "message": "Ready to submit. Review the form and confirm."
        }
    else:
        logger.info(f"Clicking next: {click_action.get('selector')}")
        _click_button(click_action["selector"])

        return {
            "status": "reading",
            "current_step": state["current_step"] + 1,
            "message": f"Advanced to step {state['current_step'] + 1}"
        }


def submit_application(state: ApplyState) -> dict:
    """Node 5: Final submission after human approval."""
    logger.info("Submitting application...")
    actions = state.get("fill_actions", [])
    click_actions = [a for a in actions if a.get("action") == "click"]

    if click_actions:
        _click_button(click_actions[-1]["selector"])

    time.sleep(3)
    result = _read_page()
    screenshots = list(state.get("screenshots", []))
    if result.get("screenshot_path"):
        screenshots.append(result["screenshot_path"])

    _close_browser()
    return {"status": "completed", "screenshots": screenshots, "message": "Application submitted successfully!"}


def handle_failure(state: ApplyState) -> dict:
    """Handle failures by closing browser."""
    _close_browser()
    return {"status": "failed", "message": state.get("error", "Unknown error occurred")}


# =====================================================================
# Router
# =====================================================================

def route_after_fill(state: ApplyState) -> str:
    if state["status"] == "failed":
        return "handle_failure"
    if state["current_step"] >= state["max_steps"]:
        return "handle_failure"
    return "detect_next_or_submit"


def route_after_detect(state: ApplyState) -> str:
    if state["status"] == "waiting_approval":
        return END
    if state["status"] == "failed":
        return "handle_failure"
    return "read_form_page"


# =====================================================================
# Graph
# =====================================================================

def build_apply_graph():
    graph = StateGraph(ApplyState)
    graph.add_node("navigate", navigate_to_application)
    graph.add_node("read_form_page", read_form_page)
    graph.add_node("map_and_fill", map_and_fill_fields)
    graph.add_node("detect_next_or_submit", detect_next_or_submit)
    graph.add_node("submit", submit_application)
    graph.add_node("handle_failure", handle_failure)

    graph.set_entry_point("navigate")
    graph.add_conditional_edges("navigate", lambda s: "read_form_page" if s["status"] != "failed" else "handle_failure")
    graph.add_edge("read_form_page", "map_and_fill")
    graph.add_conditional_edges("map_and_fill", route_after_fill)
    graph.add_conditional_edges("detect_next_or_submit", route_after_detect)
    graph.add_edge("submit", END)
    graph.add_edge("handle_failure", END)

    return graph.compile()


apply_graph = build_apply_graph()


# =====================================================================
# Public API (called from app.py via run_in_executor)
# =====================================================================

def run_auto_apply(application_url: str, resume_pdf_path: str, profile_path: str = "applicant_profile.md") -> dict:
    """
    Run the auto-apply graph (synchronous - called from executor thread).
    Returns the final state.
    """
    profile_text = get_profile_as_text(profile_path)
    if not profile_text:
        return {"status": "failed", "error": "Applicant profile not found"}

    initial_state: ApplyState = {
        "application_url": application_url,
        "resume_pdf_path": os.path.abspath(resume_pdf_path),
        "profile_text": profile_text,
        "current_step": 0,
        "max_steps": 15,
        "page_screenshot_b64": "",
        "page_fields_text": "",
        "fill_actions": [],
        "status": "reading",
        "message": "Starting auto-apply...",
        "screenshots": [],
        "error": "",
    }

    try:
        final_state = apply_graph.invoke(initial_state)
        return {
            "status": final_state["status"],
            "message": final_state["message"],
            "screenshots": final_state.get("screenshots", []),
            "current_step": final_state.get("current_step", 0),
        }
    except Exception as e:
        logger.error(f"Auto-apply graph error: {e}")
        _close_browser()
        return {"status": "failed", "error": str(e)}


def confirm_and_submit() -> dict:
    """Called after human approves the review page."""
    try:
        page = _apply_session.get("page")
        if not page:
            return {"status": "failed", "error": "No active browser session"}

        page_data = _read_page()

        llm = get_llm(temperature=0.0)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Find the final SUBMIT or APPLY button on this page. Return JSON: {\"selector\": \"CSS selector\"}"),
            ("human", "Page fields:\n{fields_text}")
        ])
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({"fields_text": page_data.get("fields_text", "")})

        submit_selector = result.get("selector", "")
        if submit_selector:
            _click_button(submit_selector)

        time.sleep(3)
        confirmation = _read_page()

        screenshots = []
        if confirmation.get("screenshot_path"):
            screenshots.append(confirmation["screenshot_path"])

        _close_browser()
        return {"status": "completed", "message": "Application submitted successfully!", "screenshots": screenshots}
    except Exception as e:
        logger.error(f"Error during final submit: {e}")
        _close_browser()
        return {"status": "failed", "error": str(e)}
