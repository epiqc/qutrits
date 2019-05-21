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
        fbase, fext = os.path.splitext(fname)
        return 'results-' + fbase + '.log'

    def validate(line):
        try:
            val = float(line)
            return True
        except ValueError:
            print('Warning: Invalid line: "{}"'.format(line))
        return False

    out_dir = '../results-2018-11-pranav/'

    def run(pattern, params):
        prefix = params + ': 0.1.0 -1   '
        line_transform = lambda line: prefix + line
        add_line_prefix_to_matches(pattern, out_dir, fname_transform, line_transform, validate)

    # cnx-btb
    # cnx-lin
    # cnx-lin-borrowed-1

    # sc-current
    # sc
    # sc-better-t1
    # sc-better-gates
    # sc-better-t1-and-gates
    # ti-qubit
    # ti-bare
    # ti-dressed

    run('bare-qutrit-*.txt', '{"n": 14, "noise": "ti-bare", "circ": "cnx-btb"}')
    run('dressed-qutrit-*.txt', '{"n": 14, "noise": "ti-dressed", "circ": "cnx-btb"}')

    run('current-sc-qutrit-*.txt', '{"n": 14, "noise": "sc-current", "circ": "cnx-btb"}')
    run('future-better-gates-and-t1-qutrit-*.txt', '{"n": 14, "noise": "sc-better-t1-and-gates", "circ": "cnx-btb"}')
    run('future-better-gates-qutrit-*.txt', '{"n": 14, "noise": "sc-better-gates", "circ": "cnx-btb"}')
    run('future-better-t1-qutrit-*.txt', '{"n": 14, "noise": "sc-better-t1", "circ": "cnx-btb"}')
    run('future-sc-qutrit-*.txt', '{"n": 14, "noise": "sc", "circ": "cnx-btb"}')

    # TODO: Fix the file names and add more


if __name__ == '__main__':
    main()
