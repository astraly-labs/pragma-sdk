#!/bin/bash

# delete all artifacts except precompiled ones
mkdir -p $CONTRACTS_COMPILED_DIRECTORY
find $CONTRACTS_COMPILED_DIRECTORY -maxdepth 1 -type f -delete

# compile Cairo1 test contracts
COMPILER_VERSION=`scarb --version 2> /dev/null`
printf "Compiling Cairo1 contracts with $COMPILER_VERSION\n\n"

cd $BUILD_DIRECTORY && scarb build

echo "Compiled Contracts successfully"
