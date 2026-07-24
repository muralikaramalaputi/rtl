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


def validate_requirement(specification):
    """
    Validate whether the requirement is related to RTL/Verilog.
    """

    validation_prompt = f"""
You are an RTL requirement validator.

Determine whether the following requirement is related to:

- RTL
- Verilog
- VHDL
- FPGA
- ASIC
- Digital Logic
- Hardware Design
- FSM
- Counter
- Register
- Flip-Flop
- ALU
- Multiplier
- Divider
- MUX
- DEMUX
- Encoder
- Decoder
- Comparator
- Memory
- FIFO
- RAM
- ROM
- UART
- SPI
- I2C
- Processor
- CPU
- Cache
- Bus
- Synthesizable Hardware

If the requirement belongs to digital hardware design reply exactly:

VALID

Otherwise reply exactly:

INVALID

Return ONLY one word.

Requirement:

{specification}
"""

    response = _generate(validation_prompt).strip().upper()

    return response == "VALID"


def generate_rtl(specification):
    """
    Generate RTL and Testbench.
    """

    # -------------------------------------------------
    # Validate Requirement
    # -------------------------------------------------
    if not validate_requirement(specification):
        raise GenerationError(
            "Requirement mismatch. Please provide a valid RTL/Verilog hardware specification."
        )

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