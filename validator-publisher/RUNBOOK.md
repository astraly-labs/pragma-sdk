# validator-publisher: operator runbook

`validator-publisher` runs next to your Starknet staking node and publishes
Pragma prices for the validator publishing pilot. It signs with a dedicated
**oracle signer** account bound to your staker address. Pilot prices are
published on-chain in shadow: no protocol reads them, they are compared with
Pragma's production oracle.

Current release: [`validator-publisher-v0.1.1`](https://github.com/astraly-labs/pragma-sdk/releases/tag/validator-publisher-v0.1.1), image
`ghcr.io/astraly-labs/pragma-sdk/validator-publisher@sha256:ba9e4178a832615d66c4fd22df4832bb15d076e276c4f19e8d014926788e8a2d`.
Verify it before the first run (section 8, step 1).

Commands below use the image; `pragma-validator` is its entrypoint:

```bash
alias pragma-validator='docker run --rm -it --env-file ./oracle-signer.env \
  -v "$PWD/validator-publisher:/config" --network pathfinder_net \
  ghcr.io/astraly-labs/pragma-sdk/validator-publisher@sha256:ba9e4178a832615d66c4fd22df4832bb15d076e276c4f19e8d014926788e8a2d'
```

## 1. Requirements

- A synced Starknet full node serving JSON-RPC 0.10 (Pathfinder or Juno), reachable from the container.
- An active staker: not exiting, self-stake at least the pilot minimum (20,000 STRK).
- Docker with the compose plugin.
- STRK for the oracle signer's gas. Keep at least 50 STRK on it.
- An accurate clock (NTP). The oracle rejects entries with bad timestamps.

## 2. Keys

Starknet staking separates the staker (cold), reward (cold) and operational (hot, attestation) addresses. The oracle signer is a **fourth, dedicated** hot account:

- Never reuse the staker, reward or operational address. The registry rejects it at registration and revokes it if it is reused later.
- It only needs to sign `publish_data_entries` on the pilot oracle and hold STRK for gas.
- The staker key never goes on the publisher host. Registration only asks the staker to sign one transaction from its usual wallet.

Create the oracle signer with a plain Stark signature account, for example with starkli and an OpenZeppelin account:

```bash
starkli signer keystore new oracle-signer.keystore.json
starkli account oz init oracle-signer.account.json --keystore oracle-signer.keystore.json
# send STRK to the address printed above, then:
starkli account deploy oracle-signer.account.json --keystore oracle-signer.keystore.json
```

Accounts with a guardian or a hardware signer cannot be used: the publisher signs every transaction itself.

## 3. Configure

```bash
mkdir validator-publisher
pragma-validator init -o /config/validator-publisher.yaml \
  --network sepolia \
  --rpc-url http://pathfinder:9545/rpc/v0_10 \
  --staker-address 0x<your staker address> \
  --oracle-signer-address 0x<oracle signer address>
```

The private key is read from `ORACLE_SIGNER_PRIVATE_KEY` by default. Put it in `oracle-signer.env`, readable by you only:

```bash
echo "ORACLE_SIGNER_PRIVATE_KEY=0x..." > oracle-signer.env && chmod 600 oracle-signer.env
```

Other sources: `keystore:/config/key.json:PASSWORD`, `aws:SECRET_NAME`, `gcp:SECRET_NAME`.

The config is versioned (`schema_version`). Unknown fields are refused and only the pilot pairs are accepted. Contract addresses ship with each release and are not part of the config.

## 4. Preflight

```bash
pragma-validator preflight -c /config/validator-publisher.yaml
```

Every line must be `ok` before you publish. `warn` lines do not block. Preflight checks:

- the node: chain id, RPC version, sync, clock;
- the oracle signer: deployed, balance;
- key separation, self-stake and registration;
- a dry-run fetch: at least 4 allowed sources per pair, within 2% of independent venues, and no fetcher reading Pragma's oracle.

Registration shows as failing until step 5 is done.

## 5. Register

```bash
pragma-validator register -c /config/validator-publisher.yaml
```

1. The command sends `declare_oracle_signer(staker)` from the oracle signer.
2. It prints the call the **staker** must sign: `bind_oracle_signer(<oracle signer>)` on the ValidatorRegistry. Sign it from the staker wallet, for example:

   ```bash
   starkli invoke <registry> bind_oracle_signer <oracle signer> \
     --account staker.account.json --keystore staker.keystore.json --rpc <node rpc>
   ```

3. Run `preflight` again: registration must be `active`.

## 6. Run

Add `deploy/docker-compose.yaml` to your node's compose file (it pins the current release), then:

```bash
docker compose up -d validator-publisher
curl -s localhost:8080/health   # liveness: the poll loop runs
curl -s localhost:8080/ready    # readiness: pushes succeed
pragma-validator status -c /config/validator-publisher.yaml
```

The first push happens within a minute: a new publisher has no entries yet. Afterwards it pushes when its own entries are older than `time_difference` (1800 s) or deviate more than `price_deviation` (1%).

## 7. Monitoring

- Scrape `:8080/metrics` and load `deploy/alerts.rules.yml`.
- Key metrics:
  - `validator_publisher_registry_status{status}`
  - `validator_publisher_signer_balance_strk`
  - `pragma_pusher_last_push_timestamp_seconds`
  - `validator_publisher_build_info{version,config_hash}`
  - `validator_publisher_pair_sources{pair}`: allowed sources that answered in the last poll
- Read the pilot feed the way a consumer does:

  ```bash
  pragma-validator feed-status --network sepolia --rpc-url <node url>
  ```

  For each pair it prints `VALID` with the price, `WITHHELD`, or `STALE`, with the number of markets and of publishers behind it. A pair is `VALID` only with at least 4 markets holding a fresh entry (under 40 min), counted across every operator. Only entries of `ACTIVE` operators on sources the registry allows count, so a revoked operator drops out at once. The command exits with 1 if any pair is not `VALID`.
- Keep ports 8080 (publisher), 3000, 9090 and the node's RPC off the public internet.

## 8. Upgrade and rollback

Releases are tagged `validator-publisher-vX.Y.Z`. Each image is signed (cosign, keyless), with an SBOM and build provenance. Rollouts are staged: Pragma's validator first, then waves of operators. Upgrade when your wave is announced.

1. Verify the new image with the `cosign verify` command in the release notes. Without cosign, the GitHub CLI checks the build provenance:

   ```bash
   gh attestation verify oci://ghcr.io/astraly-labs/pragma-sdk/validator-publisher@<digest> --repo astraly-labs/pragma-sdk
   ```
2. Run `preflight` with the new image.
3. Replace the digest in your compose file and run `docker compose up -d validator-publisher`.
4. Check `/ready` and `status`.

Rollback: put the previous digest back and run `docker compose up -d validator-publisher`. Config files stay compatible with the previous release, and no on-chain action is needed.

Changes per release:

- **0.1.1**: `feed-status`, metric `validator_publisher_pair_sources{pair}`, alert `ValidatorPublisherLowSourceCoverage`. Reload `deploy/alerts.rules.yml`. No config change.

## 9. Rotate the oracle signer

1. Create and fund a new account (step 2).
2. Run:

   ```bash
   pragma-validator rotate -c /config/validator-publisher.yaml \
     --new-signer-address 0x<new> --new-private-key env:NEW_ORACLE_SIGNER_PRIVATE_KEY
   ```

3. The staker signs the printed `bind_oracle_signer(<new>)`. This releases the old signer in the same transaction.
4. Update `oracle_signer_address` and the key in the config, restart, run `preflight`.
5. Move the remaining STRK off the old signer.

## 10. Revoke

- **Oracle key suspected compromised:** `pragma-validator revoke -c /config/validator-publisher.yaml` (signed by the oracle signer), or `revoke_oracle_signer(<staker>)` signed by the staker from its wallet. Publishing stops at once. Register a new signer to resume.
- **Automatic:** the registry stops accepting your entries if the staker:
  - sends an unstake intent;
  - is removed from staking;
  - drops below the minimum self-stake;
  - turns the oracle signer into its operational or reward address.

## 11. Leave the pilot

Run `revoke`, stop the container, and move the STRK left on the oracle signer.

## 12. Troubleshooting

- **`rpc version`**: point `rpc_url` at the node's 0.10 endpoint (`/rpc/v0_10` on Pathfinder, `/v0_10` on Juno).
- **`node sync`**: wait for the node to catch up. The publisher reads and writes through it only.
- **`clock`**: fix NTP on the host.
- **`signer balance`**: send STRK to the oracle signer.
- **`registration: declared, waiting for the staker's bind`**: the staker has not signed `bind_oracle_signer` yet.
- **`registration: staker is bound to another signer`**: the config has the wrong oracle signer. Use the bound one, or rotate.
- **`<pair> sources`**: fewer than 4 allowed sources answered. Check outbound HTTPS from the host.
- **`only N allowed source(s) answered` in the logs, `ValidatorPublisherLowSourceCoverage` alert**: your publisher still publishes the sources that answered. The 4-market quorum applies to the feed, across all operators, not to each publisher. Check outbound HTTPS from the host and the fetcher logs. If the same source is missing for every operator, that is a shared upstream failure: report it to Pragma.
- **`feedback loop`**: never expected. Report it to Pragma with the logs.
