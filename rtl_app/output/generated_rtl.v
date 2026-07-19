module comparator8(
  input [7:0] a,
  input [7:0] b,
  output equal,
  output greater,
  output less
);

always @(*) begin
  case (1)
    a == b: begin
      equal = 1'b1;
      greater = 1'b0;
      less = 1'b0;
    end
    a > b: begin
      equal = 1'b0;
      greater = 1'b1;
      less = 1'b0;
    end
    default: begin
      equal = 1'b0;
      greater = 1'b0;
      less = 1'b1;
    end
  endcase
end

endmodule