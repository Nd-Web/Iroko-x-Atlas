"""
Semantic Kernel compatibility shim.
Uses real SK when available, falls back to no-op decorator for scaffold testing.
"""
try:
    from semantic_kernel.functions import kernel_function
    from semantic_kernel import Kernel
    SK_AVAILABLE = True
except Exception:
    SK_AVAILABLE = False
    Kernel = object

    def kernel_function(description: str = "", **kwargs):
        """No-op decorator when SK is not available."""
        def decorator(func):
            func._sk_description = description
            return func
        return decorator
