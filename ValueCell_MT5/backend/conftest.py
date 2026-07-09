def pytest_ignore_collect(collection_path, config):
    """Ignore the special 'nul' device file that confuses pytest on Windows."""
    return getattr(collection_path, "name", None) == "nul"
