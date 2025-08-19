
# Overview
The user captures model elements using Python dataclass package elements.
Types undergo a transformation process before use. At minimum, all root
types (component, struct, action) must be transformed for proper
operation. In most cases, ports and exports will be transformed as well.
However, this is not absolutely required.

# Primary Goal: Embrace/Extend Python Ecosystem
- Generators and class-library modeling languages typically
use the ecosystem, but do not become a part of it.
- Typical for <tool> to be the root of the environment
  - Integrated pieces as <tool> sees fit
- Want <python> to be root of the environment in this case, and
  have various <tool>s integrated under that umbrella.

