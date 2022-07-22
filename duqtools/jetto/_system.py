from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field
from typing_extensions import Literal

from ..models import AbstractSystem
from ..operations import add_to_op_queue
from ._imas_functions import imas_from_jset_input
from ._jset import JettoSettings

if TYPE_CHECKING:
    from ..ids import ImasHandle
    from ..models import WorkDirectory


class JettoSystem(AbstractSystem):
    """This system implements a wrapper around JETTO, which is part of the
    JINTRAC modelling framework for integrated simulation of Tokamaks.

    For more information:

    - G. Cenacchi, A. Taroni, JETTO: A free-boundary plasma transport code,
        JET-IR (1988)
    - M. Romanelli  2014, Plasma and Fusion research 9, 3403023-3403023
    """
    name: Literal['jetto'] = Field('jetto', description='Name of the system.')

    @staticmethod
    @add_to_op_queue('Writing new batchfile for {run_name}')
    def write_batchfile(workspace: WorkDirectory, run_name: str):
        from duqtools.jetto import write_batchfile as jetto_write_batchfile
        return jetto_write_batchfile(workspace, run_name)

    @staticmethod
    @add_to_op_queue('Copying template to {target_drc}')
    def copy_from_template(source_drc: Path, target_drc: Path):
        from duqtools.jetto import copy_files
        return copy_files(source_drc, target_drc)

    @staticmethod
    def imas_from_path(template_drc: Path):

        jset = JettoSettings.from_directory(template_drc)
        source = imas_from_jset_input(jset)
        assert source.path().exists()
        return source

    @staticmethod
    @add_to_op_queue('Updating imas locations of {run}')
    def update_imas_locations(run: Path, inp: ImasHandle, out: ImasHandle):
        jset = JettoSettings.from_directory(run)
        jset_copy = jset.set_imas_locations(inp=inp, out=out)
        jset_copy.to_directory(run)
