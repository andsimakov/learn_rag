# Single import point for LangFuse tracing utilities.
# The client reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL
# from the environment automatically — no explicit initialisation needed.
#
# Usage:
#   @observe(name="my_operation")            # creates a span in the active trace
#   @observe(as_type="generation")           # marks it as an LLM call in the UI
#   async def my_fn(...): ...
#
#   lf = get_client()
#   lf.set_current_trace_io(input=..., output=...)
#   lf.update_current_generation(model=..., input=..., output=..., usage_details=...)
#   lf.get_current_trace_id()
from langfuse import get_client, observe

__all__ = ["get_client", "observe"]
