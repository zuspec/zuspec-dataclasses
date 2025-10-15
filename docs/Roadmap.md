
# 0.1.0
- Parity with RTL Verilog

# 0.3.0
- Bundle

- Extern components

- Procedural binding
  - Need a way to introspect bind objects

- Functional FSMs

# 0.4.0
- Constant parameterization

- Field annotations

- Template Types
  -> Ease of experimentation
  - Build decoder logic on-the-fly
  - Easier because we are code?
  - Or, need an explicit type model?
  - Can alwqys fall back to generating Python if required

- Functional logic construction
  - Explicit static expansion of recursive functions
  - Use special regions to capture 'logic'
  - May want to provide a library for constructing the
    logic netlist programmatically (OOP)
    -> Need to settle on the appropriate level of description
  - Must be able to distinguish between building and static statements
  -> Allow methods to return object model
  -> Ease of experimentation