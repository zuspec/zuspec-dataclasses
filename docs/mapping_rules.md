
# Assumption
Assume the zuspec.dataclasses package is imported as `zdc`.

All Zuspec classes must be decorated with @zdc.dataclass.

# Conventions
Mappings to the datamodel are captured using the following
notation:

<Type>:{<fieldname>:<fieldvalue|fieldcontent>}. 

By default, a datamodel element is like an BNF. It states 
what is legal and possible. For example, a list of base
types can be populated by objects of the base type as well
as any sub-types. The datamodel element may capture additional
restrictions.


# Struct
A struct is a Python class that has zdc.Struct as a direct or
indirect base. A struct may have fields, constraints, and 
non-virtual methods. A struct is a plain-data type, in that
it does not convey virtual type information. This means that 
a struct-type field cannot be converted to a sub-type. 

## Example
Example:
```python
```

## Data-model mapping
A struct type maps to 

# Int Type
Int types are mapped to dm.DataTypeInt with an unspecified 
(-1) width. When annotated with S() or U(), the width and
specified sign is specified.

```python
@zdc.dataclass
class MyC(object):
    a : int = zdc.field(default=0)
    b : Annotated[int,zdc.U(32)] = zdc.field(default=0)
```

The type of field `a` is DataTypeInt:{width:-1,signed:True}. 
The type of field `b` is DataTypeInt:{width:32,signed;:False}.

# Fields
