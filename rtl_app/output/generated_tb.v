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
    if (result !== 8'h00) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h03; opcode = 3'b000; #10;
    if (result !== 8'h08) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h03; opcode = 3'b001; #10;
    if (result !== 8'h02) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h03; opcode = 3'b010; #10;
    if (result !== 8'h01) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h03; opcode = 3'b011; #10;
    if (result !== 8'h07) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h03; opcode = 3'b100; #10;
    if (result !== 8'h06) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h00; opcode = 3'b101; #10;
    if (result !== 8'h0A) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h00; opcode = 3'b110; #10;
    if (result !== 8'h02) $display("FAIL"); else $display("PASS");
    
    a = 8'h05; b = 8'h00; opcode = 3'b111; #10;
    if (result !== 8'hFA) $display("FAIL"); else $display("PASS");
    
    $finish;
end

endmodule