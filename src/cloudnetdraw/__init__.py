"""
CloudNet Draw - Azure VNet topology visualization tool
"""
try:
    from importlib.metadata import version
    __version__ = version("cloudnetdraw")
except Exception:
    __version__ = "dev"