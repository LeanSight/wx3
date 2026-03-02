import click
import dataclasses
from pathlib import Path
from typing import Optional, Dict, Any, Type
from wx41.context import PipelineConfig
from wx41.pipeline import MediaOrchestrator
from wx41.steps import get_all_steps, StepInfo

def create_cli():
    # Ensure all steps are loaded
    all_steps = get_all_steps()
    
    @click.command(context_settings={"help_option_names": ["-h", "--help"]})
    @click.argument("src", type=click.Path(exists=True, path_type=Path))
    @click.option("--dry-run", is_flag=True, help="Simulate execution without running steps")
    @click.option("--force", is_flag=True, help="Force re-execution even if outputs exist")
    @click.option("--state-path", type=click.Path(path_type=Path), help="Path to save/restore state for interruption")
    @click.pass_context
    def main(ctx, src: Path, dry_run: bool, force: bool, state_path: Optional[Path], **kwargs):
        """Audio pipeline CLI with dynamic step configuration."""
        settings = {}
        
        for name, info in all_steps.items():
            if not info.config_class:
                continue
                
            # Collect arguments for this step
            step_args = {}
            cfg_fields = {f.name: f for f in dataclasses.fields(info.config_class)}
            
            # Check for --no-{step}
            enabled = True
            if info.optional:
                no_flag = f"no_{name}"
                if kwargs.get(no_flag):
                    enabled = False
            
            # Extract step-specific options (e.g., --transcribe-backend -> transcribe_backend)
            prefix = f"{name}_"
            for key, value in kwargs.items():
                if key.startswith(prefix):
                    field_name = key[len(prefix):]
                    if field_name in cfg_fields:
                        if value is not None:
                            step_args[field_name] = value
            
            # Instantiate config
            try:
                cfg = info.config_class(**step_args)
                if hasattr(cfg, 'enabled'):
                    cfg = dataclasses.replace(cfg, enabled=enabled)
                settings[name] = cfg
            except TypeError as e:
                click.echo(f"Error configuring step '{name}': {e}", err=True)
                ctx.exit(1)

        config = PipelineConfig(settings=settings, force=force)
        orchestrator = MediaOrchestrator(config, [], state_path=state_path)
        orchestrator.run(src, dry_run=dry_run)

    # Dynamically add options to the command
    for name, info in all_steps.items():
        if info.optional:
            main = click.option(
                f"--no-{name}", 
                is_flag=True, 
                default=False, 
                help=f"Disable {name} step. {info.description}"
            )(main)
            
        if info.config_class:
            for field in dataclasses.fields(info.config_class):
                if field.name in ('enabled', 'output_keys'):
                    continue
                
                opt_name = f"--{name}-{field.name.replace('_', '-')}"
                
                # Default values
                default = None
                if field.default is not dataclasses.MISSING:
                    default = field.default
                
                help_text = f"Config for {name} step: {field.name}"
                
                main = click.option(
                    opt_name,
                    default=default,
                    type=field.type if isinstance(field.type, type) and field.type in (str, int, float, bool, Path) else None,
                    help=help_text
                )(main)
                
    return main

main = create_cli()

if __name__ == "__main__":
    main()
