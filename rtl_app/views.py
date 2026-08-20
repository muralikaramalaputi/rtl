import os
import PyPDF2
from docx import Document

from django.shortcuts import render
from django.http import FileResponse, Http404

from .rtl_generator import generate_rtl, GenerationError


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

RTL_FILE = os.path.join(OUTPUT_DIR, "generated_rtl.v")
TB_FILE = os.path.join(OUTPUT_DIR, "testbench.v")


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
    specification = ""
    test_case_count = "1"

    if request.method == "POST":

        specification = request.POST.get("specification", "").strip()
        test_case_count = request.POST.get("test_case_count", "1").strip()

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

                rtl, tb = generate_rtl(specification, test_case_count_value)

                os.makedirs(OUTPUT_DIR, exist_ok=True)

                with open(RTL_FILE, "w", encoding="utf-8") as f:
                    f.write(rtl)

                with open(TB_FILE, "w", encoding="utf-8") as f:
                    f.write(tb)

            except GenerationError as exc:

                error = str(exc)

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
            "specification": specification,
            "test_case_count": test_case_count,
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
