from pathlib import Path
import dataclasses
import pytest
from wx41.pipeline import Pipeline, NamedStep
from wx41.context import PipelineContext

class TestPipelineGenericCore:
    def test_automatic_output_registration(self, tmp_path):
        step_name = "normalize"
        suffix = "_nom.wav"
        out_path = tmp_path / f"audio{suffix}"

        def step_fn(ctx):
            out_path.write_text("hecho", encoding="utf-8")
            new_outputs = {**ctx.outputs, step_name: out_path}
            return dataclasses.replace(ctx, outputs=new_outputs)

        def output_fn(ctx):
            return {step_name: ctx.src.parent / f"{ctx.src.stem}{suffix}"}

        step = NamedStep(name=step_name, fn=step_fn, output_fn=output_fn)
        pipeline = Pipeline(steps=[step], observers=[])
        ctx_initial = PipelineContext(src=tmp_path / "audio.m4a")

        ctx_final = pipeline.run(ctx_initial)

        assert step_name in ctx_final.outputs, f"Step '{step_name}' no registrado en outputs"
        assert ctx_final.outputs[step_name].name == f"audio{suffix}"
        assert ctx_final.outputs[step_name].exists()
