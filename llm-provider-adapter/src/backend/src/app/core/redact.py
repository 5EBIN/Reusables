"""Personal identifiers removed from a text before it is sent to a model provider: email addresses, phone numbers (UAE and international), Emirates ID numbers,
card-like digit runs and IBANs become placeholders ([email], [phone], [id], [card], [iban]). The product does not need the originals to label, group or summarise
an answer, so nothing is mapped back; where a screen shows the original text it comes from the database, not from the model.

Arabic-Indic (٠-٩) and Eastern Arabic-Indic (۰-۹) digits count as digits. Ordinary numbers (ratings, dates, ticket numbers, amounts) are left alone: a phone number
needs a + or 00 country prefix or a UAE shape, and a card needs 13-19 digits."""
import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?!\w)")
_IBAN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{2}(?:[ -]?[A-Za-z0-9]{4}){2,7}(?:[ -]?[A-Za-z0-9]{1,3})?(?![A-Za-z0-9])")
_EID = re.compile(r"(?<!\d)784[ -]?\d{4}[ -]?\d{7}[ -]?\d(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_PHONE_INTL = re.compile(r"(?<![\w+])(?:\+|00)[ -]?\d(?:[ -]?\(?\d\)?){7,13}\d(?!\d)")
_PHONE_UAE = re.compile(r"(?<!\d)(?:0(?:5[024568]|[2-4679])|971[ -]?(?:5[024568]|[2-4679]))[ -]?\d{3}[ -]?\d{4}(?!\d)")

# Order matters: the longest, most specific shapes first, so an Emirates ID is not mistaken for a phone number and a number with a + or 00 prefix is a phone, not a card.
_RULES = [(_EMAIL, "[email]"), (_IBAN, "[iban]"), (_EID, "[id]"), (_PHONE_INTL, "[phone]"), (_CARD, "[card]"), (_PHONE_UAE, "[phone]")]


def redact(text: str) -> str:
    """The text with identifiers replaced. Matching runs on a copy with the digits normalised one character for one, so positions line up with the original."""
    for rx, label in _RULES:
        view = text.translate(_DIGITS)
        out, last = [], 0
        for m in rx.finditer(view):
            out.append(text[last:m.start()])
            out.append(label)
            last = m.end()
        out.append(text[last:])
        text = "".join(out)
    return text
