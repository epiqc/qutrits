#!/usr/bin/env python3

import os, sys, glob, json, itertools


def find_files(in_dir):
    return sorted(f for f in
                  itertools.chain.from_iterable(glob.glob(os.path.join(x[0], 'results-*'))
                        for x in os.walk(in_dir))
                  if os.path.isfile(f))

def parse_line(line, version_group, parse_val):
    colon = -1 - line[::-1].find(':')
    params = line[:colon] #json.loads(line[:colon])
    version, timestamp, val_str = line[colon+1:].split()
    timestamp = float(timestamp)
    val = parse_val(val_str)
    version_g = version_group(version)
    return params, version_g, timestamp, val

def collect_file(fname, out, version_group, parse_val):
    with open(fname) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line[:1] == "=": continue
            try:
                params, version_g, timestamp, val = parse_line(line, version_group, parse_val)
            except BaseException as e:
                print('Error: Malformed results: "{}"'.format(line))
                continue
            key = params if version_g is None else (params, version_g)
            val_list = out.get(key, [])
            val_list.append(val)  # timestamp
            out[key] = val_list

def collect_files(fnames, out, version_group, parse_val):
    for fname in fnames:
        collect_file(fname, out, version_group, parse_val)


def main(in_dir):
    out = {}

    def version_group(v):
        return None

    def parse_val(val):
        return float(val)

    collect_files(find_files(in_dir), out, version_group, parse_val)

    for key in sorted(out.keys()):
        val_arr = out[key]
        print('Params: {}'.format(key))
        print('    count = {}'.format(len(val_arr)))
        print('    avg. = {}'.format(sum(val_arr) / len(val_arr)))
        print()


if __name__ == '__main__':
    in_dir = '.'
    if len(sys.argv) >= 2:
        in_dir = sys.argv[1]

    main(in_dir)
