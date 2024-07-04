from typing import Dict, Optional
from pragma.common.types.currency import Currency
from pragma.common.types.pair import Pair
from pragma.common.configs.asset_config import AssetConfig
from pydantic.dataclasses import dataclass
from dataclasses import field
import unittest


@dataclass
class HopHandler:
    hopped_currencies: Dict[str, str] = field(default_factory=dict)

    def get_hop_pair(self, pair: Pair) -> Optional[Pair]:
        """
        Returns a new pair if the quote currency is in the hopped_currencies list
        Otherwise, returns None

        :param pair: Pair
        :return: Optional[Pair]
        """

        if pair.quote_currency.id not in self.hopped_currencies:
            return None

        new_currency_id = self.hopped_currencies[pair.quote_currency.id]

        return Pair(
            pair.base_currency,
            Currency.from_asset_config(AssetConfig.from_ticker(new_currency_id)),
        )


class TestHopHandler(unittest.TestCase):
    def setUp(self):
        self.usdt = Currency.from_asset_config(AssetConfig.from_ticker("USDT"))
        self.usdc = Currency.from_asset_config(AssetConfig.from_ticker("USDC"))
        self.eth = Currency.from_asset_config(AssetConfig.from_ticker("ETH"))
        self.btc = Currency.from_asset_config(AssetConfig.from_ticker("BTC"))

        self.hop_handler = HopHandler(
            hopped_currencies={"USDC": "USDT", "USDT": "ETH", "ETH": "BTC"}
        )

    def test_get_hop_pair_exists(self):
        original_pair = Pair(self.usdt, self.usdc)
        result = self.hop_handler.get_hop_pair(original_pair)

        self.assertIsNotNone(result)
        self.assertEqual(result.base_currency, self.usdt)
        self.assertEqual(result.quote_currency, self.usdt)

    def test_get_hop_pair_not_exists(self):
        original_pair = Pair(self.usdc, self.btc)
        result = self.hop_handler.get_hop_pair(original_pair)

        self.assertIsNone(result)

    def test_get_hop_pair_chain(self):
        # Test first hop
        original_pair = Pair(self.eth, self.usdc)
        result = self.hop_handler.get_hop_pair(original_pair)

        self.assertIsNotNone(result)
        self.assertEqual(result.base_currency, self.eth)
        self.assertEqual(result.quote_currency, self.usdt)

        # Test second hop
        second_hop = self.hop_handler.get_hop_pair(result)
        self.assertIsNotNone(second_hop)
        self.assertEqual(second_hop.base_currency, self.eth)
        self.assertEqual(second_hop.quote_currency, self.eth)

        # Test third hop
        third_hop = self.hop_handler.get_hop_pair(second_hop)
        self.assertIsNotNone(third_hop)
        self.assertEqual(third_hop.base_currency, self.eth)
        self.assertEqual(third_hop.quote_currency, self.btc)

    def test_empty_hop_handler(self):
        empty_handler = HopHandler()
        pair = Pair(self.usdt, self.usdc)
        result = empty_handler.get_hop_pair(pair)

        self.assertIsNone(result)

    def test_get_hop_pair_same_currency(self):
        handler = HopHandler(hopped_currencies={"USDT": "USDT"})
        pair = Pair(self.eth, self.usdt)
        result = handler.get_hop_pair(pair)

        self.assertIsNotNone(result)
        self.assertEqual(result.base_currency, self.eth)
        self.assertEqual(result.quote_currency, self.usdt)


if __name__ == "__main__":
    unittest.main()
