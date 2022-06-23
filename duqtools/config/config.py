from __future__ import annotations

import logging
from getpass import getuser
from pathlib import Path
from typing import List

import yaml
from pydantic import DirectoryPath, validator

from duqtools._types import PathLike

from ._runs import Run, Runs
from .basemodel import BaseModel
from .create import CreateConfig
from .plot import PlotConfig
from .status import StatusConfig
from .submit import SubmitConfig

logger = logging.getLogger(__name__)


class WorkDirectory(BaseModel):
    root: DirectoryPath = f'/pfs/work/{getuser()}/jetto/runs/'

    @property
    def cwd(self):
        cwd = Path.cwd()
        if not cwd.relative_to(self.root):
            raise IOError(
                f'Work directory must be a subdirectory of {self.root}')
        return cwd

    @property
    def subdir(self):
        """Get subdirectory relative to root."""
        return self.cwd.relative_to(self.root)

    @validator('root')
    def resolve_root(cls, v):
        return v.resolve()

    @property
    def runs_yaml(self):
        """Location of runs.yaml."""
        return self.cwd / 'runs.yaml'

    @property
    def runs(self) -> List[Run]:
        """Get a list of the runs currently created from this config."""
        runs_yaml = cfg.workspace.runs_yaml

        if not runs_yaml.exists():
            raise IOError('Cannot find %s, therefore cannot show the status' %
                          runs_yaml)

        with open(runs_yaml) as f:
            mapping = yaml.safe_load(f)
            return Runs.parse_obj(mapping)


class Config(BaseModel):
    """Config class containing all configs, is a singleton and can be used with
    import duqtools.config.Config as Cfg Cfg().<variable you want>"""

    _instance = None

    plot: PlotConfig = PlotConfig()
    submit: SubmitConfig = SubmitConfig()
    create: CreateConfig = CreateConfig()
    status: StatusConfig = StatusConfig()
    workspace: WorkDirectory = WorkDirectory()

    def __new__(cls, *args, **kwargs):
        # Make it a singleton
        if not Config._instance:
            Config._instance = object.__new__(cls)
        return Config._instance

    def read(self, filename: PathLike):
        """Read config from file."""
        with open(filename, 'r') as f:
            datamap = yaml.safe_load(f)
            logger.debug(datamap)
            BaseModel.__init__(self, **datamap)


cfg = Config()
