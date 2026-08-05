module testbench;
reg [7:0] a;
reg [7:0] b;
reg [2:0] opcode;
wire [7:0] result;

alu8 uut (
    .a(a),
    .b(b),
    .opcode(opcode),
    .result(result)
);

initial begin
    $monitor("a = %h, b = %h, opcode = %h, result = %h", a, b, opcode, result);
    a = 8'h00; b = 8'h00; opcode = 3'b000; #10;
    if (result !== 8'h00) $display("FAIL: addition 0+0"); else $display("PASS: addition 0+0");
    
    a = 8'h05; b = 8'h03; opcode = 3'b000; #10;
    if (result !== 8'h08) $display("FAIL: addition 5+3"); else $display("PASS: addition 5+3");
    
    a = 8'h05; b = 8'h03; opcode = 3'b001; #10;
    if (result !== 8'h02) $display("FAIL: subtraction 5-3"); else $display("PASS: subtraction 5-3");
    
    a = 8'h05; b = 8'h03; opcode = 3'b010; #10;
    if (result !== 8'h01) $display("FAIL: and 5&3"); else $display("PASS: and 5&3");
    
    a = 8'h05; b = 8'h03; opcode = 3'b011; #10;
    if (result !== 8'h07) $display("FAIL: or 5|3"); else $display("PASS: or 5|3");
    
    a = 8'h05; b = 8'h03; opcode = 3'b100; #10;
    if (result !== 8'h06) $display("FAIL: xor 5^3"); else $display("PASS: xor 5^3");
    
    a = 8'h05; opcode = 3'b101; #10;
    if (result !== 8'h0a) $display("FAIL: left shift 5<<1"); else $display("PASS: left shift 5<<1");
    
    a = 8'h05; opcode = 3'b110; #10;
    if (result !== 8'h02) $display("FAIL: right shift 5>>1"); else $display("PASS: right shift 5>>1");
    
    a = 8'h05; opcode = 3'b111; #10;
    if (result !== 8'hfa) $display("FAIL: not ~5"); else $display("PASS: not ~5");
    
    $finish;
end

endmodule