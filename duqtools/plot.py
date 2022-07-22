import logging

from .config import cfg
from .ids import ImasHandle, get_ids_tree
from .models import WorkDirectory
from .operations import confirm_operations, op_queue

logger = logging.getLogger(__name__)
info, debug = logger.info, logger.debug


@confirm_operations
def plot(*, dry_run, **kwargs):
    """Plot subroutine to create plots from datas."""
    import matplotlib.pyplot as plt
    import numpy as np
    info('Extracting imas data')
    # Gather all results and put them in a in-memory format
    # (they should be small enough)
    profiles = []

    workspace = WorkDirectory.parse_obj(cfg.workspace)
    runs = workspace.runs

    for run in runs:
        imas_loc = ImasHandle.parse_obj(run.data_out)
        info('Reading %s', imas_loc)

        profile = get_ids_tree(imas_loc, 'core_profiles')
        if 'profiles_1d' not in profile:
            logger.warning('No data in entry, skipping...')
            continue

        profiles.append(profile)

    for i, plot in enumerate(cfg.plot.plots):
        info('Creating plot number %04i', i)

        fig, ax = plt.subplots()

        ax.set_title(plot.y)
        ax.set_xlabel(plot.get_xlabel())
        ax.set_ylabel(plot.get_ylabel())

        for j, profile in enumerate(profiles):
            y = profile.flat_fields[plot.y]

            if plot.x:
                x = profile.flat_fields[plot.x]
            else:
                x = np.linspace(0, 1, len(y))

            ax.plot(x, y, label=j)

        ax.legend()
        plotname = f'plot_{i:04d}.png'
        op_queue.add(action=fig.savefig,
                     args=(plotname, ),
                     description=f'Creating plot {plotname}')
