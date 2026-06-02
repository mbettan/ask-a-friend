import re

PATTERNS = {
    "EMAIL": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "APIKEY": r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36})",
    "BEARER": r"Bearer\s+[\w.\-]{20,}",
    "PRIVATE_KEY": r"-----BEGIN [A-Z ]*PRIVATE KEY-----[A-Za-z0-9+/=\s\n]*-----END [A-Z ]*PRIVATE KEY-----",
    "HOME_DIR": r"(?:/Users|/home|/root|[A-Za-z]:[\\/]Users)[\\/][A-Za-z0-9_.-]+"  # Mask absolute username-containing paths
}

def redact(text):
    if not text:
        return "", {}
    lookup = {}
    counter = {}
    def repl(kind):
        def inner(m):
            counter[kind] = counter.get(kind, 0) + 1
            token = f"[{kind}_{counter[kind]}]"
            lookup[token] = m.group(0)
            return token
        return inner
    for kind, pat in PATTERNS.items():
        text = re.sub(pat, repl(kind), text)
    return text, lookup

def rehydrate(text, lookup):
    if not text:
        return ""
    for token, raw in lookup.items():
        text = text.replace(token, raw)
    return text
