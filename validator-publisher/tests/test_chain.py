from validator_publisher.chain import decode_staker_info

# get_staker_info_v1(Pragma's staker) on mainnet, 2026-11-03
MAINNET_PRAGMA = [
    0x0,
    0x258DD1CAF7FFCBEDCEB0DFFD83EC17E31DF2888F19DDA09AC5C1C8505064DDE,
    0x52DC40F04AD96BCE27C3EF4775037BF6EBD115C78CFD747F8DCD59E4AA24F2C,
    0x1,
    0x43C33C1937564800000,
    0x192E5051BBBF2C8A581,
    0x0,
    0x3199FF0F152426280502DAD5D554448AD211C3B62D82C01114986C421E65388,
    0xEC37CE43F1C212625433A,
    0x1F4,
]


def test_decode_live_mainnet_staker():
    info = decode_staker_info(MAINNET_PRAGMA)
    assert info.reward_address == MAINNET_PRAGMA[1]
    assert info.operational_address == MAINNET_PRAGMA[2]
    assert info.unstake_time is None
    assert info.amount_own == 20_000 * 10**18


def test_decode_exiting_staker():
    exiting = MAINNET_PRAGMA[:3] + [0x0, 1_800_000_000] + MAINNET_PRAGMA[4:]
    info = decode_staker_info(exiting)
    assert info.unstake_time == 1_800_000_000
    assert info.amount_own == 20_000 * 10**18


def test_decode_unknown_staker():
    assert decode_staker_info([0x1]) is None
