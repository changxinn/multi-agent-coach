"""Fixed user-visible responses for input-guardrails-v1 decisions."""

from .policy_v1 import GuardrailCategory

RESPONSE_TEMPLATES = {
    GuardrailCategory.SELF_HARM: (
        "I’m really sorry you’re dealing with this. If you might hurt yourself or are in "
        "immediate danger, call your local emergency number now. If you’re in the U.S. or "
        "Canada, call or text 988 for the Suicide & Crisis Lifeline. If possible, contact "
        "someone you trust and stay with them."
    ),
    GuardrailCategory.URGENT_MEDICAL: (
        "I can’t assess an urgent medical situation in chat. Please seek immediate medical "
        "care or call your local emergency number, especially for severe symptoms or a serious injury."
    ),
    GuardrailCategory.DISORDERED_EATING: (
        "I can’t help with instructions to harm yourself through food, weight loss, or purging. "
        "You deserve support—please contact a qualified healthcare professional or someone you trust."
    ),
    GuardrailCategory.UNSAFE_EXERCISE: (
        "I can’t help with exercise that could seriously worsen an injury or put you in immediate danger. "
        "Please stop and seek urgent medical advice."
    ),
    GuardrailCategory.EXTREME_DIETING: (
        "I can’t help with extreme or unsafe weight-loss plans. I can help you build a gradual, "
        "sustainable nutrition and activity plan, ideally with guidance from a qualified clinician."
    ),
    GuardrailCategory.INJURY_EXERCISE: (
        "I can’t assess an injury in chat. Please pause the activity that causes pain and check with "
        "a qualified healthcare professional before returning to exercise."
    ),
    GuardrailCategory.SENSITIVE_DATA: (
        "For your privacy, please don’t share passwords, account numbers, government ID numbers, or "
        "other sensitive personal information here."
    ),
    GuardrailCategory.SEXUAL_CONTENT: (
        "I can’t help with sexual content. I can help with safe fitness, nutrition, recovery, or progress questions."
    ),
    GuardrailCategory.VIOLENCE_WRONGDOING: (
        "I can’t help with violence, wrongdoing, or instructions that could harm someone. I can help "
        "with safe fitness, nutrition, recovery, or progress questions."
    ),
    GuardrailCategory.PROMPT_INJECTION: (
        "I can’t follow requests to override instructions or reveal private system information. "
        "I can help with safe fitness, nutrition, recovery, or progress questions."
    ),
    GuardrailCategory.TOOL_MANIPULATION: (
        "I can’t perform or help bypass protected tools, systems, or data. I can help with safe "
        "fitness, nutrition, recovery, or progress questions."
    ),
    GuardrailCategory.HARASSMENT: (
        "I’m here to help, but please keep the conversation respectful. What fitness, nutrition, "
        "recovery, or progress goal would you like support with?"
    ),
    GuardrailCategory.PROFANITY: (
        "I’m happy to help, but please keep the language respectful. What fitness, nutrition, "
        "recovery, or progress goal would you like support with?"
    ),
    GuardrailCategory.UNSUPPORTED: (
        "I’m focused on fitness, nutrition, recovery, and progress support. What would you like "
        "help with in one of those areas?"
    ),
}