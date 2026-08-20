module alu8 (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] opcode,
    output reg  [7:0] result
);

    always @(*) begin
        case (opcode)
            3'b000:  result = a + b;
            3'b001:  result = a - b;
            3'b010:  result = a & b;
            3'b011:  result = a | b;
            3'b100:  result = a ^ b;
            3'b101:  result = a << b[2:0];
            3'b110:  result = a >> b[2:0];
            3'b111:  result = ~a;
            default: result = 8'h00;
        endcase
    end

endmodule