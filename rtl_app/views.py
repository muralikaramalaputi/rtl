import os
from pathlib import Path
import PyPDF2
from docx import Document

from django.shortcuts import render
from django.http import FileResponse, Http404

from .rtl_generator import generate_rtl, GenerationError
from .dv_generator import generate_dv_artifacts
from .verification import (
    VerificationError,
    compile_rtl_and_testbench,
    verify_rtl_syntax_and_lint,
)


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

RTL_FILE = os.path.join(OUTPUT_DIR, "generated_rtl.v")
TB_FILE = os.path.join(OUTPUT_DIR, "testbench.v")
DV_DIR = os.path.join(OUTPUT_DIR, "dv")


def extract_text(uploaded_file):
    """
    Extract text from uploaded TXT, PDF or DOCX file.
    """

    filename = uploaded_file.name.lower()

    # TXT
    if filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8")

    # PDF
    elif filename.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    # DOCX
    elif filename.endswith(".docx"):

        document = Document(uploaded_file)

        text = ""

        for para in document.paragraphs:
            text += para.text + "\n"

        return text

    return ""


def home(request):

    rtl = ""
    tb = ""
    error = ""
    validation_log = ""
    verification_results = []
    dv_artifacts = []
    specification = ""
    test_case_count = "1"
    provider = "gemini"

    if request.method == "POST":

        specification = request.POST.get("specification", "").strip()
        test_case_count = request.POST.get("test_case_count", "1").strip()
        provider = request.POST.get("provider", "gemini").strip().lower()

        uploaded_file = request.FILES.get("spec_file")

        if uploaded_file:
            specification = extract_text(uploaded_file)

        try:
            test_case_count_value = int(test_case_count)

            if not 1 <= test_case_count_value <= 50:
                raise ValueError

        except ValueError:
            error = "Enter a whole number from 1 to 50 for the test case count."

        if specification and not error:

            try:

                # ---------------------------------------------------------
                # STEP 1: Generate RTL + matching Testbench
                # ---------------------------------------------------------
                rtl, tb = generate_rtl(
                    specification,
                    test_case_count_value,
                    provider,
                )

                # ---------------------------------------------------------
                # STEP 2: RTL Syntax Check + Lint
                # ---------------------------------------------------------
                report = verify_rtl_syntax_and_lint(rtl)

                validation_log = "\n".join(report)

                verification_results = getattr(
                    report,
                    "results",
                    []
                )

                os.makedirs(
                    OUTPUT_DIR,
                    exist_ok=True
                )

                # ---------------------------------------------------------
                # STEP 3: Generate ALL DV artifacts using ONE Gemini request
                # ---------------------------------------------------------
                dv_files = generate_dv_artifacts(
                    specification,
                    rtl,
                    OUTPUT_DIR,
                    include_uvm=True,
                    provider=provider,
                )
                dv_artifacts = [path.name for path in dv_files]

                validation_log += "\n" + "\n".join(
                    f"[ok] DV artifact saved: {path.name}"
                    for path in dv_files
                )

                # ---------------------------------------------------------
                # STEP 4: Compile RTL + matching testbench
                # ---------------------------------------------------------
                compile_report = compile_rtl_and_testbench(rtl, tb)
                validation_log += "\n" + "\n".join(compile_report)
                verification_results += getattr(compile_report, "results", [])

                # ---------------------------------------------------------
                # STEP 5: Save final validated artifacts
                # ---------------------------------------------------------
                with open(
                    RTL_FILE,
                    "w",
                    encoding="utf-8"
                ) as f:
                    f.write(rtl)

                # ---------------------------------------------------------
                # STEP 6: Save Testbench
                # ---------------------------------------------------------
                with open(
                    TB_FILE,
                    "w",
                    encoding="utf-8"
                ) as f:
                    f.write(tb)

            except (
                GenerationError,
                VerificationError
            ) as exc:

                error = str(exc)

                verification_results = getattr(
                    exc,
                    "results",
                    verification_results
                )

                rtl = ""
                tb = ""

                # Remove old generated files
                if os.path.exists(RTL_FILE):
                    os.remove(RTL_FILE)

                if os.path.exists(TB_FILE):
                    os.remove(TB_FILE)

    return render(
        request,
        "index.html",
        {
            "rtl": rtl,
            "tb": tb,
            "error": error,
            "validation_log": validation_log,
            "verification_results": verification_results,
            "dv_artifacts": dv_artifacts,
            "specification": specification,
            "test_case_count": test_case_count,
            "provider": provider,
            "download": os.path.exists(RTL_FILE),
            "download_tb": os.path.exists(TB_FILE),
        },
    )


def download_verilog(request):

    if not os.path.exists(RTL_FILE):
        raise Http404("RTL file not found.")

    return FileResponse(
        open(RTL_FILE, "rb"),
        as_attachment=True,
        filename="generated_rtl.v",
    )


def download_tb(request):

    if not os.path.exists(TB_FILE):
        raise Http404("Testbench file not found.")

    return FileResponse(
        open(TB_FILE, "rb"),
        as_attachment=True,
        filename="testbench.v",
    )


def download_dv(request, filename):
    """Download a generated DV artifact without permitting path traversal."""
    if Path(filename).name != filename:
        raise Http404("DV artifact not found.")
    artifact_path = Path(DV_DIR) / filename
    if not artifact_path.is_file():
        raise Http404("DV artifact not found.")
    return FileResponse(open(artifact_path, "rb"), as_attachment=True, filename=filename)
