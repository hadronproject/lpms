#!/bin/bash

version=$(cat ../VERSION)
mkdir -p ../../lpms-$version
cp -aR ../* ../../lpms-$version
tar -czf ../../lpms-$version.tar.gz ../../lpms-$version/
