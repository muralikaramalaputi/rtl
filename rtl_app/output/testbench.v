module tb_alu8;

    reg  [7:0] a;
    reg  [7:0] b;
    reg  [2:0] opcode;
    wire [7:0] result;

    integer total_tests = 0;
    integer tests_passed = 0;
    integer tests_failed = 0;

    reg [7:0] expected_result;

    alu8 uut (
        .a(a),
        .b(b),
        .opcode(opcode),
        .result(result)
    );

    initial begin
        a = 8'h00;
        b = 8'h00;
        opcode = 3'b000;
        expected_result = 8'h00;

        #10;

        // Test Case 1: Addition (opcode 000)
        total_tests = total_tests + 1;
        a = 8'h25;
        b = 8'h1F;
        opcode = 3'b000;
        expected_result = 8'h44;
        #10;

        if (result === expected_result) begin
            $display("Test Case 1 PASS: Addition a=%h, b=%h, opcode=%b | result=%h, expected=%h", a, b, opcode, result, expected_result);
            tests_passed = tests_passed + 1;
        end else begin
            $display("Test Case 1 FAIL: Addition a=%h, b=%h, opcode=%b | result=%h, expected=%h", a, b, opcode, result, expected_result);
            tests_failed = tests_failed + 1;
        end

        $display("\nSIMULATION SUMMARY");
        $display("Total Test Cases  : %0d", total_tests);
        $display("Passed Test Cases : %0d", tests_passed);
        $display("Failed Test Cases : %0d", tests_failed);

        if (tests_failed == 0) begin
            $display("OVERALL STATUS : PASS");
        end else begin
            $display("OVERALL STATUS : FAIL");
        end

        $finish;
    end

endmodule