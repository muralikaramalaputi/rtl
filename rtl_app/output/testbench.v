module tb_alu8;
    reg [7:0] a;
    reg [7:0] b;
    reg [2:0] opcode;
    wire [7:0] result;

    alu8 dut (
        .a(a),
        .b(b),
        .opcode(opcode),
        .result(result)
    );

    integer total_tests;
    integer tests_passed;
    integer tests_failed;

    initial begin
        total_tests = 0;
        tests_passed = 0;
        tests_failed = 0;

        // Test Case 1: Addition (opcode 000)
        a = 8'h0A;
        b = 8'h05;
        opcode = 3'b000;
        #10;
        total_tests = total_tests + 1;
        if (result === 8'h0F) begin
            tests_passed = tests_passed + 1;
            $display("Test Case 1: PASS - Addition 0x0A + 0x05 = 0x0F");
        end else begin
            tests_failed = tests_failed + 1;
            $display("Test Case 1: FAIL - Expected 0x0F, Got 0x%02X", result);
        end

        $display("");
        $display("SIMULATION SUMMARY");
        $display("Total Test Cases: %0d", total_tests);
        $display("Passed Test Cases: %0d", tests_passed);
        $display("Failed Test Cases: %0d", tests_failed);
        if (tests_failed == 0) begin
            $display("OVERALL STATUS : PASS");
        end else begin
            $display("OVERALL STATUS : FAIL");
        end
        $finish;
    end
endmodule