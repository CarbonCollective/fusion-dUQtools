import logging
from typing import Iterable

from duqtools.config import cfg

from .ids import IDSMapping, ImasHandle, apply_model
from .matrix_samplers import get_matrix_sampler
from .models import WorkDirectory
from .operations import add_to_op_queue, confirm_operations, op_queue
from .schema.runs import Runs
from .system import get_system

logger = logging.getLogger(__name__)

RUN_PREFIX = 'run_'


def fail_if_locations_exist(locations: Iterable[ImasHandle]):
    """Check IDS coordinates and raise if any exist."""
    any_exists = False
    for location in locations:
        if location.exists():
            logger.info('Target %s already exists', location)
            any_exists = True
    if any_exists:
        raise IOError(
            'Found existing target location(s), use `duqtools clean` to '
            'remove or `--force` to override.')


@add_to_op_queue('Applying combination to {target_in}')
def apply_combination(target_in: ImasHandle, combination) -> None:
    core_profiles = target_in.get('core_profiles')
    ids_mapping = IDSMapping(core_profiles)

    for model in combination:
        apply_model(model, ids_mapping)

        logger.info('Writing data entry: %s', target_in)
        with target_in.open() as data_entry_target:
            core_profiles.put(db_entry=data_entry_target)


@add_to_op_queue('Writing out {workspace.runs_yaml}')
def write_runs_file(runs: list, workspace) -> None:

    runs = Runs.parse_obj(runs)
    with open(workspace.runs_yaml, 'w') as f:
        runs.yaml(stream=f)


@confirm_operations
def create(*, force, **kwargs):
    """Create input for jetto and IDS data structures.

    Parameters
    ----------
    force : bool
        Override protection if data and directories already exist.
    **kwargs
        Unused.
    """
    options = cfg.create
    if not options:
        logger.warning('No create options specified.')
        return

    workspace = WorkDirectory.parse_obj(cfg.workspace)

    template_drc = options.template
    dimensions = options.dimensions
    matrix_sampler = get_matrix_sampler(options.sampler.method)

    system = get_system()

    if not options.template_data:
        source = system.imas_from_path(template_drc)
    else:
        source = ImasHandle.parse_obj(options.template_data)

    logger.info('Source data: %s', source)

    matrix = tuple(dim.expand() for dim in dimensions)
    combinations = matrix_sampler(*matrix, **dict(options.sampler))

    if not force:
        if workspace.runs_yaml.exists():
            raise IOError(
                'Directory is not empty, use `duqtools clean` to clear or '
                '`--force` to override.')

        locations = (ImasHandle(db=options.data.db,
                                shot=source.shot,
                                run=options.data.run_in_start_at + i)
                     for i in range(len(combinations)))

        fail_if_locations_exist(locations)

    runs = []

    for i, combination in enumerate(combinations):
        run_name = f'{RUN_PREFIX}{i:04d}'
        run_drc = workspace.cwd / run_name

        op_queue.add(action=run_drc.mkdir,
                     kwargs={
                         'parents': True,
                         'exist_ok': force
                     },
                     description=f'Create folder {run_drc}')

        target_in = ImasHandle(db=options.data.db,
                               shot=source.shot,
                               run=options.data.run_in_start_at + i)
        target_out = ImasHandle(db=options.data.db,
                                shot=source.shot,
                                run=options.data.run_out_start_at + i)

        source.copy_ids_entry_to(target_in)

        apply_combination(target_in, combination)

        system.copy_from_template(template_drc, run_drc)
        system.write_batchfile(workspace, run_name)

        system.update_imas_locations(run=run_drc,
                                     inp=target_in,
                                     out=target_out)

        runs.append({
            'dirname': run_name,
            'data_in': target_in,
            'data_out': target_out,
            'operations': combination
        })

    write_runs_file(runs, workspace)
