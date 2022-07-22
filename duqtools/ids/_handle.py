from __future__ import annotations

import logging
from contextlib import contextmanager
from getpass import getuser
from pathlib import Path

from ..operations import add_to_op_queue
from ..schema import ImasBaseModel
from ._copy import copy_ids_entry
from ._imas import imas, imasdef

logger = logging.getLogger(__name__)

PATH_TEMPLATE = ('/afs/eufus.eu/user/g/{user}/public/imasdb/{db}'
                 '/3/0/ids_{shot}{run:04d}{suffix}')
SUFFIXES = (
    '.datafile',
    '.characteristics',
    '.tree',
)


def _patch_str_repr(obj: object):
    """Reset str/repr methods to default."""
    import types

    def true_repr(x):
        type_ = type(x)
        module = type_.__module__
        qualname = type_.__qualname__
        return f'<{module}.{qualname} object at {hex(id(x))}>'

    obj.__str__ = types.MethodType(true_repr, obj)  # type: ignore
    obj.__repr__ = types.MethodType(true_repr, obj)  # type: ignore


class ImasHandle(ImasBaseModel):

    def path(self) -> Path:
        """Return location as Path."""
        return Path(
            PATH_TEMPLATE.format(user=self.user,
                                 db=self.db,
                                 shot=self.shot,
                                 run=self.run,
                                 suffix=SUFFIXES[0]))

    def exists(self) -> bool:
        """Return true if the directory exists.

        Returns
        -------
        bool
        """
        path = self.path()
        return all(path.with_suffix(sf).exists() for sf in SUFFIXES)

    def copy_ids_entry_to(self, destination: ImasHandle):
        """Copy ids entry to given destination.

        Parameters
        ----------
        destination : ImasHandle
            Copy data to a new location.
        """
        copy_ids_entry(self, destination)

    @add_to_op_queue('Removing {self}')
    def delete(self):
        """Remove data from entry."""

        # ERASE_PULSE operation is yet supported by IMAS as of June 2022
        path = self.path()
        for suffix in SUFFIXES:
            to_delete = path.with_suffix(suffix)
            logger.debug('Removing %s', to_delete)
            try:
                to_delete.unlink()
            except FileNotFoundError:
                logger.warning('%s does not exist', to_delete)

    def copy_ids_entry_to_run(self, *, run: int) -> ImasHandle:
        """Copy ids entry to destination with given run number.

        The user is set to the current user, because we don't
        have access to write elsewhere.

        Parameters
        ----------
        run : int
            Run number of the target location.

        Returns
        -------
        destination : ImasHandle
            Returns the destination.
        """
        user = getuser()
        destination = self.copy(update={'run': run, 'user': user})
        self.copy_ids_entry_to(destination)
        return destination

    def get(self, key: str = 'core_profiles', **kwargs):
        """Get data from IDS entry.

        Parameters
        ----------
        key : str, optional
            Name of profiles to open.
        **kwargs
            These keyword parametes are passed to `ImasHandle.open()`.

        Returns
        -------
        data
        """
        with self.open(**kwargs) as data_entry:
            data = data_entry.get(key)

        # reset string representation because output is extremely lengthy
        _patch_str_repr(data)

        return data

    def entry(self, backend=imasdef.MDSPLUS_BACKEND):
        """Return reference to `imas.DBEntry.`

        Parameters
        ----------
        backend : optional
            Which IMAS backend to use

        Returns
        ------
        entry : imas.DBEntry
            IMAS database entry
        """
        return imas.DBEntry(backend, self.db, self.shot, self.run, self.user)

    @contextmanager
    def open(self, backend=imasdef.MDSPLUS_BACKEND, create: bool = False):
        """Context manager to open database entry.

        Parameters
        ----------
        backend : optional
            Which IMAS backend to use
        create : bool, optional
            Create empty database entry if it does not exist.

        Yields
        ------
        entry : imas.DBEntry
            Opened IMAS database entry
        """
        entry = self.entry(backend=backend)
        opcode, _ = entry.open()

        if opcode == 0:
            logger.debug('Data entry opened: %s', self)
        elif create:
            cpcode, _ = entry.create()
            if cpcode == 0:
                logger.debug('Data entry created: %s', self)
            else:
                raise IOError(
                    f'Cannot create data entry: {self}. '
                    f'Create a new db first using `imasdb {self.db}`')
        else:
            raise IOError(f'Data entry does not exist: {self}')

        try:
            yield entry
        finally:
            entry.close()
