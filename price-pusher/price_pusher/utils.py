from typing import List, Union, Optional, TypeVar

T = TypeVar("T")


def exclude_none_and_exceptions(
    to_filter: List[Optional[Union[T, BaseException]]],
) -> List[T]:
    """
    Remove exceptions and none from a list of items.
    """
    return [
        item
        for item in to_filter
        if item is not None and not isinstance(item, BaseException)
    ]


def flatten_list(to_flatten: List[Union[T, List[T]]]) -> List[T]:
    """
    Flatten a list that contains items and list of items into a list of items.
    """
    return [
        val
        for item in to_flatten
        for val in (item if isinstance(item, (list, tuple)) else [item])
    ]
