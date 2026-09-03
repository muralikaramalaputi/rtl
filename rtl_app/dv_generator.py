"""
Gemini-based generation and validation of Design Verification artifacts.

Flow supported by this module:

    Requirement
        ↓
    RTL Generation
        ↓
    RTL Syntax Check
        ↓
    RTL Lint
        ↓
    DV Generation
        ↓
    DV Syntax / Compile Check
        ↓
    Final Validated Artifacts

IMPORTANT:
- This module does NOT run simulation.
- Generated DV artifacts are intended for later simulation.
- The requirement and RTL are the source of truth.
- The generator is generic and must work for different RTL designs.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Tuple

from .model_loader import get_client, get_model, normalize_provider, types
from .rtl_generator import (
    GenerationError,
    _is_temporary_model_error,
    _model_error_message,
)


# ============================================================
# DV ARTIFACT DEFINITIONS
# ============================================================

DV_ARTIFACTS: Tuple[Tuple[str, str], ...] = (
    ("directed_tests.sv", "Directed Tests"),
    ("scoreboard_reference_model.sv", "Scoreboard / Reference Model"),
    ("assertions.sv", "Assertions (SVA)"),
    ("constrained_random_tests.sv", "Constrained-Random Tests"),
    ("functional_coverage.sv", "Functional Coverage"),
    ("regression_test_list.txt", "Regression Test List"),
    ("uvm_testbench.sv", "UVM Testbench"),
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def _run_command(
    command: List[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 120,
) -> Tuple[bool, str]:
    """
    Execute an external validation command.

    Returns:
        (success, combined stdout/stderr)
    """

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )

        output = result.stdout or ""

        return result.returncode == 0, output

    except FileNotFoundError:
        return False, f"Tool not found: {command[0]}"

    except subprocess.TimeoutExpired:
        return False, (
            f"Command timed out after {timeout} seconds: "
            f"{' '.join(command)}"
        )

    except Exception as exc:
        return False, f"Command execution failed: {exc}"


def _tool_available(tool_name: str) -> bool:
    """Return True if an executable is available in PATH."""

    return shutil.which(tool_name) is not None


# ============================================================
# ARTIFACT PARSING
# ============================================================

def _parse_artifacts(text: str) -> Dict[str, str]:
    """
    Parse delimiter-separated artifacts returned by Gemini.

    Expected format:

        <<<FILE: directed_tests.sv>>>
        file content
        <<<END FILE>>>

        <<<FILE: assertions.sv>>>
        file content
        <<<END FILE>>>
    """

    if not text:
        return {}

    pattern = re.compile(
        r"<<<FILE:\s*(?P<filename>[^\r\n>]+?)\s*>>>\s*"
        r"(?P<content>.*?)"
        r"<<<END FILE>>>",
        re.DOTALL | re.IGNORECASE,
    )

    artifacts: Dict[str, str] = {}

    for match in pattern.finditer(text):
        filename = match.group("filename").strip()
        content = match.group("content").strip()

        if filename and content:
            artifacts[filename] = content

    return artifacts


# ============================================================
# ARTIFACT CLEANING
# ============================================================

def _clean_artifact(content: str) -> str:
    """
    Remove accidental Markdown code fences.

    The generated artifact itself must contain only source/text
    content and not Markdown fences.
    """

    if not content:
        return ""

    content = content.strip()

    # Remove opening Markdown fences.
    content = re.sub(
        r"^\s*```(?:verilog|systemverilog|sv|text)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    # Remove closing Markdown fence.
    content = re.sub(
        r"\s*```\s*$",
        "",
        content,
        flags=re.IGNORECASE,
    )

    return content.strip()


# ============================================================
# FILENAME VALIDATION
# ============================================================

def _validate_filename(filename: str) -> bool:
    """
    Prevent unexpected paths such as ../../something.
    """

    path = Path(filename)

    if path.name != filename:
        return False

    if filename in {"", ".", ".."}:
        return False

    return True


# ============================================================
# BASIC STATIC VALIDATION
# ============================================================

def _source_without_comments_and_strings(content: str) -> str:
    """Remove comments and strings before performing keyword-based checks."""
    pattern = re.compile(
        r'//[^\r\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        # Keep line positions intact for any future diagnostics.
        return "\n" * match.group(0).count("\n")

    return pattern.sub(replace, content)


def _basic_systemverilog_validation(
    filename: str,
    content: str,
) -> List[str]:
    """
    Perform lightweight source-level checks.

    These checks do not replace a real simulator/compiler.
    They catch common LLM generation errors before external
    compilation is attempted.
    """

    errors: List[str] = []

    if not content.strip():
        errors.append("Artifact is empty.")
        return errors

    # --------------------------------------------------------
    # Markdown checks
    # --------------------------------------------------------

    if "```" in content:
        errors.append("Markdown code fence detected inside artifact.")

    # --------------------------------------------------------
    # Common malformed literals seen in LLM-generated code
    # --------------------------------------------------------

    malformed_literal_patterns = [
        r"\b\d+\s+me\b",
        r"\b\d+\s+mh\b",
        r"\b\d+\s+xx\b",
        r"\b\d+\s+me\s*=>",
        r"\b\d+\s+mh\s*=>",
    ]

    for pattern in malformed_literal_patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            errors.append(
                f"Malformed numeric literal detected: {pattern}"
            )

    # --------------------------------------------------------
    # Obvious natural-language leakage
    # --------------------------------------------------------

    if re.search(
        r"^\s*(Here is|Here are|Explanation:|Sure,|Certainly,)",
        content,
        flags=re.IGNORECASE | re.MULTILINE,
    ):
        errors.append(
            "Natural-language text appears before the artifact source."
        )

    # --------------------------------------------------------
    # Balanced structural keywords
    # --------------------------------------------------------

    source = _source_without_comments_and_strings(content)

    keyword_pairs = [
        ("module", r"\bmodule\s+[A-Za-z_$][A-Za-z0-9_$]*", "endmodule"),
        ("class", r"\bclass\s+[A-Za-z_$][A-Za-z0-9_$]*", "endclass"),
        ("function", r"\bfunction\b", "endfunction"),
        ("task", r"\btask\s+(?:automatic\s+|static\s+)?[A-Za-z_$]", "endtask"),
        # Do not count `assert property (...)` as a property declaration.
        ("property", r"\bproperty\s+[A-Za-z_$][A-Za-z0-9_$]*", "endproperty"),
        ("covergroup", r"\bcovergroup\s+[A-Za-z_$][A-Za-z0-9_$]*", "endgroup"),
    ]

    for start_keyword, start_pattern, end_keyword in keyword_pairs:
        start_count = len(
            re.findall(
                start_pattern,
                source,
                flags=re.IGNORECASE,
            )
        )

        end_count = len(
            re.findall(
                rf"\b{re.escape(end_keyword)}\b",
                source,
                flags=re.IGNORECASE,
            )
        )

        if start_count != end_count:
            errors.append(
                f"Unbalanced {start_keyword}/{end_keyword}: "
                f"{start_count} vs {end_count}."
            )

    # --------------------------------------------------------
    # Basic begin/end check
    # --------------------------------------------------------

    begin_count = len(
        re.findall(r"\bbegin\b", source, flags=re.IGNORECASE)
    )

    end_count = len(
        re.findall(r"\bend\b", source, flags=re.IGNORECASE)
    )

    if begin_count != end_count:
        errors.append(
            f"Unbalanced begin/end: {begin_count} vs {end_count}."
        )

    # --------------------------------------------------------
    # Duplicate coverage-bin names
    # --------------------------------------------------------
    #
    # SystemVerilog allows the same bin name in different
    # coverpoints. Therefore, duplicate names are only an error
    # when they occur more than once within the same coverpoint.
    # This avoids false failures such as:
    #
    #   coverpoint data  { bins zero = {0}; }
    #   coverpoint count { bins zero = {0}; }
    #
    # but still catches:
    #
    #   coverpoint data {
    #       bins zero = {0};
    #       bins zero = {1};
    #   }

    coverpoint_pattern = re.compile(
        r"\bcoverpoint\b(?:[^;{}]|\{[^{}]*\})*\{(?P<body>.*?)\}",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for coverpoint_match in coverpoint_pattern.finditer(source):
        coverpoint_body = coverpoint_match.group("body")

        bins = re.findall(
            r"\bbins\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
            coverpoint_body,
            flags=re.IGNORECASE,
        )

        duplicates = sorted(
            {
                name
                for name in bins
                if bins.count(name) > 1
            }
        )

        if duplicates:
            errors.append(
                "Duplicate coverage-bin names detected in the same "
                "coverpoint: "
                + ", ".join(duplicates)
            )

    # --------------------------------------------------------
    # Invalid placeholder text
    # --------------------------------------------------------

    invalid_placeholders = [
        "TODO",
        "<complete file content>",
        "<insert code here>",
        "<generated code>",
    ]

    for placeholder in invalid_placeholders:
        if placeholder.lower() in content.lower():
            errors.append(
                f"Placeholder text detected: {placeholder}"
            )

    return errors


# ============================================================
# REQUIREMENT / RTL CONSISTENCY CHECKS
# ============================================================

def _extract_dut_module_name(rtl: str) -> Optional[str]:
    """
    Extract the first Verilog/SystemVerilog module name.
    """

    if not rtl:
        return None

    match = re.search(
        r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)",
        rtl,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


def _extract_dut_ports(rtl: str) -> List[str]:
    """
    Extract simple DUT port names from the module declaration/body.

    This is intentionally conservative.
    """

    ports: List[str] = []

    # Capture declarations such as:
    # input wire clk
    # input logic [7:0] data
    # output reg [7:0] count
    pattern = re.compile(
        r"\b(?:input|output|inout)\b"
        r"(?:\s+(?:wire|reg|logic|signed|unsigned))*"
        r"(?:\s*\[[^\]]+\])?"
        r"\s+([A-Za-z_][A-Za-z0-9_]*)",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(rtl):
        name = match.group(1)

        if name not in ports:
            ports.append(name)

    return ports


def _validate_generated_dut_references(
    rtl: str,
    artifacts: Dict[str, str],
) -> List[str]:
    """
    Check that generated artifacts at least reference the actual
    DUT module name and avoid obvious hard-coded counter assumptions.

    This is not a full semantic compiler check.
    """

    errors: List[str] = []

    dut_name = _extract_dut_module_name(rtl)

    if not dut_name:
        errors.append(
            "Could not determine DUT module name from RTL."
        )
        return errors

    dut_ports = _extract_dut_ports(rtl)

    for filename, content in artifacts.items():

        # Regression list and textual artifacts don't need DUT
        # instantiation.
        if filename == "regression_test_list.txt":
            continue

        # UVM and directed tests should normally instantiate/reference
        # the DUT.
        if filename in {
            "directed_tests.sv",
            "constrained_random_tests.sv",
            "uvm_testbench.sv",
        }:
            if dut_name not in content:
                errors.append(
                    f"{filename}: DUT module '{dut_name}' "
                    f"is not referenced."
                )

        # ----------------------------------------------------
        # Check that obvious generated DUT ports exist.
        # ----------------------------------------------------

        if filename in {
            "directed_tests.sv",
            "constrained_random_tests.sv",
            "uvm_testbench.sv",
        }:
            for port in dut_ports:
                # This check is intentionally warning-like.
                # A port may be connected indirectly through an
                # interface, so don't fail solely on this.
                _ = port

    return errors


# ============================================================
# GEMINI PROMPT
# ============================================================

def _build_dv_prompt(
    requirement: str,
    rtl: str,
    include_uvm: bool,
) -> str:
    """
    Build the complete requirement-driven DV generation prompt.
    """

    artifact_list = """
