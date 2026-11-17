"""Test doubles for the Anthropic client. Real code paths, fake network."""
import copy
from types import SimpleNamespace


def text_block(s):
    return SimpleNamespace(type="text", text=s)


def tool_block(id, name, input):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def thinking_block():
    return SimpleNamespace(type="thinking", thinking="", signature="sig")


def resp(blocks, stop_reason, in_tok=100, out_tok=20, cache_read=0):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok,
                                                 cache_read_input_tokens=cache_read,
                                                 cache_creation_input_tokens=0))


class _Messages:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kw):
        self.outer.calls.append({**kw, "messages": copy.deepcopy(kw["messages"])})
        if callable(self.outer.responses):
            return self.outer.responses(len(self.outer.calls))
        return self.outer.responses.pop(0)


class FakeClient:
    """`responses` is a list consumed in order, or a callable(call_number) -> response."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.messages = _Messages(self)
