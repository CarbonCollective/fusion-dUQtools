import logging
from pathlib import Path

from duqtools.config import Config

from .schema import BaseModel

logger = logging.getLogger(__name__)


def init(*, dry_run: bool, config: str, full: bool, force: bool,
         comments: bool, **kwargs):
    """Initialize a brand new config file with all the default values.

    Parameters
    ----------
    dry_run : bool
        Do not make any changes to the file system.
    config : str
        Filename of the config.
    full : bool
        Make a config with all the default values
        (otherwise just selected important ones)
    force : bool
        Overwrite config if it already exists.
    comments : bool
        Description
    **kwargs
        Description

    Deleted Parameters
    ------------------
    comment : bool
        Add comments to the config
    kwargs
        kwargs, optional stuff.

    Raises
    ------
    RuntimeError
        Description
    """
    cfg = Config()
    BaseModel.__init__(cfg)

    logger.debug(cfg)

    config_filepath = Path(config)

    if config_filepath.exists() and not force:
        raise RuntimeError(
            f'Refusing to overwrite existing CONFIG, {config_filepath}, '
            'use --force if you really want to')

    logger.info('Writing default config to %s', config_filepath)

    if full:
        cfg_yaml = cfg.yaml(descriptions=comments)
    else:
        cfg_yaml = cfg.yaml(descriptions=comments,
                            include={
                                'workspace': True,
                                'create':
                                {'dimensions', 'sampler', 'template'},
                                'plot': {'plots'}
                            })

    if not dry_run:
        with open(config_filepath, 'w') as f:
            f.write(cfg_yaml)
