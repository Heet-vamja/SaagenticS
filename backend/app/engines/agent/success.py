"""Independent final-page checks. Missing evidence stays inconclusive."""

import re
from urllib.parse import urlsplit

from app.engines.agent.contracts import SuccessCheck
from app.engines.agent.privacy import public_url, redact


async def collect_evidence(page) -> dict:
    """Read rendered public DOM, never input values or unrestricted HTML.

    The local text is reduced to task-specific facts before persistence/inference.
    Email addresses and telephone numbers are represented by counts only.
    """
    data = await page.evaluate(r"""() => {
      const visible=e=>{const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
        return !!(r.width && r.height && s.visibility!=='hidden' && s.display!=='none');};
      const walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const parts=[]; let node, length=0;
      while ((node=walker.nextNode()) && length<30000) {
        const p=node.parentElement;
        if (p && !p.closest('input,textarea,select,[contenteditable],script,style') && visible(p)) {
          parts.push(node.textContent); length+=node.textContent.length;
        }
      }
      const text=parts.join(' ').slice(0,30000);
      const headings=[...document.querySelectorAll('h1,h2')].filter(visible).slice(0,10).map(e=>e.innerText).join(' ').slice(0,1000);
      const forms=[...document.querySelectorAll('form,[role=form]')].filter(visible).slice(0,10).map(f=>({
        fields:[...f.querySelectorAll('input,textarea,select')].filter(e=>visible(e) && !['hidden','submit','button','file','search'].includes(e.type)).slice(0,30).map(e=>({
          type:e.type || e.tagName.toLowerCase(), required:!!e.required,
          label:(e.getAttribute('aria-label') || (e.labels?[...e.labels].map(l=>{const c=l.cloneNode(true);c.querySelectorAll('input,textarea,select,[contenteditable]').forEach(e=>e.remove());return c.textContent;}).join(' '):'') || e.getAttribute('placeholder') || '').slice(0,80)
        }))
      }));
      const methods=[...document.querySelectorAll('a[href]')].filter(visible).map(e=>e.getAttribute('href'));
      return {title:document.title, headings, text, forms,
        public_address_count:[...document.querySelectorAll('address')].filter(e=>visible(e) && /[a-z]/i.test(e.innerText) && /\d/.test(e.innerText)).length,
        email_links:methods.filter(h=>/^mailto:/i.test(h)).length,
        phone_links:methods.filter(h=>/^tel:/i.test(h)).length};
    }""")
    text = data["text"]
    prices = re.findall(
        r"(?:[$€£₹]\s?\d[\d,.]*(?:\s*(?:/|per)\s*(?:mo(?:nth)?|year|user|seat))?|\b\d[\d,.]*\s?(?:USD|EUR|GBP|INR)\b)",
        text,
        re.IGNORECASE,
    )
    headings = " ".join([data["title"], urlsplit(page.url).path, data["headings"]])
    return {
        "url": public_url(page.url),
        "title": redact(data["title"], 200),
        "pricing_context": bool(
            re.search(r"pric(?:ing|es?)|plans?|subscription", headings, re.IGNORECASE)
        ),
        "prices": list(dict.fromkeys(prices))[:15],
        "contact_context": bool(
            re.search(r"contact|reach us|get in touch", headings, re.IGNORECASE)
        ),
        "public_email_count": data["email_links"]
        + len(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)),
        "public_address_count": data["public_address_count"],
        "public_phone_count": data["phone_links"]
        + len(re.findall(r"(?<!\w)\+\d[\d ()-]{7,}\d", text)),
        "signup_context": bool(
            re.search(
                r"sign.?up|register|registration|free trial|start.{0,15}trial|book.{0,15}demo|join",
                headings,
                re.IGNORECASE,
            )
        ),
        "documentation_context": bool(
            re.search(
                r"documentation|developer|api reference|getting started", headings, re.IGNORECASE
            )
        ),
        "documentation_content": bool(
            re.search(r"sdk|install|api reference|tutorial|integration", text, re.IGNORECASE)
        ),
        "forms": [
            {"fields": [dict(f, label=redact(f["label"], 80)) for f in form["fields"]]}
            for form in data["forms"]
        ],
        "challenge": bool(
            re.search(
                r"verify you are human|captcha|access denied|checking your browser",
                text[:10000],
                re.IGNORECASE,
            )
        ),
        "not_found": bool(
            re.search(r"^(?:404|page not found|not found)\b", data["title"], re.IGNORECASE)
        ),
        "requires_js": bool(
            re.search(r"enable javascript|javascript is required", text, re.IGNORECASE)
        ),
    }


def check_success(task_type: str | None, evidence: dict) -> SuccessCheck:
    if evidence.get("challenge"):
        return SuccessCheck(
            success=False,
            reason="An access challenge blocked inspection.",
            evidence=evidence,
            failure_category="blocked_by_captcha_or_bot_protection",
        )
    if evidence.get("not_found"):
        return SuccessCheck(
            success=False,
            reason="The final page reports that it does not exist.",
            evidence=evidence,
            failure_category="element_not_found",
        )
    if evidence.get("requires_js"):
        return SuccessCheck(
            success=None,
            reason="The page requests JavaScript and rendered evidence is insufficient.",
            evidence=evidence,
            failure_category="content_requires_js",
        )
    confirmed = {
        "FIND_PRICING": evidence.get("pricing_context") and bool(evidence.get("prices")),
        "FIND_CONTACT": bool(
            evidence.get("public_email_count")
            or evidence.get("public_phone_count")
            or evidence.get("public_address_count")
        )
        or (
            evidence.get("contact_context")
            and any(f.get("fields") for f in evidence.get("forms", []))
        ),
        "FIND_SIGNUP_FORM": evidence.get("signup_context")
        and any(f.get("fields") for f in evidence.get("forms", [])),
        "FIND_DOCUMENTATION": evidence.get("documentation_context")
        and evidence.get("documentation_content"),
    }.get(task_type, False)
    if confirmed:
        return SuccessCheck(
            success=True,
            reason="The rendered final page contains the requested public evidence.",
            evidence=evidence,
        )
    return SuccessCheck(
        success=None,
        reason="The final page does not provide enough evidence to verify this task.",
        evidence=evidence,
    )