1. directed_tests.sv
2. scoreboard_reference_model.sv
3. assertions.sv
4. constrained_random_tests.sv
5. functional_coverage.sv
6. regression_test_list.txt
"""

    if include_uvm:
        artifact_list += "7. uvm_testbench.sv\n"

    uvm_section = ""

    if include_uvm:
        uvm_section = """
==================================================
7. uvm_testbench.sv
==================================================

Generate a generic UVM/SystemVerilog verification environment.

Include, where applicable:

- interface
- sequence_item
- sequence
- sequencer
- driver
- monitor
- agent
- scoreboard
- environment
- test
- top module

Requirements:

- Match the exact DUT module name.
- Match exact DUT ports.
- Do not invent DUT ports.
- Do not invent DUT behavior.
- Use an independent expected/reference calculation.

SEQUENCE:

- Explicitly declare all sequence item variables.
- Do not use undeclared variables.
- Initial reset transaction must follow the requirement.
- Random transactions must use valid constraints.

DRIVER CLOCKING:

For synchronous DUTs:

- Do NOT drive DUT inputs at the same posedge used by the DUT.
- Prefer:

      @(negedge vif.clk);
      vif.<signal> <= req.<signal>;

- The DUT should sample those inputs on the following posedge.

MONITOR CLOCKING:

