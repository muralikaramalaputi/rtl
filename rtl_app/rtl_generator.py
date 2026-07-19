from .model_loader import client, MODEL
from .prompts import SYSTEM_PROMPT


class GenerationError(Exception):
    """Raised when RTL/Testbench generation fails."""
    pass


def _generate(prompt):
    """
    Generate text using Groq API.
    """

    try:

        completion = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_completion_tokens=2048,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        raise GenerationError(str(e))


def generate_rtl(specification):
    """
    Generate RTL and Testbench.
    """

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

    tb_prompt = f"""
Generate a COMPLETE SELF-CHECKING Verilog Testbench.

RTL:

{rtl}

Requirements:

1. Detect DUT automatically.
2. Detect all ports automatically.
3. Generate clock only if clk exists.
4. Generate reset only if rst exists.
5. Never generate clock for combinational logic.
6. Declare DUT inputs as reg.
7. Declare DUT outputs as wire.
8. Instantiate DUT correctly.
9. Cover all operations.
10. Calculate expected values mathematically.
11. Never guess outputs.
12. Compare DUT output with expected output.
13. Print PASS/FAIL.
14. Use $monitor.
15. Never generate nested initial blocks.
16. Never generate undeclared signals.
17. Use valid hexadecimal literals.
18. End simulation using $finish.
19. Return ONLY Verilog code.
20. No explanation.
21. No Markdown.
22. No ```verilog.
"""

    tb = _generate(tb_prompt)

    return rtl, tb