# validator-publisher

Pragma oracle publisher for Starknet validators, run next to a staking node.
It reuses the price-pusher pipeline and publishes with a dedicated oracle
signer account bound to the validator's staker address.

```bash
pragma-validator init --network sepolia --rpc-url http://localhost:9545/rpc/v0_10 \
  --staker-address 0x... --oracle-signer-address 0x...
pragma-validator preflight -c validator-publisher.yaml
pragma-validator register -c validator-publisher.yaml
pragma-validator run -c validator-publisher.yaml
```

Operator runbook and design: see the validator publishing specification.
