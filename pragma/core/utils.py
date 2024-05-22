import inspect
import logging
from functools import wraps
from typing import TypeVar

from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def str_to_felt(text):
    if text.upper() != text:
        logger.warning("Converting lower to uppercase for str_to_felt: %s", text)
        text = text.upper()
    b_text = bytes(text, "utf-8")
    return int.from_bytes(b_text, "big")


def felt_to_str(felt):
    num_bytes = (felt.bit_length() + 7) // 8
    bytes_ = felt.to_bytes(num_bytes, "big")
    return bytes_.decode("utf-8")


def log_entry(entry):
    logger.info("Entry: %s", entry.serialize())


def currency_pair_to_pair_id(quote, base):
    return f"{quote}/{base}".upper()


def key_for_asset(asset):
    return asset["key"] if "key" in asset else currency_pair_to_pair_id(*asset["pair"])


def pair_id_for_asset(asset):
    pair_id = (
        asset["key"] if "key" in asset else currency_pair_to_pair_id(*asset["pair"])
    )
    return pair_id


def get_cur_from_pair(asset):
    return asset.split("/")


T = TypeVar("T")


def make_sync(fn):
    sync_fun = async_to_sync(fn)

    @wraps(fn)
    def impl(*args, **kwargs):
        return sync_fun(*args, **kwargs)

    return impl


def add_sync_methods(original_class: T) -> T:
    """
    Decorator for adding a synchronous version of a class.
    :param original_class: Input class
    :return: Input class with .sync property that contains synchronous version of this class
    """
    properties = {**original_class.__dict__}
    for name, value in properties.items():
        sync_name = name + "_sync"

        # Handwritten implementation exists
        if sync_name in properties:
            continue

        # Make all callables synchronous
        if inspect.iscoroutinefunction(value):
            setattr(original_class, sync_name, make_sync(value))
            _set_sync_method_docstring(original_class, sync_name)
        elif isinstance(value, staticmethod) and inspect.iscoroutinefunction(
            value.__func__
        ):
            setattr(original_class, sync_name, staticmethod(make_sync(value.__func__)))
            _set_sync_method_docstring(original_class, sync_name)
        elif isinstance(value, classmethod) and inspect.iscoroutinefunction(
            value.__func__
        ):
            setattr(original_class, sync_name, classmethod(make_sync(value.__func__)))

    return original_class


def _set_sync_method_docstring(original_class, sync_name: str):
    sync_method = getattr(original_class, sync_name)
    sync_method.__doc__ = "Synchronous version of the method."
