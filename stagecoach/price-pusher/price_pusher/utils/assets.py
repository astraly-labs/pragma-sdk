from pragma.core.assets import PragmaAsset


def asset_to_pair_id(asset: PragmaAsset) -> str:
    if "pair" in asset:
        return list(asset.pair).join("/")
    elif "detail" in asset:
        return asset.detail.asset_name
    else:
        raise TypeError(f"Could not find the string pair of {asset}")
