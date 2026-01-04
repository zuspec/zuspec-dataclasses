
# Data Types

## Class
Object-oriented Class type. Supports virtual methods and data.

## Struct
Supports data and non-virtual methods. In other words, an instance
of a struct conveys only data and omit knowledge of a virtual table. 
Data uses the same alignment and packing rules as C when targeting
a byte-oriented memory.

## PackedStruct
Supports data and non-virtual methods. Data is bitwise packed, and
has no automatic padding.

# Modeling Types

## Pools
Pools hold elements that are accessed by 'claim'. This is done
to abstract providers from consumers. Claims are 'bound' to a
pool, either declaratively or procedurally.
- Pools and declarative claims can be declared on components
- Pools and procedural claims may be declared in procedural
  regions
- [Future] Declarative claims can be specified on Actions

Pools and claims are used to model:
- Distribution of resources
- Manage resource contention (ie arbitration)
- [Future] Manage on-demand element creation for scenarios

- How a pool is populated
  - Statically -- either with a bound list or constructed
  - 

are identified
  - They aren't. All are equal
    - Actually, in all cases it would be useful to have a uid for the claimant
      - Form based on code location?
  - Statically - claim instances specify claim traits
  - Dynamically - 
- How pool distributes elements to claimants
  - Capabilities are linked with claimant identification
    - If claimants specify extra 
- Supported acquisition modes for elements
  - lock/share -- really, it's always share with optional lock
  - 
- Is a single-resource pool the degenerate case of State?
-

### 

# Communication

## Port/Export
Ports and exports provide a mechanism to form a method-based 
communication channel. The type of a port or export shall be
a protocol-based class (ie pure-virtual interface) or a 
Callable. 

## Input/Output
Inputs and outputs provide a mechanism to support data-based
communication. These are typically used along with 'comb' 
and/or 'sync' evaluation blocks. 

# Declarative Scheduled Behaviors

Zuspec supports action-based scheduled activities
- Already have pools -- simply need to change how acquisition happens
- Have 'inferrence' covered -- already have a mechanism to fill
  a pool. 
  -> That's the overlap... Procedural code can 'infer' an activity
  by claiming a data item.
  -> Assume a claim is always declarative for flexibility?

## Action
An Action is a Class-like type that supports virtual methods. An action
has a built-in `claim` on a component type that is resolved as part of
the binding process that occurs when the action is evaluated. Every
action has a 'body' method, which is the default entrypoint to 
an action's activity (whether leaf or compound). Actions may override
the default entrypoint to add required parameters or customize the 
behavior. Actions may declare additional `activity`-decorated 
activty entry-point methods.

-> Hmm... May conflict with binding?
-> Want body method to be invoked after setup (randomization+binding)
   have occurred. 

action.traverse(self.comp, a, lambda: a.activity(1, 2, 3)):
  a.activity(1, 2, 3, 4)

action.traverse(self.comp, a)

self<action>.traverse(a) -> 
self<action>.traverse(A) -> handle
self<action>.traverse(lambda : A.entry)
self<action>.run(a)


# Randomization

## Constraints

Constraints are methods decorated with the `constraint` decorator. 
Decorators come in two flavors: fixed (default) and generic. A
fixed constraint always applied. A generic constraint only applies
once referenced/invoked from a constraint block.

Constraints may be placed in all composite types. 
- Components are randomized as part of the elaboration process
  - Automatic?
- Structs and Classes may be randomized using the 'randomize' statement

# Roadmap

## Introduction
- Lock
- API classes
- Comb and Sync execs
- Registers

## Randomization and Coverage
- Constraints
- Randomization statement
- Covergroups

## 
- Pool as a resource arbiter

## Scenarios
- Pool
- Action

