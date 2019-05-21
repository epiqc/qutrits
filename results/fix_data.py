#!/usr/bin/env python3


import os, glob, itertools


def add_line_prefix_to_file(fname, out_name, line_transform, validate):
    with open(fname) as f_in:
        with open(out_name, 'w') as f_out:
            print('Write:', fname, '->', out_name)
            for line in f_in:
                line = line.strip()
                if validate(line):
                    f_out.write(line_transform(line) + '\n')

def find_files(f_pattern):
    return sorted(f for f in glob.glob(f_pattern)
                  if os.path.isfile(f))

def add_line_prefix_to_matches(f_pattern, out_dir, fname_transform, line_transform, validate):
    file_path = None
    for file_path in find_files(f_pattern):
        in_dir, fname = os.path.split(file_path)
        out_name = fname_transform(fname)
        out_path = os.path.join(out_dir, out_name)
        add_line_prefix_to_file(file_path, out_path, line_transform, validate)

    if file_path is None:
        print('Error: No files matching pattern: ""'.format(f_pattern))

def main():
    def fname_transform(fname):
        #fbase, fext = os.path.splitext(fname)
        return fname

    def validate(line):
        if line.startswith("="):
            return False
        try:
            val = float(line.split()[-1])
            return True
        except ValueError:
            print('Warning: Invalid line: "{}"'.format(line))
        return False

    out_dir = 'results-2018-11-28-fix/'

    def run(pattern, params):
        prefix = params + ': 0.1.0 -1   '
        line_transform = lambda line: prefix + line.split()[-1]
        add_line_prefix_to_matches(pattern, out_dir, fname_transform, line_transform, validate)

    run('results-2018-11-28/results-*.log', '{"n": 14, "noise": "sc-better-t1-and-gates", "circ": "cnx-btb"}')


if __name__ == '__main__':
    main()
