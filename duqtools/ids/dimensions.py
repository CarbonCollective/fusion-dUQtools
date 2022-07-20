from __future__ import annotations

import logging
from functools import singledispatch

import numpy as np

from ..schema import BaseModel, IDSOperation, IDSSampler
from ._mapping import IDSMapping

logger = logging.getLogger(__name__)


@singledispatch
def apply_model(model: BaseModel, ids_mapping: IDSMapping) -> None:
    """Apply operation in model to IDS. Data are modified in-place.

    Parameters
    ----------
    model
        The model describes the operation to apply to the data.
    ids_mapping : IDSMapping
        Core profiles IDSMapping, data to apply operation to.
        Must contain the IDS path.

    Raises
    ------
    NotImplementedError
        When the model is unknown
    """

    raise NotImplementedError(f'Unknown model: {model}')


@apply_model.register
def _(model: IDSOperation, ids_mapping: IDSMapping) -> None:

    npfunc = getattr(np, model.operator)

    profile = ids_mapping.flat_fields[model.ids]

    if model.scale_to_error:
        sigma_key = model.ids + model._upper_suffix

        if model.value < 0:
            lower_key = model.ids + model._lower_suffix
            if lower_key in ids_mapping.flat_fields:
                sigma_key = lower_key

        sigma_bound = ids_mapping.flat_fields[sigma_key]
        sigma = abs(sigma_bound - profile)

        value = sigma * model.value
    else:
        value = model.value

    logger.info('Apply %s', model)

    logger.debug('data range before: %s - %s', profile.min(), profile.max())
    npfunc(profile, value, out=profile)
    logger.debug('data range after: %s - %s', profile.min(), profile.max())


@apply_model.register
def _(model: IDSSampler, ids_mapping: IDSMapping) -> None:
    """Apply operation to IDS. Data are modified in-place.

    Parameters
    ----------
    ids_mapping : IDSMapping
        Core profiles IDSMapping, data to apply operation to.
        Must contain the IDS path.
    """
    upper_key = model.ids + model._upper_suffix
    lower_key = model.ids + model._lower_suffix

    logger.info('Apply %s', model)

    profile = ids_mapping.flat_fields[model.ids]

    upper = ids_mapping.flat_fields[upper_key]
    sigma_upper = abs(upper - profile)

    has_lower = lower_key in ids_mapping.flat_fields

    if model.bounds == 'auto':
        bounds = 'asymmetric' if has_lower else 'symmetric'
    else:
        bounds = model.bounds

    # this is only ever necessary if upper/lower are different
    if bounds == 'symmetric':

        if has_lower:
            lower = ids_mapping.flat_fields[lower_key]
            sigma_lower = abs(profile - lower)
            mean_sigma = (sigma_upper + sigma_lower) / 2
        else:
            mean_sigma = sigma_upper

        rng = np.random.default_rng()
        new_profile = rng.normal(loc=profile, scale=mean_sigma)

    elif bounds == 'asymmetric':
        raise NotImplementedError
    else:
        raise ValueError(f'Unknown value for argument: bounds={model.bounds}')

    # update in-place
    profile[:] = new_profile
