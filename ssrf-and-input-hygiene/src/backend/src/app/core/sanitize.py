"""Allow-list HTML sanitizer for display-only survey content (no attributes except safe href; no scripts/styles/handlers)."""
import html
import re
from html.parser import HTMLParser

ALLOWED = {"b", "i", "u", "em", "strong", "p", "br", "ul", "ol", "li", "a", "span", "h3", "h4", "small"}
VOID = {"br"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "svg", "math", "template"}
SAFE_URL = re.compile(r"^(https?://|mailto:|/)[^\s\"'<>]*$", re.I)


class _S(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED:
            return
        if tag == "a":
            href = next((v for k, v in attrs if k == "href" and v), None)
            if href and SAFE_URL.match(href.strip()):
                self.out.append(f'<a href="{html.escape(href.strip(), quote=True)}" rel="noopener noreferrer nofollow" target="_blank">')
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED or tag in VOID:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))


def clean_html(s: str) -> str:
    p = _S()
    p.feed(s or "")
    p.close()
    return "".join(p.out)


def clean_definition(d):
    """Sanitise every `html` field (including localized dicts) of every element in a definition (returns a copy)."""
    import copy
    d = copy.deepcopy(d)

    def walk(els):
        for e in els:
            if isinstance(e, dict):
                if e.get("type") == "html" and "html" in e:
                    h = e["html"]
                    e["html"] = {k: clean_html(v) for k, v in h.items()} if isinstance(h, dict) else clean_html(h)
                if isinstance(e.get("elements"), list):
                    walk(e["elements"])
    for p in d.get("pages", []) if isinstance(d, dict) else []:
        if isinstance(p, dict) and isinstance(p.get("elements"), list):
            walk(p["elements"])
    return d
