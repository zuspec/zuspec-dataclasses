
typedef struct packed {
  bit[31:0]  val;
} reg1_s;

typedef struct packed {
  bit[15:0]  val1;
  bit[15:0]  val2;
} reg2_s;

typedef struct packed {
  reg1_s       r1;
  reg2_s       r2;
} regfile_s;

module regfile(
	input 		clock,
	input 		reset,
	output [31:0] 	val);
  regfile_s   regs;
  reg v1;

  assign val = {regs.r2.val1[3:1], regs[0]};

  always @(posedge clock or posedge reset) begin
    if (reset) begin
      regs.r1.val <= {32{1'b0}};
      regs.r2.val1 <= {16{1'b0}};
      regs.r2.val2 <= {16{1'b0}};
      v1 <= 1'b0;
    end else begin
      regs[31:0] <= regs[31:0] + 1;
      regs.r2.val1 <= regs.r2.val1 + 1;
      v1 <= ~v1;
    end
  end
endmodule

