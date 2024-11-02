## v2.3.2 (2024-11-02)

### Feat

- lambda function (#216)

### Fix

- Ekubo fetcher for quote_address == 0 (#218)
- Dexscreener fetcher API bug (#220)

## v2.3.0 (2024-10-29)

### Feat

- Nostra LP Pricer (#214)

## v2.2.0 (2024-10-24)

### Feat

- Ekubo Fetcher onchain (#211)

## v2.1.4 (2024-10-21)

## v2.1.3 (2024-10-16)

### Feat

- pragma devnet config
- add support for pragma_devnet chain (#207)

### Fix

- Mandatory VRF request fees estimation (#205)

## v2.1.2 (2024-09-04)

### Feat

- merkle-maker buildspec (#191)

### Fix

- **stable_but_slow_vrf**: Revert + Tweak old stable vrf
- **stable_but_slow_vrf**: removed keys
- **stable_but_slow_vrf**: Todo stuff
- **stable_but_slow_vrf**: Indexing without apibara
- **stable_but_slow_vrf**: Fix test
- **stable_but_slow_vrf**: check interval
- **estimate_fee_fix**: fix (#196)
- **merkle_maker**: module name
- remove useless params (#192)
- update lock files in ci (#190)
- get vrf status in pending block

## v2.1.0 (2024-08-07)

### Feat

- merkle-maker + MerkleFeed mixin (#178)
- add migration guide to docs (#185)

### Fix

- readme link (#186)
- linters

## v2.0.6 (2024-08-02)

### Feat

- add EKUBO pairs to fetchers
- Dexscreener fetcher (#183)
- Merkle Maker service (#164)

### Fix

- pair serialization method
- Price pusher median comparison (#182)

## v2.0.3 (2024-07-31)

### Feat

- config file path for checkpointer Dockerfile (#177)

### Fix

- Price pusher concurrency issue onchain (#180)
- Fixed some price pusher edge cases (#179)

## v2.0.2 (2024-07-29)

### Fix

- infra things (#176)
- Dockerfile's infra config path (#175)
- some infra changes (#173)
- More price pusher fixes after Kakarot test (#172)

## v2.0.1 (2024-07-27)

### Feat

- add infra files (#170)
- Deribit Generic Fetcher + MerkleFeedMixin (#150)

### Fix

- Various fixes after trying things on Kakarot (#171)
- dockerfile build ci (#168)

## v2.0.0-rc4 (2024-07-25)

## v2.0.0-rc3 (2024-07-24)

### Fix

- rtd warnings

## v2.0.0-rc2 (2024-07-23)

### Feat

- Private key with keystores (#161)

## v2.0.0-rc1 (2024-07-23)

### Feat

- Checkpoint setter (#145)
- ci-tests (#160)
- add infra folder for deployments (#152)
- pypi test jobs, better permissions management (#148)
- add id-token permission (#147)

### Fix

- vrf listener remove args + add sphinx docs config (#162)
- CI tests (#159)
- CI tests and prerelease (#158)
- ci-tests error (#157)
- try to fix pragma-utils error into test-pypi job (#149)
- workflows publisher, docker-build (#146)
- env variables, rm artifacts for release (#144)

## v2.0.0-rc0 (2024-07-15)

### Feat

- **ci/cd**: build/release pipeline (#139)

## v1.5.2 (2024-07-01)

### Fix

- **vrf**: log error

## v1.5.1 (2024-07-01)

### Fix

- vrf ignore request threshold

## v1.5.0 (2024-06-29)

### Feat

- PR template
- price pusher (#121)

### Fix

- **vrf-handler**: rpc url env var

## v1.4.7 (2024-06-26)

### Feat

- get vrf requests status in parallel

## v1.4.6 (2024-06-26)

### Feat

- update default RPCs

## v1.4.5 (2024-06-26)

### Fix

- vrf handler (#126)
- PragmaAPIError as exception
- **stagecoach**: default values

## v1.4.4 (2024-06-21)

## v1.4.3 (2024-06-19)

## v1.4.2 (2024-06-19)

### Feat

- add NSTR support (#119)

## v1.4.1 (2024-06-18)

### Feat

- gate io and mexc fetchers (#118)

## v1.4.0 (2024-06-16)

### Feat

- Publishing offchain future assets (#109)
- PragmaAPIClient clean up (#113)
- vrf cron (#110)
- **x10_new_assets**: Added new assets

## v1.3.10 (2024-06-04)

### Fix

- **publisher**: pending block support
- **publisher**: deviation check

## v1.3.9 (2024-05-23)

### Fix

- **vrf**: query latest block

## v1.3.8 (2024-05-23)

## v1.3.7 (2024-05-23)

### Fix

- **vrf**: support pending block

## v1.3.6 (2024-05-23)

### Fix

- **vrf**: get events chunk size

## v1.3.5 (2024-05-23)

### Fix

- **vrf**: ignore old requests (#103)

## v1.3.4 (2024-05-22)

### Fix

- vrf block number condition (#102)

## v1.3.3 (2024-05-22)

### Fix

- get events to pending block (#101)
- Binance fetcher (#100)

## v1.3.2 (2024-04-23)

### Fix

- clean up code (#99)

## v1.3.1 (2024-04-15)

## v1.3.0 (2024-04-15)

## v1.2.14 (2024-03-15)

## v1.2.13 (2024-03-14)

## v1.2.12 (2024-03-14)

## v1.2.11 (2024-03-13)

## v1.2.10 (2024-03-08)

## v1.2.9 (2024-03-08)

## v1.2.8 (2024-03-08)

## v1.2.7 (2024-03-07)

### Fix

- update deps & apply nonce mixin (#87)

## v1.2.6 (2024-03-05)

### Fix

- PublisherFetchError as Exception

## v1.2.5 (2024-02-23)

## v1.2.4 (2024-02-21)

### Fix

- kucoin fetcher timestamp

## v1.2.3 (2024-02-21)

### Fix

- fetchers volume overflow
- strk pairs fetchers hopping (#79)

## v1.2.2 (2024-02-20)

### Fix

- fetcher (#78)

## v1.2.1 (2024-02-20)

### Fix

- minor fixes

## v1.2.0 (2024-02-20)

### Feat

- add STRK to geckoterminal
- add STRK to defillama fetcher

### Fix

- gecko fetcher for STRK/USD
- defillama/gecko fetchers
- default api url

## v1.1.9 (2024-02-13)

### Feat

- add StarknetAMMFetcher

## v1.1.8 (2024-02-12)

## v1.1.7 (2024-02-05)

## v1.1.6 (2024-01-18)

### Fix

- rpc urls

## v1.1.5 (2024-01-18)

## v1.1.4 (2024-01-18)

## v1.1.3 (2024-01-18)

## v1.1.2 (2024-01-15)

## v1.1.1 (2024-01-05)

## v1.1.0 (2023-12-27)

## v1.0.10 (2023-12-18)

## v1.0.9 (2023-11-23)

## v1.0.8 (2023-11-21)

## v1.0.7 (2023-11-20)

## v1.0.6 (2023-11-16)

## v1.0.5 (2023-11-05)

## v1.0.4 (2023-11-05)

## v1.0.3 (2023-10-17)

## v1.0.2 (2023-10-16)

## v1.0.1 (2023-09-29)

### Feat

- add default rpc's and remove rpc_key env (#23)

### Fix

- get client id for rpc url (#34)
- missing warning module import (#25)

## v1.0.0 (2023-09-19)

## v1.0.0-beta7 (2023-09-17)

## v1.0.0-beta6 (2023-09-16)

## v1.0.0-beta5 (2023-09-12)

## v1.0.0-beta4 (2023-09-01)

## v1.0.0-beta3 (2023-09-01)

## v1.0.0-beta2 (2023-09-01)

## v1.0.0-beta1 (2023-09-01)

## v1.0.0-beta (2023-09-02)

## v1.0.0-alpha (2023-08-30)
