import re

from .model_loader import MODEL, get_client, types
from .prompts import SYSTEM_PROMPT


class GenerationError(Exception):
    """Raised when RTL/Testbench generation fails."""
    pass


def _generate(prompt):
    """
    Generate text using the Gemini API.
    """
    try:
        client = get_client()
        completion = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
                max_output_tokens=8192,
            ),
        )

        content = completion.text or ""
        return _extract_verilog(content)

    except Exception as e:
        raise GenerationError(str(e))


def _extract_verilog(content):
    """Discard model reasoning or formatting and return one complete Verilog module."""
    without_reasoning = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    without_fences = re.sub(
        r"```(?:verilog|systemverilog)?\s*|```", "", without_reasoning, flags=re.IGNORECASE
    ).strip()

    module_start = re.search(r"\bmodule\b", without_fences)
    if not module_start:
        raise GenerationError("The model did not return Verilog code. Please try generating again.")

    verilog = without_fences[module_start.start():]
    module_end = re.search(r"\bendmodule\b", verilog)
    if not module_end:
        raise GenerationError(
            "The model response was incomplete and did not contain endmodule. Please try again."
        )

    return verilog[:module_end.end()].strip()


def generate_rtl(specification, test_case_count=1):
    """
    Generate RTL and one testbench with the requested number of test cases.
    """

    # -------------------------------------------------
    # RTL Generation
    # -------------------------------------------------
    rtl_prompt = f"""
Generate synthesizable Verilog RTL.

Specification:

{specification}

Requirements:

1. Analyze the specification carefully.
2. Generate ONLY synthesizable Verilog-2001 RTL.
3. Generate a complete Verilog module.
4. Detect all ports correctly.
5. Use meaningful signal names.
6. Never generate latches.
7. Use always @(*) for combinational logic.
8. Use always @(posedge clk) only if clock exists.
9. Include default case.
10. Return ONLY Verilog code.
11. No explanation.
12. No Markdown.
13. No ```verilog.
"""

    rtl = _generate(rtl_prompt)

    # -------------------------------------------------
    # Testbench Generation
    # -------------------------------------------------
    tb_prompt = f"""
You are an expert RTL Verification Engineer specializing in Verilog/SystemVerilog.

Your task is to generate ONE VALID and FUNCTIONAL RTL testbench for the given RTL design.

RTL CODE:

{rtl}

NUMBER OF TEST CASES REQUESTED:

{test_case_count}

OBJECTIVE:
Generate exactly ONE testbench containing exactly {test_case_count} meaningful and different test cases for the given RTL.

IMPORTANT RULES:
1. Generate EXACTLY ONE testbench module and exactly {test_case_count} test cases inside it.
2. Every test case must be meaningfully different. Do not repeat input values or scenarios.
3. Analyze the RTL before generating: module name, ports, directions, widths, operations, encodings, combinational/sequential behavior, clock/reset requirements, and valid operating conditions.
4. Use the exact RTL module name, ports, widths, opcode/control values, and behavior. Never invent ports, signals, operations, or functionality.
5. Use suitable scenarios supported by the RTL: functional, zero, minimum/maximum, boundary, corner, control/opcode, random, overflow/underflow, reset, sequential, or stress testing.
6. Distribute cases across RTL operations/modes when appropriate. Calculate expected results from actual RTL behavior; never guess. Verify arithmetic and shift behavior carefully.
7. For sequential RTL, generate the required clock, apply reset correctly, and synchronize stimulus to the clock.
8. Each test case must include a numbered comment, stimulus, controls, delay or synchronization, expected-result check using === where appropriate, and PASS/FAIL output.
9. Maintain test-case, passed, and failed counters. Report each case result, totals, and final PASS/FAIL status.
10. Use valid Verilog/SystemVerilog syntax with declarations, DUT instantiation, appropriate delays, and $finish.
11. Do not output Markdown, code fences, explanations, analysis, multiple modules, or escaped delays such as \\#10.
12. Before returning, internally verify exactly one module, exactly {test_case_count} test cases, valid syntax, correct DUT interface, expected results, and no duplicate cases.

OUTPUT:
Return ONLY the complete Verilog/SystemVerilog testbench. No explanations or Markdown.
"""

    tb = _generate(tb_prompt)

    return rtl, tb
