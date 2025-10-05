#!/bin/sh

projdir=$(dirname $(realpath $0))

if test ! -f ${projdir}/src/zuspec/dataclasses/llms.txt; then
  curl https://zuspec.github.io/zuspec-dataclasses/llms.txt -o ${projdir}/src/zuspec/dataclasses/llms.txt
fi
