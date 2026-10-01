"""Conservative, local quality gates for extracted educational text.

These checks find reasons to review or exclude a record.  They do not certify
source fidelity or mathematical correctness.  No checker repairs inferred text,
joins hyphenated words, or exposes text excerpts in its results.
"""

from __future__ import annotations

import ast
from collections import Counter
from fractions import Fraction
import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return a new string and an audit of newline/NFC normalization only.

    The caller must retain the original text separately.  Whitespace, spelling,
    punctuation, ligatures, math, and ambiguous line-end hyphens are preserved.
    Audit entries contain no original content, including possible secrets.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    corrections: list[dict[str, Any]] = []
    crlf_count = text.count("\r\n")
    cr_count = text.count("\r") - crlf_count
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if crlf_count or cr_count:
        corrections.append({"code": "NEWLINES_NORMALIZED", "crlf_count": crlf_count,
                            "cr_count": cr_count, "operation": "CRLF/CR to LF"})
    composed = unicodedata.normalize("NFC", normalized)
    if composed != normalized:
        corrections.append({"code": "UNICODE_NFC", "operation": "Unicode NFC",
                            "before_length": len(normalized), "after_length": len(composed)})
    return composed, corrections


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)"
               r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{16,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_.~+/-]{24,}=*"),
)
_MOJIBAKE = re.compile(r"(?:Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|â[€‚„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ]|ðŸ|ï¿½)")
_NUMERIC_OCR = re.compile(r"(?<![A-Za-z])(?:[0-9]+[OlI][0-9]*|[OlI][0-9]+)(?![A-Za-z])")
_LATEX_COMMAND = re.compile(r"\\(?:frac|sqrt|sum|int|prod|begin|end|alpha|beta|theta|sigma|pi|cdot|times)\b")
_MATH_HINT = re.compile(r"[=≈≤≥∑∫√]|\\[([]|\$|\\(?:frac|sqrt|sum|int|prod)\b")
_NUM_EQUALITY = re.compile(r"(?<![A-Za-z0-9_.])([\d.() +*/^−-]+)\s*=\s*([\d.() +*/^−-]+)(?![A-Za-z0-9_])")


