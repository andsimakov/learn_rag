# LangFuse v4 tracing is handled by the @observe decorator and get_client().
# Both are imported directly from the top-level `langfuse` package.
# The client reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL
# from the environment automatically — no explicit initialisation needed.
#
# Usage pattern:
#   from langfuse import observe, get_client
#
#   @observe(name="my_operation")            # creates a span in the active trace
#   @observe(as_type="generation")           # marks it as an LLM call in the UI
#   async def my_fn(...): ...
#
#   lf = get_client()
#   lf.set_current_trace_io(input=..., output=...)   # set trace-level I/O
#   lf.update_current_span(...)                      # update current span
#   lf.update_current_generation(...)                # update LLM generation metadata
#   lf.get_current_trace_id()                        # get trace ID for the response
