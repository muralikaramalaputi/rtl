module tb_alu8;

    reg  [7:0] a;
    reg  [7:0] b;
    reg  [2:0] opcode;
    wire [7:0] result;

    integer test_case_count;
    integer passed_cases;
    integer failed_cases;

    reg [7:0] expected_result;

    alu8 uut (
        .a(a),
        .b(b),
        .opcode(opcode),
        .result(result)
    );

    initial begin
        test_case_count = 0;
        passed_cases = 0;
        failed_cases = 0;

        // Test Case 1: Addition operation test (opcode 3'b000)
        test_case_count = test_case_count + 1;
        a = 8'h12;
        b = 8'h34;
        opcode = 3'b000;
        expected_result = 8'h12 + 8'h34;
        #10;

        if (result === expected_result) begin
            $display("TEST CASE %0d PASSED: opcode=%b, a=%h, b=%h, result=%h", test_case_count, opcode, a, b, result);
            passed_cases = passed_cases + 1;
        end else begin
            $display("TEST CASE %0d FAILED: opcode=%b, a=%h, b=%h, expected=%h, got=%h", test_case_count, opcode, a, b, expected_result, result);
            failed_cases = failed_cases + 1;
        end

        $display("----------------------------------------");
        $display("Total Test Cases: %0d", test_case_count);
        $display("Passed Cases:     %0d", passed_cases);
        $display("Failed Cases:     %0d", failed_cases);
        if (failed_cases == 0 && passed_cases > 0) begin
            $display("ALL TESTS PASSED");
        end else begin
            $display("TESTS FAILED");
        end
        $display("----------------------------------------");

        $finish;
    end

endmodule