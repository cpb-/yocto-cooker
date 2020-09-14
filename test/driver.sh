#!/bin/bash

set -e

# use cooker-executable this-dir
THISDIR=$(realpath `dirname $0`)
PATH=$THISDIR:$PATH

WHICH=$(which cooker)

if [ $WHICH != "$THISDIR/cooker" ]
then
	echo need to use internal cooker-executable - paths need fixing
	exit 1
fi

# test-name
N=$1

# test-source-dir
S=$(realpath $2)

# runtime-dir (if automated, cmake-build-dir)
T=$(pwd)/tests/$N

# clean and setup test-dir
rm -rf $T
mkdir -p $T

# include test-result helpers
. $THISDIR/functions.sh

cd $T
. $S/test
