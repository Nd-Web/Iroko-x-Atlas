"""Recognise whole conversational utterances, never substantive questions.

This gate does not answer or verify regulatory facts. A mixed message such as
"thanks, what is the fine?" must still pass through evidence-backed answering.
"""

import re
import unicodedata


def conversational_kind(question: str) -> str | None:
    text = unicodedata.normalize("NFKC", question).lower().strip()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\bthat'?s\b", "that is", text)
    text = re.sub(r"\b(it'?s)\b", "it is", text)
    text = re.sub(r"[^\w\s']", " ", text)
    text = " ".join(text.split())
    if not text or len(text.split()) > 20:
        return None
    if re.fullmatch(r"(?:(?:h+a+h+a+[ha]*|lol|lmao)\s+)?(?:ok|okay|alright|all right|nice one|thanks|thank you)(?:\s+(?:thanks|thank you|alright))?(?:\s+(?:bro|brochacho|mate|buddy|fam))?", text):
        return "acknowledgement"
    if re.fullmatch(r"(?:nothing much|not much|not yet|maybe later|h+a+h+a+[ha]*|lol|lmao|wow|(?:ok|okay) (?:bro|brochacho|mate)|just (?:saying hi|checking in))(?: (?:today|right now|lol|haha|thanks)){0,3}", text):
        return "social"
    if re.fullmatch(r"(?:wow )?how smart are you|(?:tell me )?(?:all )?about (?:yourself|what you can (?:provide|do)(?: (?:for|to) me)?)|what can you (?:provide|offer)(?: (?:for|to) me)?", text):
        return "capabilities"
    greeting = r"(?:hi|hello|hey|yo|sup|good morning|good afternoon|good evening|how are you(?: doing)?|how body|how far)"
    if re.fullmatch(rf"{greeting}(?: iroko| there)?(?:\s+{greeting})?", text):
        return "greeting"
    if re.fullmatch(r"(?:bye|goodbye|see you|see you later|talk later)(?: iroko)?", text):
        return "farewell"
    if re.fullmatch(r"(?:who are you|what can you (?:actually )?(?:do|help me with)|what do you do|how can you help(?: me)?|what is iroko(?: ai)?)(?: iroko)?", text):
        return "capabilities"
    acknowledgement = r"(?:ok|okay|alright|all right|thanks(?: a lot| so much| for (?:that|this|the help|explaining))?|thank you(?: so much| very much| for (?:that|this|the help|explaining))?|got it|understood|sounds (?:good|great)|nice|great|cool|awesome|perfect|cheers|appreciate (?:it|that)|(?:that|it) (?:is|was|sounds) (?:nice|good|great|helpful|clear)|that helps|that makes sense|makes sense|all clear|no worries|no problem)"
    if re.fullmatch(rf"(?:oh |ah )?{acknowledgement}(?:\s+{acknowledgement})*(?: iroko)?", text):
        return "acknowledgement"
    if re.fullmatch(r"(?:(?:i(?:'m| am) (?:doing )?|doing )(?:fine|well|good)(?: thanks| thank you)?|(?:fine|well|good)(?: thanks| thank you))(?: and you| how about you)?", text):
        return "acknowledgement"
    return None


def conversational_reply(kind: str, is_pidgin: bool = False, *, question: str = "", first_name: str = "") -> dict:
    if kind == "greeting":
        answer = f"Hi{', ' + first_name if first_name else ''}! What's on your mind?"
    elif kind == "capabilities":
        answer = ("I can help you make sense of your documents and work through compliance questions. For example:\n\n"
                  "- **Explain a document:** turn dense wording into clear requirements and next steps.\n"
                  "- **Compare sources:** highlight differences, dates, and conflicting instructions.\n"
                  "- **Research a requirement:** check available official sources and show where the answer comes from.\n"
                  "- **Work through a risk:** identify what the evidence supports and which records are still needed.\n"
                  "- **Help draft:** prepare a source-based summary or checklist for your review.\n\n"
                  "You can start with a rough question, or name a document you'd like to understand.")
        if "how smart" in question.lower():
            answer = "Good at untangling dense documents, comparing requirements, and helping you reason through a compliance question. Give me something to work through and see how I do."
        elif "shorter" in question.lower():
            answer = "I can explain and compare your documents, research regulatory requirements, and help prepare clear summaries or checklists with supporting sources."
    elif kind == "farewell":
        answer = "Talk soon. Your saved conversation will be here when you return."
    elif kind == "social":
        text = question.lower()
        answer = "No rush. I'm here whenever you're ready."
        if any(word in text for word in ("haha", "lol", "lmao", "bro", "wow")):
            answer = "😄 You got it."
    else:
        answer = "You're welcome." if "thank" in question.lower() else "Sounds good."
    if is_pidgin and kind == "acknowledgement":
        answer = "No wahala. Wetin you wan make we look at next?"
    return {"answer": answer, "citations": [], "suggested_followups": [], "confidence": "high", "_grounded": True}
