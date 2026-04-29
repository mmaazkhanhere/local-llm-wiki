from __future__ import annotations


def source_summary_system_prompt() -> str:
    return (
        "You are maintaining a local, Obsidian-compatible LLM Wiki for a learner.\n\n"
        "Rules:\n"
        "- Do not invent facts.\n"
        "- Use only the provided source content.\n"
        "- Preserve source grounding.\n"
        "- Write in clear Markdown.\n"
        "- This is a generated source summary, not an edit to the raw source.\n"
        "- Focus on helping the user learn the material.\n"
        "- Include key ideas, definitions, examples, and questions the source helps answer.\n"
        "- If the source is unclear or incomplete, say so.\n"
    )


def source_summary_user_prompt(
    *,
    source_title: str,
    relative_source_path: str,
    extracted_text: str,
) -> str:
    return (
        f"Source title: {source_title}\n"
        f"Source path: {relative_source_path}\n\n"
        "Generate a concise, source-grounded summary in Markdown.\n"
        "Use headings and bullet points for readability.\n"
        "Include citations that reference the source path.\n\n"
        "Source content:\n"
        f"{extracted_text}\n"
    )
