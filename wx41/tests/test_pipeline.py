from pathlib import Path
from dataclasses import replace
import pytest
from wx41.pipeline import Pipeline, NamedStep
from wx41.context import PipelineContext

class TestPipelineGenericCore:
    def test_automatic_output_registration(self, tmp_path):
        # 1. Setup
        # El step no construye el path, lo recibe ya configurado (Modularidad)
        def dummy_logic(ctx, my_out_path: Path):
            my_out_path.write_text("hecho", encoding="utf-8")
            return ctx # El step solo retorna el ctx, no gestiona el mapa de outputs

        # El descriptor del step define cómo se calcula su output
        step_name = "normalize"
        suffix = "_nom.wav"
        
        # Factoría de paths (encapsulada en el NamedStep)
        def get_out(ctx): return ctx.src.parent / f"{ctx.src.stem}{suffix}"

        # Componemos el step inyectando la lógica y el generador de path
        step = NamedStep(
            name=step_name,
            fn=lambda ctx: dummy_logic(ctx, get_out(ctx)),
            output_fn=get_out
        )

        pipeline = Pipeline(steps=[step], observers=[])
        ctx_initial = PipelineContext(src=tmp_path / "audio.m4a")

        # 2. Execution
        ctx_final = pipeline.run(ctx_initial)

        # 3. Verification
        # El pipeline debe haber registrado el output AUTOMATICAMENTE por el nombre del step
        assert step_name in ctx_final.outputs, f"Step '{step_name}' no registrado en outputs"
        assert ctx_final.outputs[step_name].name == "audio_nom.wav"
        assert ctx_final.outputs[step_name].exists()
