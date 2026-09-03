import re
import time

from .model_loader import get_client, get_model, normalize_provider, types
from .prompts import SYSTEM_PROMPT


class GenerationError(Exception):
    """Raised when RTL/Testbench generation fails."""
    pass


def _is_temporary_model_error(error):
    message = str(error).upper()

    return (
        "503" in message
        or "UNAVAILABLE" in message
    )


def _model_error_message(error):
    """Turn provider quota failures into a concise, actionable error."""
    message = str(error)
    normalized = message.upper()

    if "429" in normalized or "RESOURCE_EXHAUSTED" in normalized:
        return (
            "The selected AI provider has reached its request quota. "
            "Wait for the provider's reset time, choose the other provider, "
            "or increase the provider quota."
        )

    return message


def _generate(prompt, provider="gemini"):
    """
    Generate text using the Gemini API.
    """

    try:
        provider = normalize_provider(provider)
        client = get_client(provider)
        completion = None

        for attempt in range(3):
            try:
                if provider == "groq":
                    completion = client.chat.completions.create(
                        model=get_model(provider),
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0,
                        max_tokens=8192,
                    )
                else:
                    completion = client.models.generate_content(
                        model=get_model(provider),
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0,
                            max_output_tokens=8192,
                        ),
                    )

                break

            except Exception as exc:

                if not _is_temporary_model_error(exc) or attempt == 2:
                    raise

                time.sleep(2 ** attempt)

        if completion is None:
            raise GenerationError(
                "Gemini did not return a response."
            )

        if provider == "groq":
            content = completion.choices[0].message.content or ""
        else:
            content = completion.text or ""

        return _extract_verilog(content)

    except GenerationError:
        raise

    except Exception as e:
        raise GenerationError(_model_error_message(e))


def _extract_verilog(content):
    """
    Discard model reasoning or formatting and return one complete
    Verilog/SystemVerilog module.
    """

    # Remove <think>...</think> blocks if the model returns reasoning.
    without_reasoning = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=re.DOTALL,
    )

    # Remove Markdown code fences.
    without_fences = re.sub(
        r"```(?:verilog|systemverilog)?\s*|```",
        "",
        without_reasoning,
        flags=re.IGNORECASE,
    ).strip()

    # Find first module.
    module_start = re.search(
        r"\bmodule\b",
        without_fences,
    )

    if not module_start:
        raise GenerationError(
            "The model did not return Verilog code. "
            "Please try generating again."
        )

    verilog = without_fences[module_start.start():]

    # Find endmodule.
    module_end = re.search(
        r"\bendmodule\b",
        verilog,
    )

    if not module_end:
        raise GenerationError(
            "The model response was incomplete and did not contain "
            "endmodule. Please try again."
        )

    return verilog[:module_end.end()].strip()


def _rtl_prompt(specification):
    return f"""
Generate synthesizable Verilog RTL.

USER REQUIREMENT:

{specification}

Requirements:

1. Analyze the user requirement carefully.

2. Implement every functional requirement explicitly specified by
   the user.

3. Generate ONLY synthesizable Verilog-2001 RTL.

4. Generate a complete Verilog module.

5. Preserve the exact module name specified by the requirement.

6. Preserve the exact port names specified by the requirement.

7. Preserve the exact port directions specified by the requirement.

8. Preserve the exact port widths specified by the requirement.

9. Do not invent ports, signals, operations, or functionality that
   are not specified by the requirement.

10. Use meaningful signal names.

11. For combinational logic, use appropriate combinational coding
    such as always @(*).

12. For sequential logic, use the required clock and reset behavior
    specified by the requirement.

13. Do not generate unintended latches.

14. Use appropriate case/default handling where required.

15. Implement control values, states, operations, and modes exactly
    as specified by the requirement.

16. If the requirement is ambiguous, make the smallest reasonable
    implementation assumption and keep the RTL consistent with the
    requirement.

17. Make the generated RTL synthesizable.

18. Internally verify that every requirement has a corresponding
    RTL implementation before returning the answer.

19. Return ONLY the complete Verilog code.

20. Do NOT return explanations.

21. Do NOT return Markdown.

22. Do NOT return code fences.

23. Do NOT return analysis.

OUTPUT:

Return only the complete synthesizable Verilog RTL.
"""