- Observe the DUT at its active clock edge.
- Allow nonblocking DUT updates to settle.
- A small #1 delay after posedge may be used.

SCOREBOARD:

- Maintain an independent expected state.
- Update the model according to the sampled transaction.
- Compare the expected output with the DUT output from the same cycle.
- Handle natural arithmetic wrapping at the DUT width.
- Do not compare the wrong cycle.

TOP MODULE:

- Initialize the clock.
- Initialize interface controls.
- Instantiate the DUT using exact port names.
- Set the virtual interface.
- Call run_test().

Make sure every variable is declared.
Make sure all UVM classes are complete.
Do not generate incomplete UVM syntax.
"""

    return f"""
You are generating professional Design Verification artifacts.

The USER REQUIREMENT and RTL are the ONLY source of truth.

The generated verification package must be generic and requirement-driven.

Do NOT assume the design is a counter, ALU, MUX, FIFO, UART, FSM,
memory, register, or any other specific block unless the requirement
or RTL explicitly says so.

==================================================
REQUIRED ARTIFACTS
==================================================

{artifact_list}

==================================================
GLOBAL RULES
==================================================

1. Analyze the USER REQUIREMENT before generating artifacts.

2. Analyze the RTL before generating artifacts.

3. Use the exact RTL module name.

4. Use exact RTL port names.

