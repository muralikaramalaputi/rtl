from unittest.mock import MagicMock, mock_open, patch

from django.test import TestCase

from .dv_generator import _basic_systemverilog_validation, _parse_artifacts
from .rtl_generator import GenerationError, _extract_verilog, generate_rtl
from .verification import VerificationError, verify_rtl_and_testbench


class TestbenchCountTests(TestCase):
    def test_dv_artifact_parser_accepts_raw_hdl_control_characters(self):
        """DV files are plain text, so their newlines/tabs must not be JSON-escaped."""
        generated_content = (
            "<<<FILE: directed_tests.sv>>>\n"
            "module directed_tests;\n\tinitial begin\n\t\t#10;\n\tend\nendmodule\n"
            "<<<END FILE>>>"
        )

        artifacts = _parse_artifacts(generated_content)

        self.assertEqual(
            artifacts["directed_tests.sv"],
            "module directed_tests;\n\tinitial begin\n\t\t#10;\n\tend\nendmodule",
        )

    def test_dv_static_validation_ignores_comments_and_assert_property(self):
        artifact = """
            module assertions;
                // Property 1: this comment is not a declaration.
                property p_count;
                    1 |=> 1;
                endproperty
                a_count: assert property (p_count)
                    else $error("property failed");
            endmodule
        """

        self.assertEqual(
            _basic_systemverilog_validation("assertions.sv", artifact), []
        )

    @patch("rtl_app.verification.shutil.which", return_value=None)
    @patch("rtl_app.verification.IVERILOG_PATH", "C:\\missing\\iverilog.exe")
    def test_verification_requires_iverilog(self, _which):
        with self.assertRaises(VerificationError):
            verify_rtl_and_testbench("module dut; endmodule", "module testbench; endmodule")

    @patch("rtl_app.rtl_generator._extract_verilog", return_value="module alu; endmodule")
    @patch("rtl_app.rtl_generator.get_client")
    def test_generation_keeps_gemini_client_alive_for_request(
        self, mock_get_client, _extract_verilog
    ):
        client = MagicMock()
        client.models.generate_content.return_value.text = "module alu; endmodule"
        mock_get_client.return_value = client

        from .rtl_generator import _generate

        _generate("Generate an ALU.")

        client.models.generate_content.assert_called_once()

    def test_extract_verilog_discards_model_reasoning(self):
        generated_content = "<think>Long internal reasoning</think>\nmodule alu; endmodule"

        self.assertEqual(_extract_verilog(generated_content), "module alu; endmodule")

    def test_extract_verilog_rejects_incomplete_module(self):
        with self.assertRaises(GenerationError):
            _extract_verilog("<think>reasoning</think> module alu;")

    @patch("rtl_app.rtl_generator._generate")
    def test_testbench_prompt_includes_requested_test_case_count(
        self, mock_generate
    ):
        mock_generate.side_effect = [
            "module counter; endmodule",
            "module testbench; endmodule",
        ]

        _, testbench = generate_rtl("Create a counter.", 3)

        testbench_prompt = mock_generate.call_args_list[1].args[0]

        self.assertEqual(testbench, "module testbench; endmodule")
        self.assertRegex(
            testbench_prompt,
            r"exactly\s+3\s+meaningful and different test cases",
        )

    @patch("rtl_app.rtl_generator._generate")
    def test_generation_uses_selected_provider(self, mock_generate):
        mock_generate.side_effect = [
            "module counter; endmodule",
            "module testbench; endmodule",
        ]

        generate_rtl("Create a counter.", 1, "groq")

        self.assertEqual(mock_generate.call_args_list[0].args[1], "groq")
        self.assertEqual(mock_generate.call_args_list[1].args[1], "groq")

    @patch(
        "rtl_app.views.generate_rtl",
        return_value=("module dut; endmodule", "module tb; endmodule"),
    )
    @patch("rtl_app.views.compile_rtl_and_testbench", return_value=[])
    @patch("rtl_app.views.verify_rtl_syntax_and_lint", return_value=[])
    @patch("rtl_app.views.generate_dv_artifacts", return_value=[])
    def test_home_passes_test_case_count_to_generator(
        self, _generate_dv, _verify, _compile, mock_generate
    ):
        with patch("rtl_app.views.open", mock_open(), create=True):
            response = self.client.post(
                "/",
                {
                    "specification": "Create an incrementing counter.",
                    "test_case_count": "15",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_called_once_with(
            "Create an incrementing counter.", 15, "gemini"
        )
