from unittest.mock import MagicMock, mock_open, patch

from django.test import TestCase

from .rtl_generator import GenerationError, _extract_verilog, generate_rtl


class TestbenchCountTests(TestCase):
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
        self.assertIn("exactly 3 meaningful and different test cases", testbench_prompt)

    @patch(
        "rtl_app.views.generate_rtl",
        return_value=("module dut; endmodule", "module tb; endmodule"),
    )
    def test_home_passes_test_case_count_to_generator(self, mock_generate):
        with patch("rtl_app.views.os.makedirs"), patch(
            "rtl_app.views.open", mock_open(), create=True
        ):
            response = self.client.post(
                "/",
                {
                    "specification": "Create an incrementing counter.",
                    "test_case_count": "15",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_generate.assert_called_once_with(
            "Create an incrementing counter.", 15
        )
