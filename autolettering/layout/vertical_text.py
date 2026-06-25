from __future__ import annotations


def vertical_text_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit():
            end = index + 1
            while end < len(text) and text[end].isdigit():
                end += 1
            tokens.extend(_digit_tokens(text[index:end]))
            index = end
            continue
        tokens.append(char)
        index += 1
    return tokens


def _digit_tokens(digits: str) -> list[str]:
    if len(digits) <= 1:
        return [digits]
    tokens: list[str] = []
    index = 0
    while index < len(digits):
        remaining = len(digits) - index
        chunk_size = 4 if remaining >= 4 else remaining
        tokens.append(digits[index : index + chunk_size])
        index += chunk_size
    return tokens


def vertical_digit_group_scale(token: str) -> float:
    if not token.isdigit() or len(token) <= 1:
        return 1.0
    if len(token) >= 4:
        return 0.56
    if len(token) == 3:
        return 0.64
    return 0.78