def _testbench_prompt(rtl, specification, test_case_count):
    return f"""
You are a senior RTL Design Verification engineer.

Generate ONE valid and functional Verilog/SystemVerilog testbench
for the RTL and USER REQUIREMENT provided below.

==================================================
USER REQUIREMENT
==================================================

{specification}

==================================================
RTL
==================================================

{rtl}

==================================================
REQUESTED TEST CASE COUNT
==================================================

{test_case_count}

==================================================
OBJECTIVE
==================================================

Generate exactly ONE testbench containing exactly
{test_case_count} meaningful and different test cases.

The testbench must verify the RTL against the USER REQUIREMENT.

==================================================
IMPORTANT RULES
==================================================

1. Analyze the USER REQUIREMENT first.

2. Identify every functional behavior explicitly specified in the
   USER REQUIREMENT.

3. Analyze the RTL and identify:

   - module name
   - ports
   - directions
   - widths
   - operations
   - control signals
   - clock behavior
   - reset behavior
   - state behavior
   - timing behavior
   - valid operating conditions

4. Generate tests ONLY for functionality specified by the
   USER REQUIREMENT.

5. Do NOT assume a particular design type.

   The design may be:

   - ALU
   - counter
   - FIFO
   - MUX
   - register
   - FSM
   - UART
   - memory
   - interface
   - arithmetic block
   - control block
   - or any other RTL design.

6. Do NOT hard-code assumptions about:

   - opcode values
   - signal names
   - operations
   - clock
   - reset
   - timing
   - states
   - functionality

   unless they are present in the USER REQUIREMENT or RTL.

7. Do NOT invent functionality that is not specified.

8. Use the exact RTL module name.

9. Use the exact RTL port names.

10. Use the exact RTL port widths.

11. Do not add or remove DUT ports.

12. Every important functional behavior explicitly specified in the
    USER REQUIREMENT should be tested when enough test cases are
    available.

13. If the requirement contains:

    - modes
    - commands
    - opcode values
    - select values
    - states
    - enable conditions
    - reset conditions
    - boundary conditions
    - error conditions

    create tests for those behaviors based strictly on the
    requirement.

14. If the design has multiple operations or modes, distribute the
    requested test cases across those operations or modes.

15. If the number of requested test cases is sufficient, cover every
    explicitly specified functional behavior at least once.

16. If the number of requested test cases is smaller than the number
    of required behaviors, do NOT create additional test cases.

17. When test cases are limited, prioritize the most important
    behaviors from the USER REQUIREMENT.

18. Do not generate more than exactly
    {test_case_count} test cases.

19. Do not generate fewer than exactly
    {test_case_count} test cases.

==================================================
EXPECTED RESULT
==================================================

20. Calculate expected results strictly from the USER REQUIREMENT
    and actual RTL behavior.

21. Never guess expected results.

22. For each test case, compare the DUT output against the expected
    result.

23. Use === where appropriate so unknown X/Z values can be detected.

24. For arithmetic operations, carefully verify width and overflow
    behavior according to the actual RTL.

25. For shift operations, use the actual shift behavior implemented
    by the RTL and specified by the requirement.

==================================================
COMBINATIONAL RTL
==================================================

26. For combinational RTL:

    - apply inputs
    - wait for sufficient settling time
    - calculate expected output
    - compare actual and expected outputs

==================================================
SEQUENTIAL RTL
==================================================

27. For sequential RTL:

    - generate the required clock
    - apply reset correctly
    - synchronize stimulus to the clock
    - check outputs at the correct clock/event

==================================================
TEST CASE STRUCTURE
==================================================

28. Every test case must contain:

    - numbered test-case comment
    - stimulus
    - control signals
    - appropriate delay or clock synchronization
    - expected result
    - actual-vs-expected comparison
    - PASS/FAIL message

29. Every test case must be meaningfully different.

30. Avoid duplicate input/control combinations unless the requirement
    specifically requires repeated behavior under different timing
    or conditions.

==================================================
CORNER CASES
==================================================

31. Include relevant boundary/corner cases when the number of
    requested test cases allows them.

32. Examples of potentially relevant corner cases include:

    - zero
    - minimum value
    - maximum value
    - all ones
    - overflow
    - underflow
    - boundary control values
    - first/last state
    - reset
    - enable/disable
    - empty/full
    - valid/invalid
    - minimum/maximum count

33. Only use corner cases that are relevant to the actual
    USER REQUIREMENT.

==================================================
TEST COUNTERS
==================================================

34. Maintain:

    integer total_tests;
    integer tests_passed;
    integer tests_failed;

35. Increment total_tests for every test case.

36. Increment tests_passed when the expected and actual results match.

37. Increment tests_failed when the expected and actual results do
    not match.

38. Print the result of every test case.

==================================================
FINAL SUMMARY
==================================================

39. At the end print:

    SIMULATION SUMMARY

    Total Test Cases
    Passed Test Cases
    Failed Test Cases

40. If tests_failed == 0, print:

    OVERALL STATUS : PASS

41. If tests_failed > 0, print:

    OVERALL STATUS : FAIL

42. Call $finish at the end.

==================================================
VALIDITY
==================================================

43. Generate exactly ONE testbench module.

44. Do NOT generate the RTL again.

45. Do NOT generate multiple testbench modules.

46. Include the DUT instantiation.

47. Use valid Verilog/SystemVerilog syntax.

48. Use normal delays such as #10 when required.

49. Do not generate escaped delays such as \\#10.

50. Do not use unsupported syntax.

51. Before returning, internally verify:

    - exactly one testbench module
    - exactly {test_case_count} test cases
    - correct DUT interface
    - requirement coverage
    - correct expected values
    - valid syntax
    - correct counters
    - final PASS/FAIL reporting

==================================================
OUTPUT
==================================================

Return ONLY the complete Verilog/SystemVerilog testbench.

Do NOT return:

- Markdown
- code fences
- explanations
- analysis
- comments outside the testbench
"""


def generate_testbench(rtl, specification, test_case_count, provider="gemini"):
    """
    Generate a testbench that matches both the user requirement
    and the already-generated RTL.
    """

    return _generate(
        _testbench_prompt(
            rtl,
            specification,
            test_case_count,
        ),
        provider,
    )


def generate_rtl(specification, test_case_count=1, provider="gemini"):
    """
    Generate synthesizable RTL and its matching testbench.
    """

    rtl = _generate(
        _rtl_prompt(specification),
        provider,
    )

    tb = generate_testbench(
        rtl,
        specification,
        test_case_count,
        provider,
    )

    return rtl, tb
