from __future__ import annotations
import importlib.util
import inspect
from pathlib import Path
from typing import Any
from .models import PlaybookSpec
from .sdk.base import TypedPlaybook
from .types import PlaybookCategory

class CustomPlaybookLoader:
    """
    Dynamically loads, statically validates, and compiles user-authored
    Python playbooks from the custom_playbooks/ directory.
    """
    def __init__(self, custom_dir: str | Path = "./custom_playbooks"):
        self.custom_dir = Path(custom_dir)
        self.custom_dir.mkdir(parents=True, exist_ok=True)

    def load_custom_playbooks(self) -> list[PlaybookSpec]:
        loaded_specs: list[PlaybookSpec] = []
        if not self.custom_dir.exists():
            return loaded_specs

        for file_path in sorted(self.custom_dir.glob("*.py")):
            if file_path.name.startswith("__"):
                continue
            try:
                specs = self.load_playbook_from_file(file_path)
                loaded_specs.extend(specs)
            except Exception as e:
                print(f"[CUSTOM-LOADER] Error loading custom playbook {file_path.name}: {e}")

        return loaded_specs

    def load_playbook_from_file(self, file_path: Path) -> list[PlaybookSpec]:
        module_name = f"custom_playbook_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load module spec from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        results: list[PlaybookSpec] = []
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, TypedPlaybook) and cls is not TypedPlaybook:
                instance = cls()
                # Static category validation
                cat = getattr(instance, "category", None)
                valid_categories = [c.value for c in PlaybookCategory] + list(PlaybookCategory)
                if cat not in valid_categories and str(cat) not in valid_categories:
                    raise ValueError(
                        f"Playbook class '{name}' has invalid category '{cat}'. "
                        f"Must be a valid PlaybookCategory: {[c.value for c in PlaybookCategory]}"
                    )
                pb_spec = instance.to_spec()
                results.append(pb_spec)

        return results

    def save_and_compile(self, filename: str, code: str) -> PlaybookSpec:
        """
        Saves user-authored code to a .py file, verifies types statically,
        and returns the compiled PlaybookSpec.
        """
        if not filename.endswith(".py"):
            filename += ".py"

        target_file = self.custom_dir / filename
        target_file.write_text(code, encoding="utf-8")

        specs = self.load_playbook_from_file(target_file)
        if not specs:
            target_file.unlink(missing_ok=True)
            raise ValueError(f"No valid TypedPlaybook subclass found in {filename}")

        return specs[0]
