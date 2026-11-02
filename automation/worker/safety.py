"""What on a page means "stop". Looked at on every navigation, before anything else. Insisting after a warning is what
loses an account, so nothing here tries to get past it: the worker stops and calls you."""
import re
from typing import Optional
from urllib.parse import urlparse

LINKEDIN_CHECKPOINT = re.compile(r"/checkpoint/|/challenge/|/security-verification", re.I)
LINKEDIN_LOGGED_OUT = re.compile(r"^/(login|uas/login|authwall|signup|m/login)", re.I)
RESTRICTED = re.compile(r"your account (has been|is|was) (temporarily )?restricted|we['’]ve (temporarily )?restricted your account|"
                        r"sua conta (foi|est[aá]) (temporariamente )?restringida|restringimos (temporariamente )?sua conta", re.I)
SECURITY_CHECK = re.compile(r"let['’]s do a quick security check|quick security check|verifica[cç][aã]o (r[aá]pida )?de seguran[cç]a|"
                            r"verify you['’]?re (not a robot|a human)|confirme que voc[eê] n[aã]o [eé] um rob[oô]", re.I)
RATE_LIMITED = re.compile(r"too many requests|you['’]ve reached the (daily|weekly) limit|muitas solicita[cç][oõ]es", re.I)

CAPTCHA_SITE = re.compile(r"complete the captcha|i['’]m not a robot|n[aã]o sou um rob[oô]|verify you are human", re.I)
ACCOUNT_SITE = re.compile(r"create (an |your )?account (to|and) apply|sign in to apply|log in to apply|fa[cç]a login para se candidatar|"
                          r"crie (uma |sua )?conta para se candidatar|sign in with linkedin|entrar com o linkedin", re.I)
EMAIL_SITE = re.compile(r"verify your email|confirme seu e-?mail|enter the code we sent|digite o c[oó]digo que enviamos", re.I)
# Only the top of a page counts: an ad or a post may mention these words in its own text
HEAD_CHARS = 1500


def is_linkedin(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def classify(url: str, title: str = "", text: str = "", http_status: Optional[int] = None) -> Optional[str]:
    """The code that stops this action (and, for LinkedIn, the lane), or None when the page may go on."""
    head = f"{title}\n{(text or '')[:HEAD_CHARS]}"
    if is_linkedin(url):
        path = urlparse(url).path
        if LINKEDIN_CHECKPOINT.search(path):
            return "checkpoint"
        if LINKEDIN_LOGGED_OUT.search(path):
            return "session_expired"
        if http_status in (429, 999):
            return "rate_limited"
        if RESTRICTED.search(head):
            return "restriction_notice"
        if SECURITY_CHECK.search(head):
            return "checkpoint"
        if RATE_LIMITED.search(head):
            return "rate_limited"
        return None
    if http_status == 429:
        return "rate_limited"
    if CAPTCHA_SITE.search(head):
        return "captcha"
    if EMAIL_SITE.search(head):
        return "email_verification"
    if ACCOUNT_SITE.search(head):
        return "account_required"
    return None


def has_captcha_frame(frame_urls: list) -> bool:
    """A challenge widget on a company site. Invisible badges are common and allowed through to the form; the worker only
    uses this to tell you, when a form could not be finished."""
    return any(re.search(r"recaptcha/api2/bframe|hcaptcha\.com/.*checkbox|challenges\.cloudflare\.com", u or "") for u in frame_urls)
