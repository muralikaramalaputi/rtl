module alu8(
    input  [7:0] a,
    input  [7:0] b,
    input  [2:0] opcode,
    output reg [7:0] result
);
    always @(*) begin
        case (opcode)
            3'b000: result = a + b;          // Addition
            3'b001: result = a - b;          // Subtraction
            3'b010: result = a & b;          // AND
            3'b011: result = a | b;          // OR
            3'b100: result = a ^ b;          // XOR
            3'b101: result = a << 1;         // Left Shift by 1
            3'b110: result = a >> 1;         // Right Shift by 1 (logical)
            3'b111: result = ~a;             // NOT A
            default: result = 8'b0;          // Default case
        endcase
    end
endmodule