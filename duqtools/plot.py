import logging

import matplotlib.pyplot as plt
import numpy as np

from duqtools.ids import ImasLocation
from duqtools.jetto import JettoSettings

from .config import cfg

logger = logging.getLogger(__name__)
info, debug = logger.info, logger.debug


def plot(**kwargs):
    """Plot subroutine to create plots from datas.

    Parameters
    ----------
    kwargs :
        kwargs
    """
    info('Extracting imas data')
    # Gather all results and put them in a in-memory format
    # (they should be small enough)
    profiles = []
    jset_files = list(cfg.workspace.path.glob('*/*.jset'))

    for jset_file in jset_files:
        jset = JettoSettings.from_file(jset_file)
        imas_loc = ImasLocation.from_jset_output(jset)
        profiles.append(imas_loc.get_ids_tree('core_profiles'))

    for i, plot in enumerate(cfg.plot.plots):
        info('Creating plot number %04i' % i)
        for j, profile in enumerate(profiles):
            y = profile.flat_fields[plot.y]

            if plot.x:
                x = profile.flat_fields[plot.x]
            else:
                x = np.linspace(0, 1, len(y))

            plt.xlabel(plot.get_xlabel())
            plt.ylabel(plot.get_ylabel())

            plt.plot(x, y, label=j)

        plt.legend()
        plt.savefig('plot_%04i.png' % i)
        plt.close()