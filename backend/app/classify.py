"""First-pass classification of a notification title. Unknown => 'other'. Admins can correct it."""
import re
RULES = [
    ("other", r"\btender|quotation|auction|e-?procurement|\brfp\b|\beoi\b"),
    ("admit_card", r"admit card|hall ticket|call letter|e-?admit"),
    ("answer_key", r"answer key|response sheet"),
    ("cutoff", r"cut-?off"),
    ("merit_list", r"merit list"),
    ("final_selection", r"final (result|selection|list)|appointment list"),
    ("waiting_list", r"waiting list|wait list"),
    ("document_verification", r"document verification|\bdv (list|schedule)"),
    ("interview", r"interview"),
    ("result", r"result|scorecard"),
    ("cancellation", r"cancel"),
    ("postponement", r"postpone|reschedul"),
    ("extension", r"extend|extension"),
    ("exam_date", r"exam (date|schedule|calendar)|schedule of|examination (date|schedule)"),
    ("vacancy_revision", r"revised vacanc|vacancy revis"),
    ("corrigendum", r"corrigendum|addendum|amendment"),
    ("recruitment", r"recruitment|vacanc|advertisement|advt|apply online|walk-?in|engagement of|invites? application"),
]
def classify(title: str) -> str:
    t = title.lower()
    for typ, pat in RULES:
        if re.search(pat, t):
            return typ
    return "other"
