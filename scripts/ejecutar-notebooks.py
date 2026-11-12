"""Ejecuta los tres laboratorios con el intérprete del proyecto; conserva los originales."""

import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
out = root / ".local/notebooks"
out.mkdir(parents=True, exist_ok=True)
os.environ["PATH"] = os.pathsep.join(
    [str(Path(sys.executable).parent), os.environ["PATH"]]
)
for source in sorted((root / "notebooks").glob("*.ipynb")):
    notebook = nbformat.read(source, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=240,
        kernel_name="python3",
        resources={"metadata": {"path": str(root)}},
    )
    client.execute()
    nbformat.write(notebook, out / source.name)
    print(f"OK  {source.name}", flush=True)
