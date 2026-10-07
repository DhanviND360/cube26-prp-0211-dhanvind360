"""
CUBE PREP Manager Agent Package.
Production-grade package compliance inspection agent for FBA intake.
"""

from agent.prep_agent import PrepManagerAgent
from agent.config import settings

__version__ = "3.0.0"
__all__ = ["PrepManagerAgent", "settings"]