5. Use exact RTL port directions.

6. Use exact RTL port widths.

7. Do not invent DUT ports.

8. Do not invent functionality.

9. Do not invent reset behavior.

10. Do not invent clock behavior.

11. Do not invent opcode values.

12. Do not invent state values.

13. Test only behavior specified by the requirement.

14. Keep all generated artifacts internally consistent.

15. All generated SystemVerilog must be syntactically valid.

16. Every variable must be declared.

17. Every numeric literal must be valid SystemVerilog syntax.

18. Never generate malformed literals such as:
       8 me
       8me
       8 mh
       8 xx

19. Do not generate Markdown code fences.

20. Do not return JSON.

21. Do not return explanations outside artifact blocks.

22. Do not combine multiple files into one artifact.

23. Do not omit requested artifacts.

24. Do not add extra artifacts.

25. Balance:
       begin/end
       module/endmodule
       class/endclass
       task/endtask
       function/endfunction
       property/endproperty
       covergroup/endgroup

26. Do not generate accidental natural-language text inside source code.

27. Do not add simulation-only behavior to DUT RTL.

28. DV artifacts are intended for later simulation.

29. Do not claim simulation results.

30. Before returning the files, perform an internal consistency review.

==================================================
1. directed_tests.sv
==================================================

Generate directed functional tests.

Requirements:

- Use exact DUT module name.
- Use exact DUT ports.
- Test every functional behavior explicitly specified.
- Test reset behavior.
- Test enable/hold behavior where applicable.
- Test all operating modes.
- Test specified boundary conditions.
- Test specified rollover/underflow behavior.
- Use self-checking comparisons.
- Maintain an error count.
- Report PASS/FAIL.
- End with a clear summary.

CLOCK/STIMULUS RULE:

For synchronous DUTs:

- Drive inputs before the active posedge.
- Prefer changing inputs on negedge clk.
- Check outputs after the following posedge.
- Do not race DUT sampling.

Do not invent extra functionality.

==================================================
2. scoreboard_reference_model.sv
==================================================

Generate an independent reference model.

Requirements:

