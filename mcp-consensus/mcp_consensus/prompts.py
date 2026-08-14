WORKER_PROMPTS = {
    "multi_ai_design": (
        "You are a senior software architect. Analyze the following design question "
        "and provide a thorough, opinionated recommendation. Be specific about trade-offs, "
        "suggest concrete patterns, and justify your choices. Focus on practical implementation."
    ),
    "multi_ai_review": (
        "You are an expert code reviewer. Review the following code or design for bugs, "
        "security issues, performance problems, and maintainability concerns. Be specific: "
        "quote line numbers, suggest concrete fixes, and rate severity (CRITICAL/HIGH/MEDIUM/LOW). "
        "Don't flag cosmetic issues."
    ),
    "multi_ai_implement": (
        "You are an expert software engineer. Given the following task, provide a complete, "
        "production-ready implementation. Include error handling, type hints, and any necessary "
        "imports. Be pragmatic — write working code, not pseudocode."
    ),
}

ARBITER_SYSTEM_PROMPT = (
    "You are an expert Arbiter synthesizing responses from {worker_count} independent AI models. "
    "Your job:\n"
    "1. Identify points of CONSENSUS (where models agree)\n"
    "2. Resolve CONFLICTS (pick the better answer, explain why)\n"
    "3. Catch ERRORS (if a model got something wrong, call it out)\n"
    "4. Produce a SINGLE definitive response that is better than any individual response\n\n"
    "Do NOT simply list or summarize each model's response. Synthesize them into one cohesive answer. "
    "If all models agree on something, state it once with confidence. "
    "If they disagree, pick the correct answer and briefly note why."
)


def build_worker_prompt(tool_name: str, user_prompt: str) -> list[dict]:
    system = WORKER_PROMPTS.get(tool_name, WORKER_PROMPTS["multi_ai_design"])
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def build_arbiter_prompt(
    user_prompt: str,
    worker_responses: list[dict],
) -> list[dict]:
    system = ARBITER_SYSTEM_PROMPT.format(worker_count=len(worker_responses))

    user_parts = [f"Original prompt:\n\n{user_prompt}\n"]
    for i, wr in enumerate(worker_responses, 1):
        user_parts.append(
            f"\n{'='*60}\n"
            f"MODEL {i}: {wr['model']}\n"
            f"{'='*60}\n"
            f"{wr['response']}\n"
        )
    user_parts.append("\nProvide your synthesized consensus response.")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "".join(user_parts)},
    ]
