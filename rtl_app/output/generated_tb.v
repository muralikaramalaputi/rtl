module tb_comparator8;
reg [7:0] a;
reg [7:0] b;
wire equal;
wire greater;
wire less;

comparator8 uut (
  .a(a),
  .b(b),
  .equal(equal),
  .greater(greater),
  .less(less)
);

initial begin
  $monitor("a = %h, b = %h, equal = %b, greater = %b, less = %b", a, b, equal, greater, less);
  a = 8'h00; b = 8'h00; #10;
  if (equal === 1'b1 && greater === 1'b0 && less === 1'b0) $display("PASS");
  else $display("FAIL");
  
  a = 8'h10; b = 8'h00; #10;
  if (equal === 1'b0 && greater === 1'b1 && less === 1'b0) $display("PASS");
  else $display("FAIL");
  
  a = 8'h00; b = 8'h10; #10;
  if (equal === 1'b0 && greater === 1'b0 && less === 1'b1) $display("PASS");
  else $display("FAIL");
  
  a = 8'hFF; b = 8'hFF; #10;
  if (equal === 1'b1 && greater === 1'b0 && less === 1'b0) $display("PASS");
  else $display("FAIL");
  
  a = 8'h10; b = 8'h20; #10;
  if (equal === 1'b0 && greater === 1'b0 && less === 1'b1) $display("PASS");
  else $display("FAIL");
  
  a = 8'h20; b = 8'h10; #10;
  if (equal === 1'b0 && greater === 1'b1 && less === 1'b0) $display("PASS");
  else $display("FAIL");
  
  $finish;
end

endmodule