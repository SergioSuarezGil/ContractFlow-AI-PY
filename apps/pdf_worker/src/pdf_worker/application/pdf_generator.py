from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from fpdf import FPDF


@dataclass
class PdfReportInput:
    title: str
    job_id: str
    contract_id: str
    verdict: str
    summary: str
    price_notes: str
    coverage_notes: str
    disclaimer: str
    analysis_mode: str = "mock"
    risks: list[str] = field(default_factory=list)
    citations: list[dict[str, object]] = field(default_factory=list)


class MultipagePdfGenerator:
    """Generate a multipage A4 PDF report (task 8)."""

    def generate(self, input_data: PdfReportInput) -> bytes:
        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_margins(20, 20, 20)

        self._write(pdf, _safe(input_data.title), bold=True, size=16)
        mode = "REAL (Gemini)" if input_data.analysis_mode == "gemini" else "MOCK"
        for line in (
            f"Analysis mode: {mode}",
            f"Verdict: {input_data.verdict}",
            f"Job: {input_data.job_id}",
            f"Contract: {input_data.contract_id}",
        ):
            self._write(pdf, _safe(line), size=11)
        pdf.ln(4)

        for heading, body in (
            ("Summary", input_data.summary),
            ("Price notes", input_data.price_notes),
            ("Coverage notes", input_data.coverage_notes),
            ("Disclaimer", input_data.disclaimer),
        ):
            self._write(pdf, _safe(heading), bold=True, size=12)
            self._write(pdf, _safe(body or "-"), size=11)
            pdf.ln(2)

        if input_data.risks:
            self._write(pdf, "Risks", bold=True, size=12)
            for risk in input_data.risks:
                self._write(pdf, _safe(f"- {risk}"), size=11)
            pdf.ln(2)

        if input_data.citations:
            self._write(pdf, "Citations", bold=True, size=12)
            for citation in input_data.citations:
                doc_id = citation.get("documentId", "")
                page = citation.get("page")
                excerpt = citation.get("excerpt", "")
                label = f"[{doc_id}"
                if page is not None:
                    label += f" p.{page}"
                label += f"] {excerpt}"
                self._write(pdf, _safe(label), size=11)

        if pdf.page_no() < 2:
            pdf.add_page()
            self._write(
                pdf,
                _safe(
                    "Appendix — ContractFlow AI generated this comparative report "
                    "for interview-spine demos. Page intentionally reserved for multipage proof."
                ),
                size=11,
            )

        buffer = BytesIO()
        pdf.output(buffer)
        return buffer.getvalue()

    def _write(self, pdf: FPDF, text: str, *, bold: bool = False, size: int = 11) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(pdf.epw, 6, text)


def _safe(value: str) -> str:
    return value.encode("latin-1", errors="replace").decode("latin-1")
