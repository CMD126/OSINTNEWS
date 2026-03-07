"""
Advanced prompt engineering for the RAG Generator.

Design goals:
  1. GROUNDING    — LLM is anchored to retrieved sources only (anti-hallucination).
  2. CITATIONS    — Every factual claim must cite a [Source N] reference.
  3. STRUCTURED   — Output follows a fixed schema for easy parsing & HTML rendering.
  4. CALIBRATION  — Risk levels have explicit definitions to prevent over/under-assessment.
  5. GAP HONESTY  — Model must declare what it cannot determine from available data.

Functional principle: prompts are pure strings built from pure functions.
No state, no side effects — same inputs always produce the same prompt.
"""

from modules.rag.models import NewsItem

# ---------------------------------------------------------------------------
# System prompt — the "instruction set" for the LLM
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior OSINT Intelligence Analyst with expertise in:
- Open-source intelligence gathering and analysis
- Risk assessment and threat modeling
- Investigative journalism and due diligence
- Cybersecurity and corporate intelligence

YOUR MISSION:
Analyze retrieved news and document snippets about a target and produce a structured, \
evidence-based intelligence report.

═══════════════════════════════════════════════════════
CRITICAL ANTI-HALLUCINATION RULES — NEVER VIOLATE THESE
═══════════════════════════════════════════════════════
1. ONLY use information explicitly present in the provided [Source N] entries.
2. NEVER add external knowledge, assumptions, or information from your training data.
3. EVERY factual claim in your report MUST be followed by its citation: [Source N]
4. If sources are insufficient to answer a question, write exactly: "⚠ Insufficient data."
5. Clearly distinguish between:
   • CONFIRMED FACT — directly stated in a source
   • INFERENCE     — logical deduction from source content (label it as such)
   • ALLEGATION    — claimed but unverified information in a source

RISK LEVEL DEFINITIONS (use these exact definitions):
• LOW      — Routine business activity, no negative findings
• MEDIUM   — Minor concerns, reputation risk, civil disputes
• HIGH     — Serious legal issues, criminal investigations, significant financial risk
• CRITICAL — Active criminal charges, sanctions, systemic fraud, imminent threats

OUTPUT FORMAT:
Always respond with the exact section headers shown in the user prompt.
Use markdown formatting. Be concise and professional.
Do not add disclaimers, preambles, or meta-commentary about your role."""


# ---------------------------------------------------------------------------
# Pure context builder
# ---------------------------------------------------------------------------

def build_source_context(items: tuple, max_items: int = 25) -> str:
    """
    Pure function: tuple[NewsItem] → formatted source context string.
    Limits to max_items to stay within LLM context windows.
    """
    selected = items[:max_items]
    parts = []
    for i, item in enumerate(selected, 1):
        parts.append(
            f"[Source {i}]\n"
            f"Category : {item.category}\n"
            f"Title    : {item.title}\n"
            f"URL      : {item.url}\n"
            f"Snippet  : {item.snippet}\n"
        )
    return "\n" + ("─" * 60 + "\n").join(parts)


def build_user_prompt(target: str, source_context: str, source_count: int) -> str:
    """
    Pure function: builds the user-facing analysis prompt.
    The structured sections act as a schema that constrains the LLM output.
    """
    return f"""INTELLIGENCE TARGET: "{target}"
TOTAL SOURCES PROVIDED: {source_count}
ANALYSIS DATE: Use current date.

━━━━━━━━━━━━━━━━━━━━ RETRIEVED SOURCES ━━━━━━━━━━━━━━━━━━━━
{source_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Using ONLY the sources above, produce an intelligence report with these EXACT sections:

## 🎯 Executive Summary
Write 2–4 paragraphs. Summarize the most significant findings about "{target}".
Cite every factual claim inline: e.g., "The company faces regulatory scrutiny [Source 3]."

## ⚠️ Risk Assessment
**Overall Risk Level: [LOW / MEDIUM / HIGH / CRITICAL]**
**Justification:** 2–3 sentences explaining the rating with source citations.

## 🔍 Key Findings
List 4–10 bullet points. Each bullet MUST follow this format:
- **[FACT/INFERENCE/ALLEGATION]** Finding statement. [Source N]

## 📰 Source Summary
Brief one-line description of each source used, with its URL.
Format: `[Source N]` — Title (URL)

## 🕳️ Intelligence Gaps
List topics or questions that CANNOT be answered from the available sources.
If no gaps exist, write: "All key questions addressed by available sources."

## 💡 Recommended Actions
List 2–5 specific, actionable recommendations based solely on the findings above.

REMEMBER: If you cannot support a statement with a [Source N] citation, DO NOT include it."""


# ---------------------------------------------------------------------------
# Pure prompt assembler
# ---------------------------------------------------------------------------

def build_prompt_pair(
    target: str,
    items:  tuple,
    max_sources: int = 25,
) -> tuple[str, str]:
    """
    Pure function: returns (system_prompt, user_prompt) tuple.
    The caller sends these directly to the LLM API.
    """
    context      = build_source_context(items, max_items=max_sources)
    user_prompt  = build_user_prompt(target, context, min(len(items), max_sources))
    return (SYSTEM_PROMPT, user_prompt)
