from typing import Tuple

from starknet_py.net.account.account import Account
from starknet_py.net.client import Client


from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.types.types import (
    MeanFeedParams,
    TwapFeedParams,
    VolatilityFeedParams,
)


class SummaryStatsMixin:
    client: Client
    account: Account
    summary_stats: Contract

    async def calculate_mean(self, mean_feed_params: MeanFeedParams) -> Tuple[int, int]:
        """
        Calculates the mean for a given data feeds.

        :param asset: Asset for which we want to compute the mean
        :param start: Start timestamp
        :param stop: End timestamp
        :param aggregation_mode: AggregationMode

        :return: Tuple[int, int] (mean, decimals)
        """

        (response,) = await self.summary_stats.functions["calculate_mean"].call(
            *mean_feed_params.to_list()
        )

        return tuple(response)

    async def calculate_volatility(
        self, volatility_feed_params: VolatilityFeedParams
    ) -> Tuple[int, int]:
        """
        Calculates the volatility for a given data feeds.

        :param asset: Asset for which we want to compute the volatility
        :param start_tick: Starting timestamp
        :param end_tick: End timestamp
        :param num_samples: Number of samples used to compute the volatility
        :param aggregation_mode: AggregationMode

        :return: Tuple[int, int] (volatility, decimals)
        """

        (response,) = await self.summary_stats.functions["calculate_volatility"].call(
            *volatility_feed_params.to_list()
        )

        return tuple(response)

    async def calculate_twap(self, twap_feed_params: TwapFeedParams) -> Tuple[int, int]:
        """
        Calculates the TWAP for a given data feeds.
        see https://docs.pragma.build/Resources/Cairo%201/computational-feeds/TWAP for more info
        The TWAP will be calculated between start_time and start_time+time.

        :param asset: Asset for which we want to compute the volatility
        :param aggregation_mode: AggregationMode
        :param time: The duration (in seconds ) over which you want to calculate the TWAP.
        :param start_time: The start time (in seconds) from which you want to calculate the TWAP.

        :return: Tuple[int, int] (twap, decimals)
        """

        (response,) = await self.summary_stats.functions["calculate_twap"].call(
            *twap_feed_params.to_list()
        )

        return tuple(response)
