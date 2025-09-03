
# Parse AST
- Captures lexical and logical relationships
- Very source centric
- Does capture (?) things like precedence?

# Model-Semantic AST
- Captures intent of 

# Story
- User captures modeling intent in Python with special conventions
  - Identify classes with significance via base class
  - Classes are `dataclass` classes
  - Identify significant class members with decorators
- Core injection point is a type factory
  - Accept DSL type, return Python type

Need to be able to have a Python implementation for everything we do.
Need infrastructure to iterate over classes to:
  - Construct a pure-Python class with infrastructure attached to
    implement executable semantics. Not always possible.
  - Construct a semantic type model for use with other tools
    - Might be used as an implementation of the pure-python class
    - Might be used on its own to derive an independent 
      implementation based on the class API

  -> Should be able to stack generators such that we can mix 
    at the right level.
    -> Point of bounding at a component 
       -> Subtree may have <impl> while sibling has <impl2>

- Package has a default type factory / type transformer
  - Allows use of a specific element standalone (eg Type(...))
- Several type implemenetations may be formed
- Tools are injected at several levels
  - Package has a default 

# User -- extensible modeling features
  - Ensure we have a way to extend capabilities
  - Use / Replace 
  - In Python, maybe delegate is better?
  - Base class is a 