from testcontainers.core.container import DockerContainer

DEVNET_IMAGE = "shardlabs/starknet-devnet-rs"
DEVNET_PORT = 5050
DEVNET_ARGS = "--seed 1 --block-generation-on 1 --fork-network https://starknet-mainnet.public.blastapi.io/rpc/v0_7"


def starknet_devnet_container() -> DockerContainer:
    devnet = DockerContainer(DEVNET_IMAGE)
    devnet.with_command(DEVNET_ARGS)
    devnet.with_exposed_ports(DEVNET_PORT)
    devnet.with_bind_ports(DEVNET_PORT, DEVNET_PORT)
    return devnet