def inspect_sensitive(text: str) -> list[str]:
    """Return classification codes only for content that must be left alone.

    Invoke before persisting extracted text. This intentionally errs toward
    exclusion when labeled financial or medical identifiers appear, including
    plausible synthetic examples. Generic academic uses of "account", "bank",
    "patient", or "password" alone are not sufficient. No match contents,
    offsets, identifiers, or snippets are returned.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    result: set[str] = set()
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        result.add("POSSIBLE_SECRET")
    credential_assignment = re.search(
        r"(?im)\b(?:password|passwd|pwd|passphrase)\s*[:=]\s*[\"']?[^\s\"']{3,}", text)
    if credential_assignment:
        result.add("LOGIN_CREDENTIALS")
    email = re.search(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if email and credential_assignment:
        result.add("EMAIL_AND_PASSWORD")
    if re.search(r"(?i)\b(?:routing(?:\s+(?:number|no\.?|#))?|aba(?:\s+(?:number|routing))?)\s*[:=#-]?\s*\d(?:[ -]?\d){8}\b", text):
        result.add("BANK_ROUTING_NUMBER")
    if re.search(r"(?i)\b(?:(?:bank|checking|savings)\s+(?:account\s*)?(?:number|no\.?|#)?|account\s+(?:number|no\.?|#)|acct\.?\s*(?:number|no\.?|#)?)\s*[:=#-]?\s*\d(?:[ -]?\d){5,19}\b", text):
        result.add("BANK_ACCOUNT_NUMBER")
    if re.search(r"(?i)\bIBAN\s*[:=#-]?\s*[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){10,30}\b", text):
        result.add("BANK_ACCOUNT_NUMBER")
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text) or re.search(
        r"(?i)\b(?:SSN|social\s+security(?:\s+(?:number|no\.?))?)\s*[:=#-]?\s*\d(?:[ -]?\d){8}\b", text):
        result.add("POSSIBLE_SSN")
    if re.search(r"(?i)\b(?:MRN|medical\s+record\s*(?:number|no\.?|#)|patient\s+(?:id|identifier|number|no\.?))\s*[:=#-]?\s*[A-Z0-9][A-Z0-9-]{3,}\b", text):
        result.add("MEDICAL_RECORD_IDENTIFIER")
    # A named/identified record together with patient-specific clinical fields
    # is sensitive even when the institutional MRN field is omitted.
    patient_identity = re.search(r"(?im)^\s*(?:patient\s+name|patient|name)\s*:\s*[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)+", text)
    clinical_field = re.search(r"(?im)^\s*(?:diagnosis|medications?|date\s+of\s+birth|DOB|treatment|chief\s+complaint)\s*:", text)
    if patient_identity and clinical_field:
        result.add("PERSONAL_MEDICAL_RECORD")
    return sorted(result)


def _numeric_value(expression: str) -> Fraction | None:
    """Evaluate only small arithmetic expressions, never names or function calls."""
    expression = expression.strip().replace("−", "-").replace("^", "**")
    if not expression or len(expression) > 160:
        return None
    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 80:
            return None

        def visit(node: ast.AST) -> Fraction:
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                # Use the lexical representation, not binary floating point.
                source = ast.get_source_segment(expression, node)
                if source is None or len(source) > 32:
                    raise ValueError
                result = Fraction(source)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                result = visit(node.operand)
                if isinstance(node.op, ast.USub):
                    result = -result
            elif isinstance(node, ast.BinOp):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Add):
                    result = left + right
                elif isinstance(node.op, ast.Sub):
                    result = left - right
                elif isinstance(node.op, ast.Mult):
                    result = left * right
                elif isinstance(node.op, ast.Div):
                    result = left / right
                elif isinstance(node.op, ast.Pow) and right.denominator == 1 and abs(right) <= 12:
                    result = left ** int(right)
                else:
                    raise ValueError
            else:
                raise ValueError
            if result.numerator.bit_length() > 1024 or result.denominator.bit_length() > 1024:
                raise ValueError
            return result

        return visit(tree.body)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
        return None


def _unbalanced_pairs(value: str) -> bool:
    """Check nesting, including mismatched pairs; skip escaped literal braces."""
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(value):
        if char in "{}" and index and value[index - 1] == "\\":
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return True
    return bool(stack)


def inspect_text(text: str, *, method: str = "native", context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect raw or cleaned text without claiming semantic verification.

    ``context`` optionally supports ``expected_problem``, ``expected_solution``,
    ``problem_complete``, ``solution_complete``, ``source_verified``,
    ``technical_verified``, ``ocr_confidence`` (0..1), and ``scope`` ("record",
    "document", or "page"). Verification flags must come from a separate source
    comparison/review process, not this detector. Default scope is "record".

    Output is JSON serializable. Checks contain sanitized location/count evidence
    only. ``critical`` and ``eligible_for_training`` enforce unresolved math,
    serious extraction defects, and secret exclusions. A heuristic pass remains
    ``review_required`` for training until fidelity and technical verification
    are supplied explicitly; text alone cannot establish either.
    """
    normalized, corrections = normalize_text(text)
    context = context if isinstance(context, dict) else {}
    checks: list[dict[str, Any]] = []
    lines = normalized.splitlines()
    math_lines = [(i + 1, line) for i, line in enumerate(lines) if _MATH_HINT.search(line) or _LATEX_COMMAND.search(line)]

    def add(code: str, category: str, severity: str, message: str,
            *, count: int = 1, line_numbers: list[int] | None = None) -> None:
        evidence: dict[str, Any] = {"count": count}
        if line_numbers:
            evidence["line_numbers"] = sorted(set(line_numbers))[:30]
        checks.append({"code": code, "category": category, "severity": severity,
                       "message": message, "evidence": evidence})

    def positions(pattern: re.Pattern[str]) -> list[int]:
        return [normalized.count("\n", 0, match.start()) + 1 for match in pattern.finditer(normalized)]

    if not normalized.strip():
        add("EMPTY_TEXT", "extraction_fidelity", "critical", "No usable extracted text.")
    placeholders = positions(re.compile(r'\[(?:pic(?:ture)?|image|diagram|figure)\s+(?:goes|insert|here)|\b(?:insert|missing)\s+(?:diagram|image|figure)\b', re.I))
    if placeholders:
        add('SOURCE_VISUAL_PLACEHOLDER', 'training_suitability', 'critical', 'Source refers to a missing visual placeholder; the dependency must be restored or verified unnecessary.', count=len(placeholders), line_numbers=placeholders)
    replacements = normalized.count("\ufffd")
    if replacements:
        add("REPLACEMENT_CHARACTERS", "extraction_fidelity", "critical",
            "Unicode replacement characters indicate lost source content.", count=replacements)
    mojibake_lines = positions(_MOJIBAKE)
    if mojibake_lines:
        add("MOJIBAKE", "extraction_fidelity", "critical",
            "Likely broken character decoding; compare with the source before repair.",
            count=len(mojibake_lines), line_numbers=mojibake_lines)
    private_count = sum(unicodedata.category(char) == "Co" for char in normalized)
    if private_count:
        add("PRIVATE_USE_GLYPHS", "extraction_fidelity", "critical",
            "Font-specific private-use characters may conceal missing letters or math.", count=private_count)
    control_count = sum(unicodedata.category(char) == "Cc" and char not in "\n\t\f" for char in normalized)
    if control_count:
        add("CONTROL_CHARACTERS", "extraction_fidelity", "major",
            "Unexpected control characters remain in extracted text.", count=control_count)
    format_count = sum(char in "\u200b\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069" for char in normalized)
    if format_count:
        add("INVISIBLE_FORMATTING", "extraction_fidelity", "major",
            "Invisible spacing or direction controls require source comparison.", count=format_count)
    for sensitive_code in inspect_sensitive(normalized):
        add(sensitive_code, "training_suitability", "critical",
            "Potential credentials or sensitive personal records detected; exclude without logging contents.")

    hyphen_lines = positions(re.compile(r"[^\W\d_]\-\n\s*[^\W\d_]", re.UNICODE))
    soft_hyphens = normalized.count("\u00ad")
    if hyphen_lines or soft_hyphens:
        add("AMBIGUOUS_HYPHENATION", "extraction_fidelity", "major",
            "Line-end or soft hyphens may split words; preserve them until source review.",
            count=len(hyphen_lines) + soft_hyphens, line_numbers=hyphen_lines)
    spaced_lines = positions(re.compile(r"(?<!\w)(?:[A-Za-z] ){4,}[A-Za-z](?!\w)"))
    if spaced_lines:
        add("SPACED_LETTER_FRAGMENTS", "extraction_fidelity", "major",
            "Runs of separated letters may be chopped words or layout damage.",
            count=len(spaced_lines), line_numbers=spaced_lines)
    nonempty_lines = [(i + 1, line.strip()) for i, line in enumerate(lines) if line.strip()]
    short_lines = [number for number, line in nonempty_lines if len(line) <= 3]
    if len(nonempty_lines) >= 8 and len(short_lines) / len(nonempty_lines) > 0.45:
        add("FRAGMENTED_LINES", "extraction_fidelity", "major",
            "Many very short lines may indicate broken reading order or chopped text.",
            count=len(short_lines), line_numbers=short_lines)
    repeated_lines = [(i + 1) for i, line in enumerate(lines) if re.search(r"([^\w\s])\1{5,}", line)]
    if repeated_lines:
        add("GARBLED_SYMBOL_RUN", "extraction_fidelity", "major",
            "Long repeated symbol runs may be OCR or extraction damage.",
            count=len(repeated_lines), line_numbers=repeated_lines)
    words = re.findall(r"\b[A-Za-z]{5,}\b", normalized)
    malformed_words = [word for word in words if re.search(r"(.)\1{4,}", word, re.I)]
    if malformed_words:
        add("GARBLED_WORDS", "extraction_fidelity", "major",
            "Implausible repeated letters require comparison with the source.", count=len(malformed_words))
    question_numbers = [(i + 1, int(match.group(1))) for i, line in enumerate(lines)
                        if (match := re.match(r"\s*(?:Question\s+|Problem\s+)(\d{1,5})\b", line, re.I))]
    backward = [right[0] for left, right in zip(question_numbers, question_numbers[1:]) if right[1] < left[1]]
    if backward:
        add("READING_ORDER_HINT", "extraction_fidelity", "major",
            "Question numbering moves backwards; confirm page and column reading order.",
            count=len(backward), line_numbers=backward)

    # TeX delimiters are checked globally because a formula can span lines.
    delimiter_text = re.sub(r"\\\$", "", normalized)
    display_count = len(re.findall(r"\$\$", delimiter_text))
    single_text = delimiter_text.replace("$$", "")
    single_count = single_text.count("$")
    # A sole monetary dollar amount is not treated as TeX.
    monetary_only = bool(re.fullmatch(r"[^$]*\$\d[\d,.]*(?:\s+[^$]*)?", single_text))
    if display_count % 2 or (single_count % 2 and not monetary_only):
        add("UNBALANCED_MATH_DELIMITERS", "technical_correctness", "critical",
            "Unpaired TeX dollar delimiters leave a formula boundary unresolved.")
    for opening, closing in ((r"\(", r"\)"), (r"\[", r"\]")):
        tokens = re.findall(re.escape(opening) + "|" + re.escape(closing), normalized)
        depth = 0
        bad = False
        for token in tokens:
            depth += 1 if token == opening else -1
            bad = bad or depth < 0 or depth > 1
        if depth or bad:
            add("UNBALANCED_MATH_DELIMITERS", "technical_correctness", "critical",
                "Unpaired or incorrectly nested TeX math delimiters need source review.")
    environments = re.findall(r"\\(begin|end)\{([^{}]+)\}", normalized)
    env_stack: list[str] = []
    env_bad = False
    for direction, name in environments:
        if direction == "begin":
            env_stack.append(name)
        elif not env_stack or env_stack.pop() != name:
            env_bad = True
    if env_stack or env_bad:
        add("UNBALANCED_LATEX_ENVIRONMENT", "technical_correctness", "critical",
            "LaTeX environments are incomplete or incorrectly nested.")
    # A whole record can legitimately contain multiline math; do not check each
    # line independently, which would falsely reject an ordinary multiline frac.
    if math_lines and _unbalanced_pairs(normalized):
        add("UNBALANCED_MATH_BRACKETS", "technical_correctness", "critical",
            "Unbalanced or mismatched brackets leave mathematical structure unresolved.")
    suspect_numbers = [(number, len(list(_NUMERIC_OCR.finditer(line)))) for number, line in math_lines]
    suspect_numbers = [(number, count) for number, count in suspect_numbers if count]
    if suspect_numbers:
        add("OCR_NUMERIC_CONFUSION", "technical_correctness", "critical",
            "Adjacent letters and digits may confuse O/0, I/1, or l/1 in a formula; no substitution was made.",
            count=sum(count for _, count in suspect_numbers), line_numbers=[number for number, _ in suspect_numbers])
    incomplete_math_lines = [number for number, line in math_lines
                             if re.search(r"(?:[=+*/^−-]|\\(?:frac|sqrt|cdot|times))\s*$", line.strip())]
    # Operators at a line break can be intentional. They still require source
    # comparison before a fragment becomes an independent training record.
    if incomplete_math_lines:
        add("INCOMPLETE_MATH", "technical_correctness", "critical",
            "A formula ends with an operator or incomplete command; resolve its continuation.",
            count=len(incomplete_math_lines), line_numbers=incomplete_math_lines)
    empty_arg_lines = [number for number, line in math_lines
                       if re.search(r"\\(?:frac|sqrt)\s*\{\s*\}|\\frac\s*\{[^{}]*\}\s*\{\s*\}|(?:\^|_)\s*\{\s*\}", line)]
    if empty_arg_lines:
        add("EMPTY_MATH_ARGUMENT", "technical_correctness", "critical",
            "A formula contains an empty required argument or exponent.",
            count=len(empty_arg_lines), line_numbers=empty_arg_lines)
    broken_unit_lines = [i + 1 for i, line in enumerate(lines)
                         if re.search(r"\b(?:m|cm|mm|km|s|kg|N|J|Pa|W|Hz|V|A)\s*[\^_]\s*(?:$|[.,;])", line)]
    if broken_unit_lines:
        add("BROKEN_UNIT_EXPONENT", "technical_correctness", "critical",
            "A physical unit has a missing exponent; do not infer the intended dimension.",
            count=len(broken_unit_lines), line_numbers=broken_unit_lines)

    arithmetic_count = 0
    mismatch_lines: list[int] = []
    for number, line in math_lines:
        for match in _NUM_EQUALITY.finditer(line):
            left, right = (_numeric_value(part) for part in match.groups())
            if left is not None and right is not None:
                arithmetic_count += 1
                if left != right:
                    # Printed decimal answers may be rounded. Only flag a
                    # discrepancy larger than half a unit in the final place.
                    decimal_answer = re.fullmatch(r"[+-]?\d*\.(\d+)", match.group(2).strip())
                    tolerance = Fraction(1, 2 * 10 ** len(decimal_answer.group(1))) if decimal_answer else Fraction(0)
                    if abs(left - right) > tolerance:
                        mismatch_lines.append(number)
    if mismatch_lines:
        add("NUMERIC_EQUALITY_MISMATCH", "technical_correctness", "critical",
            "A simple numeric equality does not agree within its printed precision; verify source and solution.",
            count=len(mismatch_lines), line_numbers=mismatch_lines)

    has_problem = bool(re.search(r"(?im)^\s*(?:problem|question|exercise)\b", normalized))
    has_solution = bool(re.search(r"(?im)^\s*(?:solution|answer|worked solution)\b", normalized))
    if context.get("expected_problem") and not has_problem and context.get("problem_complete") is not True:
        add("PROBLEM_NOT_ESTABLISHED", "training_suitability", "major",
            "An expected problem statement has not been established; review record boundaries.")
    if context.get("expected_solution") and not has_solution and context.get("solution_complete") is not True:
        add("SOLUTION_NOT_ESTABLISHED", "training_suitability", "major",
            "An expected solution has not been established; review record boundaries.")
    for field, code in (("problem_complete", "INCOMPLETE_PROBLEM"), ("solution_complete", "INCOMPLETE_SOLUTION")):
        if context.get(field) is False:
            add(code, "training_suitability", "critical", "Context identifies an incomplete educational record.")
    if context.get("scope", "record") == "record" and re.search(r"(?i)\b(?:and|or|because|therefore|where|given|such that|equals)\s*$", normalized.strip()):
        add("TRUNCATED_SENTENCE_HINT", "extraction_fidelity", "major",
            "The record ends with a likely incomplete sentence; confirm the source boundary.")
    heading_only = re.search(r"(?im)^\s*(?:problem|question|exercise|solution|answer)\s*(?:\d+)?\s*[:.]?\s*$", normalized.rstrip().split("\n")[-1] if normalized else "")
    if heading_only:
        add("EMPTY_EDUCATIONAL_SECTION", "training_suitability", "critical",
            "A final problem or solution heading has no following content.")
    confidence = context.get("ocr_confidence")
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1 and confidence < 0.90:
        add("LOW_OCR_CONFIDENCE", "extraction_fidelity", "major",
            "Reported OCR confidence is below the conservative review threshold.")

    critical = any(check["severity"] == "critical" for check in checks)
    extraction_checks = [check for check in checks if check["category"] == "extraction_fidelity"]
    technical_checks = [check for check in checks if check["category"] == "technical_correctness"]

    def status(group: list[dict[str, Any]], verified: bool) -> str:
        if any(check["severity"] == "critical" for check in group):
            return "fail"
        if group:
            return "review_required"
        return "verified" if verified else "unverified"

    statuses = {
        "extraction_fidelity": status(extraction_checks, context.get("source_verified") is True),
        "technical_correctness": status(technical_checks, context.get("technical_verified") is True),
    }
    verified = all(value == "verified" for value in statuses.values())
    statuses["training_suitability"] = "exclude" if critical else ("eligible" if verified and not checks else "review_required")
    return {
        "schema_version": "1.0",
        "method": str(method),
        "checks": checks,
        "critical": critical,
        "statuses": statuses,
        "eligible_for_training": statuses["training_suitability"] == "eligible",
        "metrics": {"characters": len(normalized), "non_whitespace_characters": sum(not c.isspace() for c in normalized),
                    "lines": len(lines), "words": len(re.findall(r"\S+", normalized)),
                    "math_lines": len(math_lines), "numeric_equalities_checked": arithmetic_count,
                    "check_counts": dict(Counter(check["severity"] for check in checks))},
        "normalization": corrections,
    }
