import os
from contextlib import contextmanager
from pathlib import Path

from ._types import PathLike


@contextmanager
def work_directory(path: PathLike):
    """Changes working directory and returns to previous on exit.

    Parameters
    ----------
    path : PathLike
        Temporarily change to this directory.
    """
    prev_cwd = Path.cwd()
    os.chdir(path)
    yield
    os.chdir(prev_cwd)
