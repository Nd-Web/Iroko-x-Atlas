"""
services/regulatory_returns/templates.py

Excel input templates for returns that need bulk data (the monthly prudential
pack and CTRs), and strict parsers for the completed files. Parsers key on line
codes and header names, never on positions, and report problems by sheet/row so
the user can fix the file in one pass.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from .prudential import BORROWER_TYPES, PL_LINES, SFP_LINES, SIGNED_LINES, Loan

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_HEAD = Font(bold=True, color="FFFFFF")
_HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
_NOTE = Font(italic=True, color="555555")

LOAN_HEADERS = (
    "Borrower ID", "Borrower name", "Borrower type", "Insider (Y/N)", "Insider relationship",
    "Facility ID", "Outstanding balance (NGN)", "Days past due", "Sector", "Restructured (Y/N)",
)
TXN_HEADERS = (
    "Transaction date", "Customer name", "Customer type", "Account number", "BVN / RC number",
    "Transaction type", "Amount (NGN)", "Narration", "Branch", "Channel / teller",
)
CTR_THRESHOLDS = {"Individual": 5_000_000.0, "Body corporate": 10_000_000.0}


class TemplateError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems[:5]))
        self.problems = problems


def _header(ws, headers: tuple[str, ...], widths: tuple[int, ...]) -> None:
    ws.append(list(headers))
    for i, cell in enumerate(ws[ws.max_row], start=1):
        cell.font, cell.fill = _HEAD, _HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[cell.column_letter].width = widths[i - 1] if i - 1 < len(widths) else 18
    ws.freeze_panes = ws.cell(row=ws.max_row + 1, column=1)


def _instructions(wb: Workbook, title: str, lines: list[str]) -> None:
    ws = wb.active
    ws.title = "Instructions"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    for i, line in enumerate(lines, start=3):
        ws.cell(row=i, column=1, value=line).alignment = Alignment(wrap_text=True)
    ws.column_dimensions["A"].width = 120


def _to_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def prudential_template() -> bytes:
    wb = Workbook()
    _instructions(wb, "Iroko AI — Monthly prudential returns input", [
        "1. Fill the SFP and PL sheets with balances from your trial balance at month end. Enter amounts in naira, without the ₦ sign.",
        "2. Keep the codes in column A unchanged; Iroko reads figures by code. Leave a line blank or 0 if it does not apply.",
        "3. PL is cumulative for the financial year to date (MMFBR 1000), not the current month alone.",
        "4. A08 (impairment allowance) is entered as a positive number; Iroko deducts it from gross loans.",
        "5. A04 covers placements maturing within 90 days only; report longer placements in A06 so the liquidity ratio is not overstated.",
        "6. E05 may be negative for accumulated losses.",
        "7. LoanBook: one row per facility. Use the same Borrower ID for every facility of one borrower so exposures aggregate correctly.",
        "   Borrower type must be Individual, Group, Cooperative or Corporate. Insider = Y for directors, staff, shareholders and their related parties.",
        "8. The loan book total should equal A07 (gross loans); Iroko flags any difference.",
    ])
    for name, lines in (("SFP", SFP_LINES), ("PL", PL_LINES)):
        ws = wb.create_sheet(name)
        _header(ws, ("Code", "Line item", "Amount (NGN)"), (8, 80, 22))
        for code, label, _ in lines:
            ws.append([code, label, None])
            ws.cell(row=ws.max_row, column=3).number_format = "#,##0.00"
    ws = wb.create_sheet("LoanBook")
    _header(ws, LOAN_HEADERS, (16, 32, 16, 12, 24, 16, 22, 14, 18, 14))
    dv_type = DataValidation(type="list", formula1=f'"{",".join(BORROWER_TYPES)}"', allow_blank=True)
    dv_yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    ws.add_data_validation(dv_type)
    ws.add_data_validation(dv_yn)
    dv_type.add("C2:C20000")
    dv_yn.add("D2:D20000")
    dv_yn.add("J2:J20000")
    for col in ("G",):
        for r in range(2, 2001):
            ws[f"{col}{r}"].number_format = "#,##0.00"
    return _to_bytes(wb)


def ctr_template() -> bytes:
    wb = Workbook()
    _instructions(wb, "Iroko AI — Currency transaction report input", [
        "1. Export the period's transactions from your core banking system into the Transactions sheet (one row per transaction).",
        "2. Customer type must be Individual or Body corporate.",
        "3. Iroko selects single transactions in excess of ₦5,000,000 (individual) or ₦10,000,000 (body corporate) — MLPPA 2022 s.11(1).",
        "4. Dates as YYYY-MM-DD or Excel dates. Amounts in naira without the ₦ sign.",
    ])
    ws = wb.create_sheet("Transactions")
    _header(ws, TXN_HEADERS, (14, 32, 16, 16, 18, 20, 18, 40, 18, 18))
    dv = DataValidation(type="list", formula1='"Individual,Body corporate"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("C2:C50000")
    return _to_bytes(wb)


TEMPLATES = {"prudential": prudential_template, "ctr": ctr_template}

# ─── Parsing ──────────────────────────────────────────────────────────────────


def _num(value, where: str, problems: list[str], allow_negative: bool = False) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0.0
    if isinstance(value, (int, float)):
        n = float(value)
    else:
        text = str(value).strip().replace(",", "").replace("₦", "").replace("NGN", "").strip()
        neg = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        try:
            n = -float(text) if neg else float(text)
        except ValueError:
            problems.append(f"{where}: '{value}' is not a number.")
            return 0.0
    if n < 0 and not allow_negative:
        problems.append(f"{where}: negative amount {n:,.2f} is not allowed on this line.")
    return n


def _yn(value) -> bool:
    return str(value or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _date(value, where: str, problems: list[str]) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        problems.append(f"{where}: date is missing.")
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    problems.append(f"{where}: '{text}' is not a date (use YYYY-MM-DD).")
    return None


def _open(data: bytes):
    if not data:
        raise TemplateError(["The uploaded file is empty."])
    if len(data) > MAX_UPLOAD_BYTES:
        raise TemplateError(["The uploaded file exceeds the 10 MB limit."])
    try:
        return load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception:
        raise TemplateError(["The file is not a readable .xlsx workbook. Download the Iroko template and fill it in."])


def _header_map(rows: list[tuple], expected: tuple[str, ...], sheet: str) -> tuple[int, dict[str, int]]:
    norm = lambda s: " ".join(str(s or "").strip().lower().split())  # noqa: E731
    wanted = {norm(h): h for h in expected}
    for idx, row in enumerate(rows[:10]):
        cols = {wanted[norm(c)]: i for i, c in enumerate(row) if norm(c) in wanted}
        if len(cols) >= max(3, len(expected) // 2):
            missing = [h for h in expected if h not in cols]
            if missing:
                raise TemplateError([f"{sheet}: missing column(s) {', '.join(missing)}."])
            return idx, cols
    raise TemplateError([f"{sheet}: header row not found — use the Iroko template."])


@dataclass
class PrudentialUpload:
    sfp: dict[str, float]
    pl: dict[str, float]
    loans: list[Loan]
    problems: list[str] = field(default_factory=list)


def parse_prudential(data: bytes) -> PrudentialUpload:
    wb = _open(data)
    problems: list[str] = []
    sheets = {ws.title.strip().lower(): ws for ws in wb.worksheets}
    values: dict[str, dict[str, float]] = {}
    for name, lines in (("sfp", SFP_LINES), ("pl", PL_LINES)):
        ws = sheets.get(name)
        if ws is None:
            raise TemplateError([f"Sheet '{name.upper()}' is missing — use the Iroko template."])
        codes = {c for c, _, _ in lines}
        found: dict[str, float] = {}
        for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
            code = str(row[0] or "").strip().upper() if row else ""
            if code in codes:
                amount = row[2] if len(row) > 2 else None
                found[code] = _num(amount, f"{name.upper()} row {r} ({code})", problems, allow_negative=code in SIGNED_LINES)
        absent = sorted(codes - set(found))
        if absent:
            problems.append(f"{name.upper()}: line code(s) {', '.join(absent)} not found — keep column A unchanged.")
        values[name] = found

    loans: list[Loan] = []
    ws = sheets.get("loanbook")
    if ws is not None:
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            hdr_idx, cols = _header_map(rows, LOAN_HEADERS, "LoanBook")
            for offset, row in enumerate(rows[hdr_idx + 1:], start=hdr_idx + 2):
                get = lambda h: row[cols[h]] if cols[h] < len(row) else None  # noqa: E731
                if all(v in (None, "") for v in row):
                    continue
                where = f"LoanBook row {offset}"
                btype = str(get("Borrower type") or "").strip().title()
                if btype == "Co-Operative":
                    btype = "Cooperative"
                if btype not in BORROWER_TYPES:
                    problems.append(f"{where}: borrower type '{get('Borrower type')}' must be one of {', '.join(BORROWER_TYPES)}.")
                    btype = "Individual"
                dpd_raw = get("Days past due")
                dpd = int(_num(dpd_raw, f"{where} days past due", problems))
                name = str(get("Borrower name") or "").strip()
                if not name:
                    problems.append(f"{where}: borrower name is missing.")
                loans.append(Loan(
                    borrower_id=str(get("Borrower ID") or "").strip(),
                    borrower_name=name,
                    borrower_type=btype,
                    insider=_yn(get("Insider (Y/N)")),
                    insider_relationship=str(get("Insider relationship") or "").strip(),
                    facility_id=str(get("Facility ID") or "").strip(),
                    outstanding=_num(get("Outstanding balance (NGN)"), f"{where} outstanding", problems),
                    days_past_due=max(dpd, 0),
                    sector=str(get("Sector") or "").strip(),
                    restructured=_yn(get("Restructured (Y/N)")),
                    row=offset,
                ))
    return PrudentialUpload(values["sfp"], values["pl"], loans, problems)


@dataclass
class Txn:
    date: date
    customer_name: str
    customer_type: str
    account_number: str
    bvn_or_rc: str
    transaction_type: str
    amount: float
    narration: str
    branch: str
    channel: str
    row: int


def parse_transactions(data: bytes) -> tuple[list[Txn], list[str]]:
    wb = _open(data)
    problems: list[str] = []
    ws = next((w for w in wb.worksheets if w.title.strip().lower() == "transactions"), None)
    if ws is None:
        raise TemplateError(["Sheet 'Transactions' is missing — use the Iroko template."])
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise TemplateError(["The Transactions sheet is empty."])
    hdr_idx, cols = _header_map(rows, TXN_HEADERS, "Transactions")
    out: list[Txn] = []
    for offset, row in enumerate(rows[hdr_idx + 1:], start=hdr_idx + 2):
        if all(v in (None, "") for v in row):
            continue
        get = lambda h: row[cols[h]] if cols[h] < len(row) else None  # noqa: E731
        where = f"Transactions row {offset}"
        ctype = str(get("Customer type") or "").strip()
        ctype = {"individual": "Individual", "body corporate": "Body corporate", "corporate": "Body corporate"}.get(ctype.lower(), "")
        if not ctype:
            problems.append(f"{where}: customer type must be Individual or Body corporate.")
            continue
        d = _date(get("Transaction date"), where, problems)
        if d is None:
            continue
        out.append(Txn(
            date=d,
            customer_name=str(get("Customer name") or "").strip(),
            customer_type=ctype,
            account_number=str(get("Account number") or "").strip(),
            bvn_or_rc=str(get("BVN / RC number") or "").strip(),
            transaction_type=str(get("Transaction type") or "").strip(),
            amount=_num(get("Amount (NGN)"), f"{where} amount", problems),
            narration=str(get("Narration") or "").strip(),
            branch=str(get("Branch") or "").strip(),
            channel=str(get("Channel / teller") or "").strip(),
            row=offset,
        ))
    return out, problems
