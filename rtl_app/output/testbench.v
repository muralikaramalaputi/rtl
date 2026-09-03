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

    integer total_tests = 0;
    integer tests_passed = 0;
    integer tests_failed = 0;

    initial begin
        // Test case 1: Addition with overflow
        total_tests = total_tests + 1;
        a = 8'hFF;
        b = 8'h01;
        opcode = 3'b000; // addition
        #10; // wait for combinational logic
        if (result === 8'h00) begin
            $display("Test 1 PASS: %h + %h = %h", a, b, result);
            tests_passed = tests_passed + 1;
        end else begin
            $display("Test 1 FAIL: %h + %h = %h, expected 8'h00", a, b, result);
            tests_failed = tests_failed + 1;
        end

        // Summary
        $display("\nSIMULATION SUMMARY");
        $display("Total Test Cases: %0d", total_tests);
        $display("Passed Test Cases: %0d", tests_passed);
        $display("Failed Test Cases: %0d", tests_failed);
        if (tests_failed == 0)
            $display("OVERALL STATUS : PASS");
        else
            $display("OVERALL STATUS : FAIL");
        $finish;
    end
endmodule