def pytest_ignore_collect(path, config):
    """Ignore the special 'nul' device file that confuses pytest on Windows."""
    return getattr(path, "basename", None) == "nul"
