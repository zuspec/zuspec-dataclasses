import os


def skills():
    """agent.skills entry-point: return the directory containing SKILL.md."""
    return [os.path.dirname(os.path.abspath(__file__))]
