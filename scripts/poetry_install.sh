#!/bin/sh
# This script reflects the latest changes of pyproject.lock into the virtualenv
#  by running `poetry install --sync`
# It first configures poetry to use the right python for creation of the virtual env
set -x
set -u
set -e
DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "${DIR}/.." || exit

# all python packages, in topological order
. ${DIR}/projects.sh
_projects=". ${PROJECTS}"
echo "Running on following projects: ${_projects}"
for p in $_projects
do
  cd "${DIR}/../${p}" || exit
  (pyenv local && poetry env use $(which python)) || poetry env use 3.11
  poetry install --sync
done
