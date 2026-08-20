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
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b000;
    #10;
    if (result === (a + b)) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b001;
    #10;
    if (result === (a - b)) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b010;
    #10;
    if (result === (a & b)) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b011;
    #10;
    if (result === (a | b)) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b100;
    #10;
    if (result === (a ^ b)) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b101;
    #10;
    if (result === {a[6:0], 1'b0}) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b110;
    #10;
    if (result === {1'b0, a[7:1]}) $display("PASS");
    else $display("FAIL");
    
    a = 8'h15;
    b = 8'h05;
    opcode = 3'b111;
    #10;
    if (result === (~a)) $display("PASS");
    else $display("FAIL");
    
    $finish;
end

endmodule