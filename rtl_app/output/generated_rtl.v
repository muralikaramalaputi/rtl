module alu8(
    input [7:0] a,
    input [7:0] b,
    input [2:0] opcode,
    output [7:0] result
);

reg [7:0] result_reg;

always @(*)
begin
    case (opcode)
        3'b000: result_reg = a + b;
        3'b001: result_reg = a - b;
        3'b010: result_reg = a & b;
        3'b011: result_reg = a | b;
        3'b100: result_reg = a ^ b;
        3'b101: result_reg = a << 1;
        3'b110: result_reg = a >> 1;
        3'b111: result_reg = ~a;
        default: result_reg = 8'b0;
    endcase
end

assign result = result_reg;

endmodule