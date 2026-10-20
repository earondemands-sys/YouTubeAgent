#!/usr/bin/env python3
"""telugu_roman.py - Telugu script to the Roman "Tenglish" spelling people actually type.

    python3 scripts/telugu_roman.py "ఇప్పుడు actual topic లోకి వెళ్దాం"
    -> ippudu actual topic loki veldhaam

Casual spelling, not ISO 15919: త->th, ద->dh, ట->t, డ->d, long vowels doubled. Latin text (the English
tech terms Tenglish keeps in English) passes through untouched. It is a first pass for captions; the
editor agent fixes the words the creator spells differently.
"""
import sys

VOWELS = {"అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ee", "ఉ": "u", "ఊ": "oo", "ఋ": "ru", "ౠ": "ruu",
          "ఎ": "e", "ఏ": "e", "ఐ": "ai", "ఒ": "o", "ఓ": "o", "ఔ": "au"}
MATRAS = {"ా": "aa", "ి": "i", "ీ": "ee", "ు": "u", "ూ": "oo", "ృ": "ru", "ౄ": "ruu", "ె": "e", "ే": "e",
          "ై": "ai", "ొ": "o", "ో": "o", "ౌ": "au"}
CONSONANTS = {"క": "k", "ఖ": "kh", "గ": "g", "ఘ": "gh", "ఙ": "ng", "చ": "ch", "ఛ": "chh", "జ": "j", "ఝ": "jh",
              "ఞ": "ny", "ట": "t", "ఠ": "th", "డ": "d", "ఢ": "dh", "ణ": "n", "త": "th", "థ": "th", "ద": "dh",
              "ధ": "dh", "న": "n", "ప": "p", "ఫ": "ph", "బ": "b", "భ": "bh", "మ": "m", "య": "y", "ర": "r",
              "ఱ": "r", "ల": "l", "ళ": "l", "వ": "v", "శ": "sh", "ష": "sh", "స": "s", "హ": "h", "ౘ": "ts", "ౙ": "dz"}
VIRAMA, ANUSVARA, VISARGA, CHANDRA = "్", "ం", "ః", "ఁ"
DIGITS = {chr(0x0C66 + i): str(i) for i in range(10)}


def romanize(text):
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in CONSONANTS:
            # A doubled consonant (ద్ద, త్త) is written "ddh", "tth" - not "dhdh".
            if i >= 2 and text[i - 1] == VIRAMA and text[i - 2] == ch and len(CONSONANTS[ch]) > 1:
                out[-1] = CONSONANTS[ch][0]
            out.append(CONSONANTS[ch])
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt in MATRAS:
                out.append(MATRAS[nxt])
                i += 1
            elif nxt == VIRAMA:
                i += 1
            else:
                out.append("a")
        elif ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch == ANUSVARA:
            nxt = text[i + 1] if i + 1 < n else ""
            out.append("n" if nxt in CONSONANTS and CONSONANTS[nxt][0] not in "pbm" else "m")
        elif ch == VISARGA:
            out.append("h")
        elif ch in (CHANDRA, VIRAMA) or ch in MATRAS:
            pass  # stray marks: nothing to say out loud
        elif ch in DIGITS:
            out.append(DIGITS[ch])
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def has_telugu(text):
    return any("ఀ" <= c <= "౿" for c in text)


if __name__ == "__main__":
    print(romanize(" ".join(sys.argv[1:]) or sys.stdin.read()))
