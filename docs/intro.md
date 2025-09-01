
# Zuspec Language Overview

Zuspec is a language focused on modeling digital hardware
designs at multiple levels of abstraction -- from an 
abstract behavioral model down to register transfer level (RTL).
Multiple distinct implementations can be derived from a Zuspec
model to address various points on the performance / fidelity curve.

Zuspec is a Python-based language, which means that it is embedded in
Python and adopts Python syntax, but applies special semantic rules 
to specified portions of the description. 

Let's look at an example:

```python3
# Counter example
import zuspec.dataclasses as zdc

@zdc.dataclass
class Counter(zdc.Component):
    clock : zdc.Bit = zdc.input()
    reset : zdc.Bit = zdc.input()
    count : zdc.Bit[32] = zdc.output()

    @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
    def _inc(self):
        if self.reset:
            self.count = 0
        else:
            self.count += 1
```

Note that we follow the Python `dataclasses` pattern

- **Component** - Components are structural elements, equivalent to 
Verilog modules and SystemC or PSS components.
- **Signal Ports** - 
- **Sync** - Marks a method as being activated on a clock or 
reset edge. The semantics of code in the method are behavioral.
However, output variables only change at clock edge (ie Verilog 
non-blocking assignment).

# Interaction with Tools

Zuspec defines a language, which means that tools must have a way to
operate on a Zuspec description. The `zuspec.dataclasses.api` 
package provides a visitor that iterates over key features of a Zuspec
model. 



# Abstracted Messaging (base on which TLM was built)
- field of <Api> = port()
- field of <Api> = export(bind here)
- build/connect process ensures logical result

=> Really clumsy to do in C++ ; impossible in SV
=> Really easy to describe in Python. Several (more-complex)
   ways to implement.

Goal: capture specification not implementation

=> Leverage association rules
  - associate with nearest timebase provider
  - association control
  => Use association properties for static APIs?
  Api::C -> nearest association -- which might be top
=> Assess

Pool is an association:
pool<T> forms an association with any input<T>, output<T>
- Filter rule: associate anything?
-> Each provider 
-> Pushing down match rules
--> component must gather providers
-> Error if multiple rules match
-> associate() -> Returns a map to add to the stack
--> Upper must win...

-> Two stacks: natural ; override
--> Check override stack first
--> Check natural stack second

=> Do need something for binding
-> That's impl specific...
-> Transform -> map 'std' to <provider>
=> Top-level component has required associatians
  -> Use for an external API (vs being built-in)

=> Must identify base types assumed to be tool-supported
  -> Ex: tool that doesn't support registers must be flagged
  -> Contract of 'tool recognizes these core constructs'
  --> This is extensible. Libraries can flag their base classes
    as needing to be recognized

Pure: having no data -> Really talking about abstract class?

Core language support (parser) must provide elab and linking
facilities. 
- Build associations maps

Alias methods to services?
print() <-> std.print()
- Certain implementations can require a method to be
  a struct member

# Creating a component instance triggers a scan for required services
- If a component has associated actions, then 
-> Forall actions that match this type, check for 
--> memory and resource claims
--> Buffer/State/

Violation of scheduling rules can be detected at runtime:
-> Parallel must check for duplicate targets 
-> Actions must expose associations
-> State is a single resource with completion semantics

Service Provider
Resource Provider <-> Pool is also a resource provider

forall: 

with forall(select) as fp:
  constraints

# Locating the claim
- up- or -down associative
- optional (0,1), single, or multi
- Use a dedicated 

Associations can be up- or down-associative.
- comp is a down-associative 
- aspace (claim), pool (lock/share, input/output) is 

# Organizing assiciations
- Provider / Client
- Is different from port binding
-> Provider instances add to this component's scope
-> Push an override 
--> Provider stack searched in reverse
--> Override stack searched in order
--> Bind acts as an override(!)

action input/output ports are consumers

Associate Providers

# Associating features with methods

# Structs

# Components
- init
- associate_down (maybe: available in build?)
- build
- associate_up
- bind / connect

=> Can avoid repeated constructions

Type model
- Type variants expanded
- Cut-off evaluation ASAP

-> Component is left with
  - bindmap of associations
    - claim -> src
  - bindmap of connections
  - 

# Actions
- How 
- Associate themselves with 0+ components
<path>.execute(ActionT)
-> 
-> When a type is not valid on a subtree, it is not valid for all members 

# Services
- Individual connection
- Specific provider is secondary to the existence of a provider
-> Config is a service
--> Can distribute as needed
-> Config can also be passed down as a const

-> Service-provider component
--> Provide access for programmatic build?
--> Need a point where 
--> Have to be 'bottom-up' build

- bind is either p2p or a match pattern
- 

# Covergroups


# What about local providers / consumers?
- assumes 
- functions support providers as well?
  - Claims establish local deps
  - Can roll-up 
- How to identify? By type handle
- action

# External API to provider functionality
- 

# Generative Features
- Create exec blocks with parameterized co-routines
- Create sub-components / sub-fields

# Profiles
- Language must define sets of supported features
  - Synthesizable RTL
  - Behavioral RTL
  - Behavioral HVL
  - Portable TLM
  - Portable PV
  - Portable Test
  - Python
  - Static/Formal

  Run checks in terms of profiles

  - A profile is a concept.
  - Always described in human-readable text
  - Identified by a class
  - Class provides a validator
    - Validate decorated class with respect to its profile (always specific to most-restrictive type)
    - 

  - Profiles are composed by 