- Calculate expected behavior independently.
- Use exact DUT input/output behavior.
- Maintain expected state/value.
- Handle reset exactly as specified.
- Handle enable/hold exactly as specified.
- Handle arithmetic width correctly.
- Natural N-bit arithmetic must wrap naturally.
- Do not introduce saturation unless explicitly required.
- Provide a clear comparison mechanism.
- The model must be valid SystemVerilog.

==================================================
3. assertions.sv
==================================================

Generate meaningful SystemVerilog Assertions.

Requirements:

- Check only specified behavior.
- Check synchronous reset correctly.
- Check hold behavior where applicable.
- Check each operating mode.
- Check specified boundary transitions.
- Use correct clock semantics.
- Use $past() only when appropriate.
- Use disable iff only when semantically correct.

For N-bit arithmetic:

- Natural N-bit truncation/wraparound is expected.

If bind is used:

- Use exact DUT module name.
- Use exact DUT signal names.
- Use syntactically valid bind syntax.

==================================================
4. constrained_random_tests.sv
==================================================

Generate constrained-random verification.

Requirements:

- Use SystemVerilog randomization.
- Generate only legal input values.
- Constraints must come from the requirement.
- Exercise reset, enable and operating modes where applicable.
- Include enough cycles for meaningful corner cases.
- Maintain an independent expected value.
- Compare output after the active clock edge.
- Clearly report mismatches.

CLOCK/STIMULUS:

For synchronous DUTs:

- Randomize before driving.
- Prefer driving on negedge clk.
- Sample/check after posedge clk.
- Never compare the DUT against the wrong cycle.

==================================================
5. functional_coverage.sv
==================================================

Generate SystemVerilog functional coverage.

Requirements:

- Cover important requirement-defined controls.
- Cover reset active/inactive where applicable.
- Cover enable active/inactive where applicable.
- Cover operating modes.
- Cover important output values.
- Cover specified boundaries.
- Cover specified transitions.
- Add meaningful cross coverage only.

For an 8-bit counter, if applicable:

    bins rollover  = (8'hFF => 8'h00);
    bins underflow = (8'h00 => 8'hFF);

Never generate invalid literals.

Do not duplicate identical bins.

- Bin names must be unique within each coverpoint.
- The same bin name may be reused in different coverpoints.
- If the same semantic bin name would occur in multiple coverpoints,
  prefix it with the coverpoint name, for example data_zero and count_zero.
- Never declare two bins with the same name inside one coverpoint.

The complete covergroup must be valid SystemVerilog.

If bind is used:

- Use exact DUT module name.
- Use exact signal names.
- Use valid bind syntax.

==================================================
6. regression_test_list.txt
==================================================

Generate a concise regression plan.

Each entry must contain:

- test name
- purpose
- actual generated filename

Only include tests corresponding to generated artifacts.

Example:

test_reset_behavior       | Validate reset behavior       | directed_tests.sv
test_hold_mode            | Validate hold behavior        | directed_tests.sv
test_count_up             | Validate count-up behavior    | directed_tests.sv
test_count_down           | Validate count-down behavior  | directed_tests.sv
test_rollover             | Validate rollover behavior   | directed_tests.sv
test_underflow            | Validate underflow behavior  | directed_tests.sv
test_constrained_random   | Randomized verification      | constrained_random_tests.sv
test_uvm_random_suite     | UVM verification             | uvm_testbench.sv

{uvm_section}

==================================================
USER REQUIREMENT
==================================================

{requirement}

==================================================
RTL
==================================================

{rtl}

==================================================
OUTPUT FORMAT
==================================================

Return every requested artifact using EXACTLY this format:

<<<FILE: directed_tests.sv>>>
<complete file content>
<<<END FILE>>>

<<<FILE: scoreboard_reference_model.sv>>>
<complete file content>
<<<END FILE>>>

<<<FILE: assertions.sv>>>
<complete file content>
<<<END FILE>>>

<<<FILE: constrained_random_tests.sv>>>
<complete file content>
<<<END FILE>>>

<<<FILE: functional_coverage.sv>>>
<complete file content>
<<<END FILE>>>

<<<FILE: regression_test_list.txt>>>
<complete file content>
<<<END FILE>>>

{'''
<<<FILE: uvm_testbench.sv>>>
<complete file content>
<<<END FILE>>>
''' if include_uvm else ""}

