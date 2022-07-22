from __future__ import annotations

import logging
from collections import deque
from inspect import signature
from typing import Callable

import click
from pydantic import Field

from .config import cfg
from .schema import BaseModel

logger = logging.getLogger(__name__)


class Operation(BaseModel):
    """Operation, simple class which has a callable action."""

    description: str = Field(
        description='description of the operation to be done')
    action: Callable = Field(
        description='a function which can be executed when we '
        'decide to apply this operation')
    args: tuple = Field((),
                        description='positional arguments that have to be '
                        'passed to the action')
    kwargs: dict = Field({},
                         description='keyword arguments that will be '
                         'passed to the action')

    def __call__(self) -> Operation:
        logger.info(f'-: {self.description}')
        if not cfg.dry_run:
            self.action(*self.args, **self.kwargs)
        else:
            logger.info('Dry run enabled, refusing to apply operation: '
                        f'{self.description}')
        return self


class Operations(deque):
    """Operations Queue which keeps track of all the operations that need to be
    done."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        # Make it a singleton
        if not Operations._instance:
            Operations._instance = super().__new__(cls)
        return Operations._instance

    def add(self, *args, **kwargs) -> None:
        """convenience Operation wrapper around put."""

        self.append(Operation(*args, **kwargs))

    def put(self, item: Operation) -> None:
        """synonym for append."""
        self.append(item)

    def append(self, item: Operation) -> None:  # type: ignore
        """Restrict our diet to Operation objects only."""

        super().append(item)

    def apply(self) -> Operation:
        """Apply the next operation in the queue and remove it."""

        return self.popleft()()

    def apply_all(self) -> None:
        """Apply all queued operations and empty the queue."""
        while len(self) != 0:
            self.apply()

    def confirm_apply_all(self) -> bool:
        """First asks the user if he wants to apply everything.

        Returns
        -------
        bool: did we apply everything or not
        """

        # To print the descriptions we need to get them
        logger.info('')
        logger.info('Operations in the Queue:')
        logger.info('========================')
        for op in self:
            logging.info(op.description)

        if not cfg.dry_run:
            ans = click.confirm('Do you want to apply all these operations?',
                                default=False)
        else:
            logger.info('Dry run enabled, not applying operations')
            ans = False

        if ans:
            self.apply_all()
        return ans


op_queue = Operations()


def confirm_operations(func):
    """Decorator which confirms and applies queued operations after the
    function."""

    def wrapper(*args, **kwargs):
        ret = func(*args, **kwargs)
        op_queue.confirm_apply_all()
        return ret

    return wrapper


def add_to_op_queue(description: str):
    """Decorator which adds the function call to the op_queue, instead of
    executing it directly, the string can be a format string and use the
    function arguments."""

    def op_queue_real(func):

        def wrapper(*args, **kwargs) -> None:
            # For the description format we must convert args to kwargs
            sig = signature(func)
            args_to_kw = dict(zip(sig.parameters, args))
            fkwargs = kwargs.copy()
            fkwargs.update(args_to_kw)
            formatted_description = description.format(**fkwargs)

            # add the function to the queue
            op_queue.add(action=func,
                         args=args,
                         kwargs=kwargs,
                         description=formatted_description)

        return wrapper

    return op_queue_real
