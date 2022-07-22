from __future__ import annotations

import logging
import xml.sax
import xml.sax.handler
from getpass import getuser
from typing import TYPE_CHECKING

from packaging import version

from .._logging_utils import LoggingContext
from ..operations import add_to_op_queue
from ._imas import imas

if TYPE_CHECKING:
    from .ids import ImasHandle

PATH_IDSDEF = '/gw/swimas/core/installer/src/3.34.0/ual/4.9.3/xml/IDSDef.xml'


class Parser(xml.sax.handler.ContentHandler):

    def __init__(self):
        xml.sax.handler.ContentHandler.__init__(self)
        self.idss = []

    def startElement(self, name: str, attrs):
        if name == 'IDS':
            ids = {}
            for i in attrs.getNames():
                ids[i] = attrs.getValue(i)
            self.idss.append(ids)

    @classmethod
    def load_idsdef(cls):
        parser = cls()
        xml.sax.parse(PATH_IDSDEF, parser)
        return parser


def get_imas_ual_version():
    """Get imas/ual versions.

    Parsed from a string like: `imas_3_34_0_ual_4_9_3`
    """
    vsplit = imas.names[0].split('_')

    imas_version = version.parse('.'.join(vsplit[1:4]))
    ual_version = version.parse('.'.join(vsplit[5:8]))

    return imas_version, ual_version


@add_to_op_queue('Create {target} from template')
def copy_ids_entry(source: ImasHandle, target: ImasHandle):
    """Copies the ids entry to a new location.

    Parameters
    ----------
    source : ImasHandle
        Source ids entry
    target : ImasHandle
        Target ids entry

    Raises
    ------
    KeyError
        If the IDS entry you are trying to copy does not exist.
    """
    assert target.user == getuser()

    imas_version, _ = get_imas_ual_version()

    idss_in = imas.ids(source.shot, source.run)
    op = idss_in.open_env(source.user, source.db, str(imas_version.major))

    ids_not_found = op[0] < 0
    if ids_not_found:
        raise KeyError('The entry you are trying to copy does not exist')

    idss_out = imas.ids(target.shot, target.run)

    idss_out.create_env(target.user, target.db, str(imas_version.major))
    idx = idss_out.expIdx

    parser = Parser.load_idsdef()

    # Temporarily hide warnings, because this loop is very spammy
    with LoggingContext(level=logging.CRITICAL):

        for ids_info in parser.idss:
            name = ids_info['name']
            maxoccur = int(ids_info['maxoccur'])

            if name in ('ec_launchers', 'numerics', 'sdn'):
                continue

            for i in range(maxoccur + 1):
                ids = idss_in.__dict__[name]
                ids.get(i)
                ids.setExpIdx(idx)  # this line sets the index to the output
                ids.put(i)

    idss_in.close()
    idss_out.close()
