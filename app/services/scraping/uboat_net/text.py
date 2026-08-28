def clean_text(node) -> str:
    return " ".join(node.text(deep=True, separator=" ", strip=True).split())