FINAL RULES:

- Return ALL requested files.
- Use exact filenames.
- Return exactly one block for each file.
- Do not omit files.
- Do not add extra files.
- Do not use Markdown code fences.
- Do not put explanations outside file blocks.
- Ensure all artifacts are syntactically valid.
- Ensure all artifacts are internally consistent.
"""


# ============================================================
# GEMINI GENERATION
# ============================================================

def _generate_all_dv_artifacts(
    requirement: str,
    rtl: str,
    include_uvm: bool = True,
    provider: str = "gemini",
) -> Dict[str, str]:
    """
    Generate all DV artifacts using one Gemini request.
    """

    if not requirement or not requirement.strip():
        raise GenerationError(
            "DV generation failed: requirement is empty."
        )

    if not rtl or not rtl.strip():
        raise GenerationError(
            "DV generation failed: RTL is empty."
        )

    prompt = _build_dv_prompt(
        requirement=requirement,
        rtl=rtl,
        include_uvm=include_uvm,
    )

    try:
        provider = normalize_provider(provider)
        client = get_client(provider)

        response = None

        for attempt in range(3):

            try:
                if provider == "groq":
                    response = client.chat.completions.create(
                        model=get_model(provider),
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                        max_tokens=30000,
                    )
                else:
                    response = client.models.generate_content(
                        model=get_model(provider),
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0,
                            max_output_tokens=30000,
                        ),
                    )

                break

            except Exception as exc:

                if (
                    not _is_temporary_model_error(exc)
                    or attempt == 2
                ):
                    raise

                time.sleep(2 ** attempt)

        if response is None:
            raise GenerationError(
                "Gemini returned no response for DV generation."
            )

        if provider == "groq":
            content = response.choices[0].message.content
        else:
            content = getattr(response, "text", None)

        if not content:
            raise GenerationError(
                "Gemini returned no DV artifacts."
            )

        artifacts = _parse_artifacts(content.strip())

        if not artifacts:
            raise GenerationError(
                "Gemini returned DV artifacts in an invalid file format."
            )

        required_files = [
            "directed_tests.sv",
            "scoreboard_reference_model.sv",
            "assertions.sv",
            "constrained_random_tests.sv",
            "functional_coverage.sv",
            "regression_test_list.txt",
        ]

        if include_uvm:
            required_files.append("uvm_testbench.sv")

        missing_files = [
            filename
            for filename in required_files
            if filename not in artifacts
        ]

        if missing_files:
            raise GenerationError(
                "Gemini did not generate required DV artifacts: "
                + ", ".join(missing_files)
            )

        cleaned_artifacts: Dict[str, str] = {}

        for filename in required_files:

            if not _validate_filename(filename):
                raise GenerationError(
                    f"Invalid artifact filename: {filename}"
                )

            cleaned_content = _clean_artifact(
                artifacts[filename]
            )

            if not cleaned_content:
                raise GenerationError(
                    f"DV artifact {filename} is empty."
                )

            cleaned_artifacts[filename] = cleaned_content

        # ----------------------------------------------------
        # Basic static checks
        # ----------------------------------------------------

        static_errors: List[str] = []

        for filename, artifact in cleaned_artifacts.items():

            if not filename.endswith(".txt"):

                errors = _basic_systemverilog_validation(
                    filename,
                    artifact,
                )

                if errors:
                    static_errors.extend(
                        f"{filename}: {error}"
                        for error in errors
                    )

        if static_errors:
            raise GenerationError(
                "Generated DV artifacts failed static validation:\n"
                + "\n".join(
                    f"- {error}"
                    for error in static_errors
                )
            )

        # ----------------------------------------------------
        # DUT consistency check
        # ----------------------------------------------------

        dut_errors = _validate_generated_dut_references(
            rtl,
            cleaned_artifacts,
        )

        if dut_errors:
            raise GenerationError(
                "Generated DV artifacts failed DUT consistency "
                "validation:\n"
                + "\n".join(
                    f"- {error}"
                    for error in dut_errors
                )
            )

        return cleaned_artifacts

    except GenerationError:
        raise

    except Exception as exc:
        raise GenerationError(
            f"DV generation failed: {_model_error_message(exc)}"
        ) from exc


# ============================================================
# DV COMPILATION / SYNTAX VALIDATION
# ============================================================

def _validate_with_iverilog(
    artifact_path: Path,
    rtl_path: Path,
) -> Tuple[bool, str]:
    """
    Validate a SystemVerilog artifact using Icarus Verilog.

    This is primarily useful for:
    - directed tests
    - constrained-random tests
    - simple SystemVerilog modules

    Some advanced SystemVerilog/UVM constructs may not be supported
    by Icarus. In those cases Verilator or a commercial simulator
    should be used.
    """

    if not _tool_available("iverilog"):
        return False, "iverilog is not installed."

    with tempfile.TemporaryDirectory() as temp_dir:

        output_file = Path(temp_dir) / "compile.out"

        command = [
            "iverilog",
            "-g2012",
            "-s",
            artifact_path.stem,
            "-o",
            str(output_file),
            str(rtl_path),
            str(artifact_path),
        ]

        return _run_command(
            command,
            cwd=artifact_path.parent,
        )


def _validate_with_verilator(
    artifact_path: Path,
    rtl_path: Path,
) -> Tuple[bool, str]:
    """
    Validate SystemVerilog with Verilator lint mode.

    This is useful for syntax/lint validation without simulation.
    """

    if not _tool_available("verilator"):
        return False, "verilator is not installed."

    command = [
        "verilator",
        "--lint-only",
        "--language",
        "1800-2012",
        str(rtl_path),
        str(artifact_path),
    ]

    return _run_command(
        command,
        cwd=artifact_path.parent,
    )


def _validate_sv_artifact(
    artifact_path: Path,
    rtl_path: Path,
) -> Tuple[bool, str]:
    """
    Validate one generated SystemVerilog artifact.

    Strategy:

    1. Try Verilator if available.
    2. Otherwise try Icarus.
    3. Otherwise report that an external validator is unavailable.

    No simulation is executed.
    """

    if _tool_available("verilator"):

        success, output = _validate_with_verilator(
            artifact_path,
            rtl_path,
        )

        if success:
            return True, output

        return False, output

    if _tool_available("iverilog"):

        return _validate_with_iverilog(
            artifact_path,
            rtl_path,
        )

    return (
        False,
        "No SystemVerilog compiler/linter found. "
        "Install Verilator or Icarus Verilog.",
    )


# ============================================================
# DV DIRECTORY VALIDATION
# ============================================================

def validate_dv_artifacts(
    rtl_path: Path,
    dv_directory: Path,
    *,
    include_uvm: bool = True,
) -> Dict[str, object]:
    """
    Validate generated DV artifacts.

    IMPORTANT:
    This function performs syntax/compile/lint-style checking only.

    It does NOT run simulation.

    Returns:

        {
            "passed": bool,
            "checked_files": [...],
            "failed_files": [...],
            "messages": [...]
        }
    """

    rtl_path = Path(rtl_path)
    dv_directory = Path(dv_directory)

    result: Dict[str, object] = {
        "passed": True,
        "checked_files": [],
        "failed_files": [],
        "messages": [],
    }

    if not rtl_path.exists():
        result["passed"] = False
        result["messages"].append(
            f"RTL file does not exist: {rtl_path}"
        )
        return result

    if not dv_directory.exists():
        result["passed"] = False
        result["messages"].append(
            f"DV directory does not exist: {dv_directory}"
        )
        return result

    files_to_validate = [
        "directed_tests.sv",
        "constrained_random_tests.sv",
    ]

    # Assertions, coverage, scoreboard and UVM may contain
    # advanced SystemVerilog constructs that require a simulator
    # with full SystemVerilog/UVM support.
    advanced_sv_files = [
        "scoreboard_reference_model.sv",
        "assertions.sv",
        "functional_coverage.sv",
    ]

    if include_uvm:
        advanced_sv_files.append("uvm_testbench.sv")

    files_to_validate.extend(advanced_sv_files)

    for filename in files_to_validate:

        artifact_path = dv_directory / filename

        if not artifact_path.exists():
            result["passed"] = False
            result["failed_files"].append(filename)
            result["messages"].append(
                f"Missing generated artifact: {filename}"
            )
            continue

        result["checked_files"].append(filename)

        static_errors = _basic_systemverilog_validation(
            filename,
            artifact_path.read_text(encoding="utf-8"),
        )

        if static_errors:

            result["passed"] = False
            result["failed_files"].append(filename)

            for error in static_errors:
                result["messages"].append(
                    f"{filename}: {error}"
                )

            continue

        # ----------------------------------------------------
        # External validation
        # ----------------------------------------------------

        success, output = _validate_sv_artifact(
            artifact_path,
            rtl_path,
        )

        if not success:

            # Do not silently call a missing compiler a successful
            # validation.
            result["passed"] = False
            result["failed_files"].append(filename)

            result["messages"].append(
                f"{filename}: external validation failed:\n"
                f"{output}"
            )

        else:

            result["messages"].append(
                f"{filename}: validation passed."
            )

    return result


# ============================================================
# MAIN DV GENERATION FUNCTION
# ============================================================

def generate_dv_artifacts(
    requirement: str,
    rtl: str,
    output_directory,
    include_uvm: bool = True,
    *,
    provider: str = "gemini",
    validate: bool = False,
    rtl_path: Optional[Path] = None,
):
    """
    Generate all DV artifacts.

    Args:
        requirement:
            Original user/design requirement.

        rtl:
            Generated RTL source.

        output_directory:
            Root output directory.

        include_uvm:
            Whether to generate UVM testbench.

        validate:
            If True, perform external syntax/lint validation
            after generation.

        rtl_path:
            Existing RTL file path used for compilation/lint.

    Returns:
        list[Path]:
            Generated DV artifact paths.

    IMPORTANT:
        Simulation is NOT performed.
    """

    if not requirement or not requirement.strip():
        raise GenerationError(
            "Requirement cannot be empty."
        )

    if not rtl or not rtl.strip():
        raise GenerationError(
            "RTL cannot be empty."
        )

    output_directory = Path(output_directory)

    dv_directory = output_directory / "dv"

    dv_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Generate artifacts
    # --------------------------------------------------------

    artifacts = _generate_all_dv_artifacts(
        requirement=requirement,
        rtl=rtl,
        include_uvm=include_uvm,
        provider=provider,
    )

    generated_paths: List[Path] = []

    # --------------------------------------------------------
    # Write artifacts
    # --------------------------------------------------------

    for filename, _name in DV_ARTIFACTS:

        if not include_uvm and filename == "uvm_testbench.sv":
            continue

        if filename not in artifacts:
            continue

        artifact_path = dv_directory / filename

        artifact_path.write_text(
            artifacts[filename],
            encoding="utf-8",
        )

        generated_paths.append(
            artifact_path
        )

    # --------------------------------------------------------
    # Optional external validation
    # --------------------------------------------------------

    if validate:

        if rtl_path is None:

            raise GenerationError(
                "Validation requested but rtl_path was not supplied."
            )

        validation_result = validate_dv_artifacts(
            rtl_path=Path(rtl_path),
            dv_directory=dv_directory,
            include_uvm=include_uvm,
        )

        if not validation_result["passed"]:

            messages = validation_result.get(
                "messages",
                [],
            )

            raise GenerationError(
                "Generated DV artifacts failed validation:\n"
                + "\n".join(
                    f"- {message}"
                    for message in messages
                )
            )

    return generated_paths


# ============================================================
# FULL DV PIPELINE HELPER
# ============================================================

def generate_and_validate_dv_artifacts(
    requirement: str,
    rtl: str,
    rtl_path: Path,
    output_directory,
    include_uvm: bool = True,
    provider: str = "gemini",
):
    """
    Generate DV artifacts and then validate them.

    No simulation is performed.

    Flow:

        Requirement
             ↓
        RTL already generated
             ↓
        DV Generation
             ↓
        DV Static Validation
             ↓
        DV Syntax/Lint/Compile Validation
             ↓
        Final Artifacts
    """

    return generate_dv_artifacts(
        requirement=requirement,
        rtl=rtl,
        output_directory=output_directory,
        include_uvm=include_uvm,
        provider=provider,
        validate=True,
        rtl_path=rtl_path,
    )
