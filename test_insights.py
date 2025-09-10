# Compatibility shim for tests expecting test_insights module.
from simple_dashboard import SimpleProgressMonitor  # re-export

__all__ = ["SimpleProgressMonitor"]
