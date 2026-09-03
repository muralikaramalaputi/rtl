"""Local Verilog verification stages for generated design files."""

import shutil
import subprocess
import tempfile
from pathlib import Path


IVERILOG_PATH = r"C:\Users\karam\OneDrive\Desktop\rtl\rtll\iverilog\bin\iverilog.exe"


class VerificationError(Exception):
    """Raised when generated Verilog cannot pass local verification."""


class VerificationReport(list):
    """Verification log lines together with their per-stage statuses."""

    def __init__(self, logs, results):
        super().__init__(logs)
        self.results = results


def _run(command, stage, cwd):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    details = "\n".join(item for item in (result.stdout, result.stderr) if item).strip()

    if result.returncode:
        message = details or "No diagnostic output was produced."
        raise VerificationError(f"{stage} failed:\n{message}")

    return details


def _get_iverilog(results):
    """Return Icarus Verilog or raise an error that preserves stage statuses."""
    iverilog = IVERILOG_PATH if Path(IVERILOG_PATH).is_file() else shutil.which("iverilog")
    if iverilog:
        return iverilog

    error = VerificationError(
        "Icarus Verilog (iverilog) is required for RTL verification but is not installed."
    )
    error.results = results
    raise error


def verify_rtl_syntax_and_lint(rtl):
    """Run the syntax-check and lint stages for generated RTL."""
    results = [
        {"name": "RTL Syntax Check", "status": "not_run"},
        {"name": "RTL Lint", "status": "not_run"},
    ]
    iverilog = _get_iverilog(results)

    verification_root = Path(__file__).resolve().parent / "output"
    verification_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="rtl_verification_", dir=verification_root
    ) as temp_dir:
        directory = Path(temp_dir)
        rtl_file = directory / "generated_rtl.v"
        rtl_file.write_text(rtl, encoding="utf-8")

        try:
            syntax_details = _run(
                [iverilog, "-g2012", "-tnull", str(rtl_file)],
                "RTL syntax check",
                directory,
            )
            results[0]["status"] = "passed"
            lint_details = _run(
                [iverilog, "-g2012", "-Wall", "-tnull", str(rtl_file)],
                "RTL lint",
                directory,
            )
            results[1]["status"] = "passed"
        except VerificationError as error:
            pending = next((result for result in results if result["status"] == "not_run"), None)
            if pending:
                pending["status"] = "failed"
            error.results = results
            raise

    logs = [
        "[ok] RTL syntax check passed",
        "[ok] RTL lint passed",
    ]
    for details in (syntax_details, lint_details):
        if details:
            logs.append(details)
    return VerificationReport(logs, results)


def compile_rtl_and_testbench(rtl, testbench):
    """Compile the generated RTL and matching testbench after DV generation."""
    results = [{"name": "RTL + Testbench Compile", "status": "not_run"}]
    iverilog = _get_iverilog(results)
    verification_root = Path(__file__).resolve().parent / "output"
    verification_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="rtl_compile_", dir=verification_root
    ) as temp_dir:
        directory = Path(temp_dir)
        rtl_file = directory / "generated_rtl.v"
        testbench_file = directory / "testbench.v"
        executable = directory / "simulation.out"
        rtl_file.write_text(rtl, encoding="utf-8")
        testbench_file.write_text(testbench, encoding="utf-8")

        try:
            details = _run(
                [
                    iverilog, "-g2012", "-Wall", "-o", str(executable),
                    str(rtl_file), str(testbench_file),
                ],
                "RTL + testbench compile",
                directory,
            )
            results[0]["status"] = "passed"
        except VerificationError as error:
            results[0]["status"] = "failed"
            error.results = results
            raise

    logs = ["[ok] RTL + testbench compile passed"]
    if details:
        logs.append(details)
    return VerificationReport(logs, results)


def verify_rtl_and_testbench(rtl, testbench):
    """Backward-compatible complete RTL verification helper."""
    checks = verify_rtl_syntax_and_lint(rtl)
    compile_report = compile_rtl_and_testbench(rtl, testbench)
    return VerificationReport(
        [*checks, *compile_report], [*checks.results, *compile_report.results]
    )
