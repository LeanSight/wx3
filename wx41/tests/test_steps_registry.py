from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from pathlib import Path
import pytest


def test_step_info_holds_metadata():
    from wx41.steps import StepInfo
    
    @dataclass(frozen=True)
    class DummyConfig:
        output_keys: tuple = ("dummy_key",)
        
    info = StepInfo(
        name="dummy",
        config_class=DummyConfig,
        step_fn=lambda ctx, cfg: ctx,
        optional=True,
        description="A dummy step"
    )
    
    assert info.name == "dummy"
    assert info.optional is True
    assert info.config_class == DummyConfig
    assert info.description == "A dummy step"

def test_register_step_uses_step_info():
    from wx41.steps import register_step, get_step_info
    
    def dummy_fn(ctx, cfg): return ctx
    
    register_step(
        name="test_step",
        step_fn=dummy_fn,
        optional=True,
        description="test description"
    )
    
    info = get_step_info("test_step")
    assert info.name == "test_step"
    assert info.step_fn == dummy_fn
    assert info.optional is True
    assert info.description == "test description"
